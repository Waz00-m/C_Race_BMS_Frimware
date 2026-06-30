#ifndef ESP32_PIN_CONFIG_H
#define ESP32_PIN_CONFIG_H

#include "bms_adc_hal.h"

static const int BMS_ESP32_ADC_PINS[BMS_ADC_CHANNEL_COUNT] = {
    36,
    39,
    34,
    35,
    32,
    33,
    25,
    26,
    27,
    14,
    13,
};

#endif
