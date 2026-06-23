#include "globals.h"
#include "network_manager.h"
#include "hardware_control.h"
#include "traffic_logic.h"

void firebaseTask(void *pvParameters) {
    Serial.println("Firebase task started on Core 0");
    while (true) {
        String* jsonStrPtr = NULL;
        if (xQueueReceive(firebaseQueue, &jsonStrPtr, portMAX_DELAY) == pdPASS) {
            if (jsonStrPtr != NULL) {
                FirebaseJson json;
                json.setJsonData(jsonStrPtr->c_str());
                if (Firebase.updateNode(fbdo, "/traffic_system/latest_status", json)) {
                    // Success
                } else {
                    Serial.print("Firebase async update failed: ");
                    Serial.println(fbdo.errorReason());
                }
                delete jsonStrPtr;
            }
        }
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

void setup() {
    Serial.begin(115200);
    
    // GPIO Initialization
    pinMode(R_1, OUTPUT); pinMode(Y_1, OUTPUT); pinMode(G_1, OUTPUT);
    pinMode(R_2, OUTPUT); pinMode(Y_2, OUTPUT); pinMode(G_2, OUTPUT);
    pinMode(R_3, OUTPUT); pinMode(Y_3, OUTPUT); pinMode(G_3, OUTPUT);
    pinMode(R_4, OUTPUT); pinMode(Y_4, OUTPUT); pinMode(G_4, OUTPUT);
    pinMode(SW0, INPUT_PULLUP); pinMode(SW1, INPUT_PULLUP);
    pinMode(SW2, INPUT_PULLUP);
    
    // TM1637 Display Setup
    display.setBrightness(0x0f);
    display.clear();
    
    // Wi-Fi and MQTT connection
    setup_wifi();
    client.setBufferSize(MQTT_BUFFER_SIZE);
    client.setServer(mqtt_server, MQTT_BROKER_PORT);
    client.setKeepAlive(60);
    client.setSocketTimeout(15);
    client.setCallback(callback);
    ensureMqttConnected();
    
    // Firebase Setup
    Serial.println("Khoi tao Firebase...");
    configTime(7 * 3600, 0, "pool.ntp.org", "time.nist.gov");
    unsigned long startSync = millis();
    while (time(nullptr) < 100000 && millis() - startSync < 5000) {
        delay(100);
    }
    
    firebaseConfig.host = FIREBASE_HOST;
    firebaseConfig.api_key = FIREBASE_AUTH; 
    firebaseAuth.user.email = "test@gmail.com";     
    firebaseAuth.user.password = "123456";           
    
    Firebase.begin(&firebaseConfig, &firebaseAuth);
    Firebase.reconnectWiFi(true);
    
    // Khởi tạo Queue và Task cho Firebase chạy ngầm trên Core 0
    firebaseQueue = xQueueCreate(10, sizeof(String*));
    xTaskCreatePinnedToCore(
        firebaseTask,
        "FirebaseTask",
        8192,
        NULL,
        1,
        NULL,
        0
    );
    
    // Initial states
    lastChangeTime = millis();
    updateTimeLeft();
    updateLEDs();
    displayTime();
    
    Serial.println("He thong da khoi dong");
}

void loop() {
    ensureMqttConnected();
    client.loop();
    
    // Publish light state immediately on change
    static TrafficState lastPublishedState = (TrafficState)-1;
    if (currentState != lastPublishedState) {
        publishLightState(currentState);
        lastPublishedState = currentState;
    }
    
    checkSleepMode(); 
    
    static bool wasSleeping = false;
    if (sleepMode) {
        if (!wasSleeping) {
            enterSleepMode();
            wasSleeping = true;
        }
        if (millis() - lastMqttPub > 2000) { 
            publishTrafficStatusToFirebase();
            lastMqttPub = millis();
        }
        return;
    }
    wasSleeping = false;
    
    checkButtons(); 
    
    if (currentMode == MODE_AUTO) {
        autoMode();
    }
    
    displayTime();
    
    if (millis() - lastMqttPub > 1000) {
        publishTrafficStatusToFirebase();
        lastMqttPub = millis();
    }
    
    delay(10); 
}