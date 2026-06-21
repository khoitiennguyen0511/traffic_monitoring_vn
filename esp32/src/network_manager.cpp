#include "network_manager.h"
#include "hardware_control.h"
#include "traffic_logic.h"

void setup_wifi() {
    delay(10);
    Serial.println();
    Serial.print("Dang ket noi WiFi: ");
    Serial.println(ssid);
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println("");
    Serial.println("WiFi da ket noi");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
}

void callback(char* topic, byte* payload, unsigned int length) {
    if (length >= MQTT_BUFFER_SIZE) {
        Serial.println("MQTT payload qua lon, bo qua");
        return;
    }
    
    char messageBuf[MQTT_BUFFER_SIZE];
    memcpy(messageBuf, payload, length);
    messageBuf[length] = '\0';
    String message = String(messageBuf);
    
    Serial.print("Nhan lenh MQTT tu topic: ");
    Serial.print(topic);
    Serial.print(", Message: ");
    Serial.println(message);
    
    // 1. Green Time command
    if (String(topic) == topic_sub_cmd) {
        if (currentMode == MODE_AUTO) { 
            int new_green_time = message.toInt();
            if (new_green_time > 0) {
                greenTime1 = new_green_time;
                greenTime2 = new_green_time; 
                Serial.print("Cap nhat Green Time moi (thủ công): ");
                Serial.println(new_green_time);
                
                lastChangeTime = millis();
                updateTimeLeft();
                updateLEDs();
            }
        }
    }
    // 2. Control Mode command
    else if (String(topic) == topic_sub_manual) {
        if (message == "AUTO") {
            currentMode = MODE_AUTO;
            Serial.println("Remote: Chuyen sang AUTO");
        } else if (message == "MANUAL") {
            currentMode = MODE_MANUAL;
            Serial.println("Remote: Chuyen sang MANUAL");
        } else if (message == "SLEEP") {
            sleepMode = !sleepMode;
            if(!sleepMode) { 
                lastChangeTime = millis();
                updateTimeLeft();
                updateLEDs();
            }
        }
    }
    // 3. Vehicle Count data from RPi
    else if (String(topic) == topic_sub_vehicle_count) {
        Serial.println("Nhận dữ liệu vehicle count từ RPi");
        DynamicJsonDocument doc(1024);
        DeserializationError error = deserializeJson(doc, message);
        
        if (error) {
            Serial.print("deserializeJson() failed: ");
            Serial.println(error.c_str());
            return;
        }
        
        for (int i = 0; i < 4; i++) {
            String reg = "region_" + String(i + 1);
            JsonObject obj = doc[reg];
            regionCounts[i][0] = obj["motorbike"] | 0;
            regionCounts[i][1] = obj["car"] | 0;
            regionCounts[i][2] = obj["bus"] | 0;
            regionCounts[i][3] = obj["truck"] | 0;
        }
        
        int totalVehicles = 0;
        for (int i = 0; i < 4; i++) {
            for (int j = 0; j < 4; j++) {
                totalVehicles += regionCounts[i][j];
            }
        }
        
        if (totalVehicles > 50) {
            densityLevel = "HIGH";
        } else if (totalVehicles > 20) {
            densityLevel = "MEDIUM";
        } else {
            densityLevel = "LOW";
        }
        
        if (currentMode == MODE_AUTO) {
            calculateGreenTimes();
        }
        
        publishTrafficStatusToFirebase();
    }
}

bool mqttSubscribeAll() {
    bool subCmd = client.subscribe(topic_sub_cmd);
    bool subManual = client.subscribe(topic_sub_manual);
    bool subVehicle = client.subscribe(topic_sub_vehicle_count);
    Serial.print("MQTT subscribe cmd=");
    Serial.print(subCmd ? "OK" : "FAIL");
    Serial.print(" manual=");
    Serial.print(subManual ? "OK" : "FAIL");
    Serial.print(" vehicle_count=");
    Serial.println(subVehicle ? "OK" : "FAIL");
    return subCmd && subManual && subVehicle;
}

void ensureMqttConnected() {
    if (client.connected()) {
        return;
    }
    if (millis() - lastMqttAttempt < MQTT_RETRY_MS) {
        return;
    }
    lastMqttAttempt = millis();

    Serial.print("Dang ket noi MQTT ");
    Serial.print(mqtt_server);
    Serial.print(":");
    Serial.print(MQTT_BROKER_PORT);
    Serial.print(" ... ");
    if (client.connect(MQTT_CLIENT_ID)) {
        Serial.println("Da ket noi!");
        mqttSubscribeAll();
    } else {
        Serial.print("Loi, rc=");
        Serial.print(client.state());
        Serial.println(" (thu lai sau 5s)");
    }
}

void publishTrafficStatusToFirebase() {
    String currentStateStr;
    switch(currentState) {
        case STATE_1_GREEN:   currentStateStr = "1_GREEN"; break;
        case STATE_1_YELLOW:  currentStateStr = "1_YELLOW"; break;
        case STATE_2_GREEN:   currentStateStr = "2_GREEN"; break;
        case STATE_2_YELLOW:  currentStateStr = "2_YELLOW"; break;
    }
    
    FirebaseJson json;
    
    if (sleepMode) {
        json.set("esp32_mode", "SLEEP");
        json.set("esp32_state", "ALL_OFF");
        json.set("time_left_1", 0);
        json.set("time_left_2", 0);
    } else {
        json.set("esp32_mode", currentMode == MODE_AUTO ? "AUTO" : "MANUAL");
        json.set("esp32_state", currentStateStr.c_str());
        json.set("time_left_1", currentTimeLeft1);
        json.set("time_left_2", currentTimeLeft2);
        json.set("green_time_1", greenTime1); 
        json.set("green_time_2", greenTime2); 
        json.set("latest_status", densityLevel.c_str());
    }
    
    FirebaseJson regionObject;
    int totalVehiclesAll = 0;
    
    for (int i = 0; i < 4; i++) {
        int regionTotal = 0;
        for (int j = 0; j < 4; j++) {
            regionTotal += regionCounts[i][j];
        }
        
        String regionKey = "Region_" + String(i + 1); 
        
        FirebaseJson regionJson;
        regionJson.set("motorbike", regionCounts[i][0]);
        regionJson.set("car", regionCounts[i][1]);
        regionJson.set("bus", regionCounts[i][2]);
        regionJson.set("truck", regionCounts[i][3]);
        regionJson.set("total_in_region", regionTotal);
        
        regionObject.set(regionKey.c_str(), regionJson); 
        totalVehiclesAll += regionTotal;
    }
    
    json.set("region_counts", regionObject); 
    json.set("total_vehicles_all_time", totalVehiclesAll);
    json.set("timestamp", String(time(nullptr)));
    
    String serializedStr;
    json.toString(serializedStr, true);
    String* pStr = new String(serializedStr);
    
    if (firebaseQueue != NULL) {
        if (xQueueSend(firebaseQueue, &pStr, 0) != pdPASS) {
            Serial.println("Firebase Queue full! Dropping update.");
            delete pStr;
        }
    } else {
        delete pStr;
    }
}

void publishLightState(TrafficState state) {
    if (!client.connected()) return;
    
    String stateStr;
    switch(state) {
        case STATE_1_GREEN:   stateStr = "1_GREEN"; break;
        case STATE_1_YELLOW:  stateStr = "1_YELLOW"; break;
        case STATE_2_GREEN:   stateStr = "2_GREEN"; break;
        case STATE_2_YELLOW:  stateStr = "2_YELLOW"; break;
    }
    
    client.publish(MQTT_TOPIC_LIGHT_STATE, stateStr.c_str());
}
