#include "hardware_control.h"

void enterSleepMode() {
    digitalWrite(R_1, LOW); digitalWrite(Y_1, LOW); digitalWrite(G_1, LOW);
    digitalWrite(R_2, LOW); digitalWrite(Y_2, LOW); digitalWrite(G_2, LOW);
    digitalWrite(R_3, LOW); digitalWrite(Y_3, LOW); digitalWrite(G_3, LOW);
    digitalWrite(R_4, LOW); digitalWrite(Y_4, LOW); digitalWrite(G_4, LOW);
    
    uint8_t sleepData[] = {
        SEG_A | SEG_F | SEG_G | SEG_C | SEG_D, 
        SEG_D | SEG_E | SEG_F,                 
        0x00,                                  
        0x00                                   
    };
    
    display.setSegments(sleepData);
    delay(100);
}

void updateLEDs() {
    digitalWrite(R_1, LOW); digitalWrite(Y_1, LOW); digitalWrite(G_1, LOW);
    digitalWrite(R_2, LOW); digitalWrite(Y_2, LOW); digitalWrite(G_2, LOW);
    digitalWrite(R_3, LOW); digitalWrite(Y_3, LOW); digitalWrite(G_3, LOW);
    digitalWrite(R_4, LOW); digitalWrite(Y_4, LOW); digitalWrite(G_4, LOW);
    
    switch(currentState) {
        case STATE_1_GREEN: 
            digitalWrite(G_1, HIGH); 
            digitalWrite(G_3, HIGH); 
            digitalWrite(R_2, HIGH); 
            digitalWrite(R_4, HIGH); 
            break;
        case STATE_1_YELLOW: 
            digitalWrite(Y_1, HIGH); 
            digitalWrite(Y_3, HIGH); 
            digitalWrite(R_2, HIGH); 
            digitalWrite(R_4, HIGH); 
            break;
        case STATE_2_GREEN: 
            digitalWrite(R_1, HIGH); 
            digitalWrite(R_3, HIGH); 
            digitalWrite(G_2, HIGH); 
            digitalWrite(G_4, HIGH); 
            break;
        case STATE_2_YELLOW: 
            digitalWrite(R_1, HIGH); 
            digitalWrite(R_3, HIGH); 
            digitalWrite(Y_2, HIGH); 
            digitalWrite(Y_4, HIGH); 
            break;
    }
}

void updateTimeLeft() {
    switch(currentState) {
        case STATE_1_GREEN: 
            currentTimeLeft1 = greenTime1; 
            currentTimeLeft2 = greenTime1 + yellowTime; 
            break;
        case STATE_1_YELLOW: 
            currentTimeLeft1 = yellowTime; 
            currentTimeLeft2 = yellowTime; 
            break;
        case STATE_2_GREEN: 
            currentTimeLeft1 = greenTime2 + yellowTime; 
            currentTimeLeft2 = greenTime2; 
            break;
        case STATE_2_YELLOW: 
            currentTimeLeft1 = yellowTime; 
            currentTimeLeft2 = yellowTime; 
            break;
    }
}

void displayTime() {
    if (sleepMode) {
        return;
    } 
    
    if (currentMode == MODE_MANUAL) {
        uint8_t manualData[] = { SEG_G, SEG_G, SEG_G, SEG_G };
        display.setSegments(manualData);
    } 
    else {
        int displayNumber = (currentTimeLeft1 * 100) + currentTimeLeft2;
        display.showNumberDecEx(displayNumber, 0b1110000, true);
    }
}
