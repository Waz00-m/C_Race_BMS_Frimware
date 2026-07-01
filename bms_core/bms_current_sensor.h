#ifndef BMS_CURRENT_SENSOR_H
#define BMS_CURRENT_SENSOR_H

#include <stdbool.h>
#include <stdint.h>

#include "bms_status.h"

#ifdef __cplusplus
extern "C" {
#endif

bms_status_t BMS_CurrentSensor_Init(void);
bms_status_t BMS_CurrentSensor_ConvertAdcMilliVolts(
    uint16_t adc_mV,
    int32_t *current_mA,
    bool *current_valid);
bms_status_t BMS_CurrentSensor_ReadDigitalMilliAmps(
    int32_t *current_mA,
    bool *current_valid);
bool BMS_CurrentSensor_UsesAdc(void);

#ifdef __cplusplus
}
#endif

#endif
