#include "bms_uart_hal.h"

#include <Arduino.h>

#ifndef BMS_ESP32_UART_BAUD_RATE
#define BMS_ESP32_UART_BAUD_RATE 115200UL
#endif

bms_status_t BMS_HAL_UART_Init(void)
{
    Serial.begin(BMS_ESP32_UART_BAUD_RATE);
    return BMS_STATUS_OK;
}

bms_status_t BMS_HAL_UART_Send(const char *text)
{
    if (text == NULL) {
        return BMS_STATUS_INVALID_ARGUMENT;
    }

    Serial.print(text);
    return BMS_STATUS_OK;
}

bms_status_t BMS_HAL_UART_ReadByte(uint8_t *byte)
{
    if (byte == NULL) {
        return BMS_STATUS_INVALID_ARGUMENT;
    }

    if (Serial.available() <= 0) {
        return BMS_STATUS_NO_DATA;
    }

    const int value = Serial.read();
    if (value < 0) {
        return BMS_STATUS_NO_DATA;
    }

    *byte = (uint8_t)value;
    return BMS_STATUS_OK;
}
