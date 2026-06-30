#ifndef BMS_ADC_HAL_H
#define BMS_ADC_HAL_H

#include <stdint.h>

#include "bms_status.h"
#include "bms_types.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    BMS_ADC_CHANNEL_CELL_1 = 0,
    BMS_ADC_CHANNEL_CELL_2,
    BMS_ADC_CHANNEL_CELL_3,
    BMS_ADC_CHANNEL_CELL_4,
    BMS_ADC_CHANNEL_CELL_5,
    BMS_ADC_CHANNEL_CELL_6,
    BMS_ADC_CHANNEL_CURRENT,
    BMS_ADC_CHANNEL_TEMP_1,
    BMS_ADC_CHANNEL_TEMP_2,
    BMS_ADC_CHANNEL_TEMP_3,
    BMS_ADC_CHANNEL_TEMP_4,
    BMS_ADC_CHANNEL_COUNT
} bms_adc_channel_t;

bms_status_t BMS_HAL_ADC_Init(void);
bms_status_t BMS_HAL_ADC_ReadRaw(bms_adc_channel_t channel, uint16_t *raw);
bms_status_t BMS_HAL_ADC_ReadMilliVolts(bms_adc_channel_t channel, uint16_t *mV);

#ifdef __cplusplus
}
#endif

#endif
