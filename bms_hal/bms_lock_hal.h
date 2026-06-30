#ifndef BMS_LOCK_HAL_H
#define BMS_LOCK_HAL_H

#include "bms_status.h"

#ifdef __cplusplus
extern "C" {
#endif

bms_status_t BMS_HAL_Lock_Init(void);
void BMS_HAL_Lock_EnterCritical(void);
void BMS_HAL_Lock_ExitCritical(void);

#ifdef __cplusplus
}
#endif

#endif
