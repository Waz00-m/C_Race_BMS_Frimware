#ifndef BMS_I2C_HAL_H
#define BMS_I2C_HAL_H

#include <stdint.h>

#include "bms_status.h"

#ifdef __cplusplus
extern "C" {
#endif

bms_status_t BMS_HAL_I2C_Init(void);
bms_status_t BMS_HAL_I2C_WriteRegister16(
    uint8_t device_address,
    uint8_t register_address,
    uint16_t value);
bms_status_t BMS_HAL_I2C_ReadRegister16(
    uint8_t device_address,
    uint8_t register_address,
    uint16_t *value);

#ifdef __cplusplus
}
#endif

#endif
