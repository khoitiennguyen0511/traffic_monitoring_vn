#include "traffic_logic.h"
#include "hardware_control.h"
#include "network_manager.h"

void checkSleepMode() {
    static bool lastSW2State = HIGH;
    bool currentSW2State = digitalRead(SW2);
    
    // Chỉ kích hoạt khi có sự chuyển đổi trạng thái từ HIGH sang LOW (nhấn xuống)
    if (currentSW2State == LOW && lastSW2State == HIGH) {
        delay(debounceDelay); // Chống dội phím
        if (digitalRead(SW2) == LOW) {
            sleepMode = !sleepMode;
            Serial.println(sleepMode ? "Vào chế độ ngủ" : "Thoát chế độ ngủ");
            
            if (!sleepMode) {
                lastChangeTime = millis();
                updateTimeLeft();
                updateLEDs();
            }
        }
    }
    lastSW2State = currentSW2State;
}

void checkButtons() {
    static bool lastSW0State = HIGH;
    static bool lastSW1State = HIGH;
    
    bool currentSW0State = digitalRead(SW0);
    bool currentSW1State = digitalRead(SW1);
    
    // SW0: Auto/Manual Mode Switch
    if (currentSW0State == LOW && lastSW0State == HIGH) {
        delay(debounceDelay);
        if (digitalRead(SW0) == LOW) {
            currentMode = (currentMode == MODE_AUTO) ? MODE_MANUAL : MODE_AUTO;
            Serial.println(currentMode == MODE_AUTO ? "Chế độ TỰ ĐỘNG" : "Chế độ THỦ CÔNG");
            
            lastChangeTime = millis();
            updateTimeLeft();
        }
    }
    
    // SW1: Manual state switch (Only in MANUAL mode)
    if (currentMode == MODE_MANUAL && currentSW1State == LOW && lastSW1State == HIGH) {
        delay(debounceDelay);
        if (digitalRead(SW1) == LOW) {
            switch(currentState) {
                case STATE_1_GREEN:   currentState = STATE_1_YELLOW; break;
                case STATE_1_YELLOW:  currentState = STATE_2_GREEN;  break;
                case STATE_2_GREEN:   currentState = STATE_2_YELLOW; break;
                case STATE_2_YELLOW:  currentState = STATE_1_GREEN;  break;
            }
            updateLEDs();
            lastChangeTime = millis();
            updateTimeLeft();
            
            Serial.println("Chuyển trạng thái thủ công");
        }
    }
    
    lastSW0State = currentSW0State;
    lastSW1State = currentSW1State;
}

void autoMode() {
    unsigned long currentTime = millis();
    unsigned long elapsedTime = (currentTime - lastChangeTime) / 1000;
    bool stateChanged = false;
    
    // 1. Kiểm tra điều kiện chuyển trạng thái trước
    switch(currentState) {
        case STATE_1_GREEN:
            if (elapsedTime >= greenTime1) {
                currentState = STATE_1_YELLOW;
                stateChanged = true;
            }
            break;
            
        case STATE_1_YELLOW:
            if (elapsedTime >= yellowTime) {
                currentState = STATE_2_GREEN;
                stateChanged = true;
            }
            break;
            
        case STATE_2_GREEN:
            if (elapsedTime >= greenTime2) {
                currentState = STATE_2_YELLOW;
                stateChanged = true;
            }
            break;
            
        case STATE_2_YELLOW:
            if (elapsedTime >= yellowTime) {
                currentState = STATE_1_GREEN;
                stateChanged = true;
            }
            break;
    }
    
    // Nếu chuyển trạng thái, cập nhật LED, reset mốc thời gian và tính lại elapsedTime = 0
    if (stateChanged) {
        updateLEDs();
        lastChangeTime = currentTime;
        elapsedTime = 0;
    }
    
    // 2. Tính toán thời gian đếm ngược chính xác dựa trên trạng thái (mới)
    switch(currentState) {
        case STATE_1_GREEN:
            currentTimeLeft1 = greenTime1 - elapsedTime;
            currentTimeLeft2 = greenTime1 + yellowTime - elapsedTime;
            break;
            
        case STATE_1_YELLOW:
            currentTimeLeft1 = yellowTime - elapsedTime;
            currentTimeLeft2 = yellowTime - elapsedTime;
            break;
            
        case STATE_2_GREEN:
            currentTimeLeft1 = greenTime2 + yellowTime - elapsedTime;
            currentTimeLeft2 = greenTime2 - elapsedTime;
            break;
            
        case STATE_2_YELLOW:
            currentTimeLeft1 = yellowTime - elapsedTime;
            currentTimeLeft2 = yellowTime - elapsedTime;
            break;
    }
    
    if (currentTimeLeft1 < 0) currentTimeLeft1 = 0;
    if (currentTimeLeft2 < 0) currentTimeLeft2 = 0;
}

// Adaptive Green Time calculation based on vehicle count
void calculateGreenTimes() {
    // Lane 1 traffic = Region 1 + Region 3
    int countLane1 = 0;
    for (int j = 0; j < 4; j++) {
        countLane1 += regionCounts[0][j] + regionCounts[2][j];
    }
    
    // Lane 2 traffic = Region 2 + Region 4
    int countLane2 = 0;
    for (int j = 0; j < 4; j++) {
        countLane2 += regionCounts[1][j] + regionCounts[3][j];
    }
    
    int totalCounts = countLane1 + countLane2;
    
    if (totalCounts == 0) {
        greenTime1 = MIN_GREEN;
        greenTime2 = MIN_GREEN;
    } 
    else {
        float prop1 = (float)countLane1 / totalCounts;
        greenTime1 = MIN_GREEN + (int)((MAX_GREEN - MIN_GREEN) * prop1);
        greenTime2 = MIN_GREEN + (int)((MAX_GREEN - MIN_GREEN) * (1.0 - prop1));
    }
    
    // Apply bounds
    if (greenTime1 < MIN_GREEN) greenTime1 = MIN_GREEN;
    if (greenTime1 > MAX_GREEN) greenTime1 = MAX_GREEN;
    
    if (greenTime2 < MIN_GREEN) greenTime2 = MIN_GREEN;
    if (greenTime2 > MAX_GREEN) greenTime2 = MAX_GREEN;
    
    Serial.println("--- ADAPTIVE GREEN TIME CALCULATION ---");
    Serial.print("Lane 1 vehicles: "); Serial.println(countLane1);
    Serial.print("Lane 2 vehicles: "); Serial.println(countLane2);
    Serial.print("Result - Green 1: "); Serial.print(greenTime1); Serial.print("s | Green 2: "); Serial.print(greenTime2); Serial.println("s");
    Serial.println("---------------------------------------");
}
