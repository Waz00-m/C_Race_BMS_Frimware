#include "bms_adc_hal.h"

#include <Arduino.h>

#include "esp32_pin_config.h"

static bool BMS_ESP32_ADC_IsValidChannel(bms_adc_channel_t channel)
{
    return ((uint8_t)channel < (uint8_t)BMS_ADC_CHANNEL_COUNT);
}

bms_status_t BMS_HAL_ADC_Init(void)
{
    analogReadResolution(12);
    analogSetWidth(12);

    for (uint8_t i = 0U; i < (uint8_t)BMS_ADC_CHANNEL_COUNT; ++i) {
        analogSetPinAttenuation(BMS_ESP32_ADC_PINS[i], ADC_11db);
    }

    return BMS_STATUS_OK;
}

bms_status_t BMS_HAL_ADC_ReadRaw(bms_adc_channel_t channel, uint16_t *raw)
{
    if ((raw == NULL) || !BMS_ESP32_ADC_IsValidChannel(channel)) {
        return BMS_STATUS_INVALID_ARGUMENT;
    }

    const int pin = BMS_ESP32_ADC_PINS[(uint8_t)channel];
    const int value = analogRead(pin);

    if (value < 0) {
        return BMS_STATUS_HAL_ERROR;
    }

    *raw = (uint16_t)value;
    return BMS_STATUS_OK;
}

bms_status_t BMS_HAL_ADC_ReadMilliVolts(bms_adc_channel_t channel, uint16_t *mV)
{
    if ((mV == NULL) || !BMS_ESP32_ADC_IsValidChannel(channel)) {
        return BMS_STATUS_INVALID_ARGUMENT;
    }

    const int pin = BMS_ESP32_ADC_PINS[(uint8_t)channel];
    const uint32_t value_mV = analogReadMilliVolts(pin);

    if (value_mV > UINT16_MAX) {
        return BMS_STATUS_HAL_ERROR;
    }

    *mV = (uint16_t)value_mV;
    return BMS_STATUS_OK;
}
