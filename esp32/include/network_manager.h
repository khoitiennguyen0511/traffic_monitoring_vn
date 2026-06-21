#ifndef NETWORK_MANAGER_H
#define NETWORK_MANAGER_H

#include "globals.h"

void setup_wifi();
void callback(char* topic, byte* payload, unsigned int length);
bool mqttSubscribeAll();
void ensureMqttConnected();
void publishTrafficStatusToFirebase();
void publishLightState(TrafficState state);

#endif
