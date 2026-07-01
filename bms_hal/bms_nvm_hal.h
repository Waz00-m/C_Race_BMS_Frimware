#ifndef BMS_NVM_HAL_H
#define BMS_NVM_HAL_H

#include <stdint.h>

#include "bms_status.h"

#ifdef __cplusplus
extern "C" {
#endif

bms_status_t BMS_HAL_NVM_Init(void);
bms_status_t BMS_HAL_NVM_ReadConfig(void *data, uint16_t length);
bms_status_t BMS_HAL_NVM_WriteConfig(const void *data, uint16_t length);
bms_status_t BMS_HAL_NVM_EraseConfig(void);

#ifdef __cplusplus
}
#endif

#endif
