// Dong bo IP voi shared/configs/settings.yaml -> mqtt.broker
#ifndef MQTT_CONFIG_H
#define MQTT_CONFIG_H

#define MQTT_BROKER_HOST "172.20.10.5"
#define MQTT_BROKER_PORT 1883
#define MQTT_CLIENT_ID "ESP32_TrafficLight_Client"
#define MQTT_BUFFER_SIZE 1024

#define MQTT_TOPIC_GREEN_TIME_CMD "he_thong_giam_sat_luu_luong/green_time_cmd"
#define MQTT_TOPIC_CONTROL "he_thong_giam_sat_luu_luong/control"
#define MQTT_TOPIC_VEHICLE_COUNT "he_thong_giam_sat_luu_luong/vehicle_count"
#define MQTT_TOPIC_LIGHT_STATE "he_thong_giam_sat_luu_luong/light_state"

#endif
