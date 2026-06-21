#ifndef GLOBALS_H
#define GLOBALS_H

#include <Arduino.h>
#include <TM1637Display.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <FirebaseESP32.h>
#include <ArduinoJson.h>
#include "mqtt_config.h"
#include "credentials.h"

// Cấu hình Firebase
#define FIREBASE_HOST FB_HOST
#define FIREBASE_AUTH FB_AUTH 


// Định nghĩa chân phần cứng
#define R_1 23
#define Y_1 22
#define G_1 21
#define R_2 19
#define Y_2 18
#define G_2 5
#define R_3 25
#define Y_3 14
#define G_3 12
#define R_4 13
#define Y_4 15
#define G_4 4
#define TM1637_CLK 17
#define TM1637_DIO 16
#define SW0 32
#define SW1 33
#define SW2 27

// Định nghĩa enums trạng thái
enum TrafficMode { MODE_AUTO, MODE_MANUAL };
enum TrafficState { STATE_1_GREEN, STATE_1_YELLOW, STATE_2_GREEN, STATE_2_YELLOW };

// Khai báo biến toàn cục (extern)
extern const char* ssid;
extern const char* password;
extern const char* mqtt_server;
extern const char* topic_sub_cmd;
extern const char* topic_sub_manual;
extern const char* topic_sub_vehicle_count;

#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>

extern WiFiClient espClient;
extern PubSubClient client;
extern unsigned long lastMqttAttempt;
extern const unsigned long MQTT_RETRY_MS;

extern FirebaseData fbdo;
extern FirebaseConfig firebaseConfig;
extern FirebaseAuth firebaseAuth;
extern QueueHandle_t firebaseQueue;

extern TM1637Display display;

extern TrafficMode currentMode;
extern TrafficState currentState;
extern bool sleepMode;

extern int greenTime1; 
extern int greenTime2; 
extern int yellowTime;
extern unsigned long lastChangeTime;
extern int currentTimeLeft1;
extern int currentTimeLeft2;

extern unsigned long debounceDelay;
extern unsigned long lastMqttPub;
extern int regionCounts[4][4]; 
extern String densityLevel;

extern const int MIN_GREEN;
extern const int MAX_GREEN;

#endif
