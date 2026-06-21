#include "globals.h"

// WiFi
const char* ssid = WIFI_SSID;
const char* password = WIFI_PASSWORD;

// MQTT Topics
const char* mqtt_server = MQTT_BROKER_HOST;
const char* topic_sub_cmd = MQTT_TOPIC_GREEN_TIME_CMD;
const char* topic_sub_manual = MQTT_TOPIC_CONTROL;
const char* topic_sub_vehicle_count = MQTT_TOPIC_VEHICLE_COUNT;

// Clients
WiFiClient espClient;
PubSubClient client(espClient);
unsigned long lastMqttAttempt = 0;
const unsigned long MQTT_RETRY_MS = 5000;

// Firebase
FirebaseData fbdo;
FirebaseConfig firebaseConfig;
FirebaseAuth firebaseAuth;
QueueHandle_t firebaseQueue = NULL;

// TM1637 Display
TM1637Display display(TM1637_CLK, TM1637_DIO);

// States
TrafficMode currentMode = MODE_AUTO;
TrafficState currentState = STATE_1_GREEN;
bool sleepMode = false;

// Timings
int greenTime1 = 10; 
int greenTime2 = 10; 
int yellowTime = 3;
unsigned long lastChangeTime = 0;
int currentTimeLeft1 = 0;
int currentTimeLeft2 = 0;

// Debounce & Firebase timer
unsigned long debounceDelay = 50;
unsigned long lastMqttPub = 0;

// Vehicle counting
int regionCounts[4][4] = {{0}}; 
String densityLevel = "LOW";

// Limits
const int MIN_GREEN = 10;
const int MAX_GREEN = 30;
