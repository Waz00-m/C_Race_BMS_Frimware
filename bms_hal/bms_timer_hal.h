#ifndef BMS_TIMER_HAL_H
#define BMS_TIMER_HAL_H

#include <stdint.h>

#include "bms_status.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef void (*bms_hal_timer_callback_t)(void *user_arg);

bms_status_t BMS_HAL_Timer_Init(void);
bms_status_t BMS_HAL_Timer_StartBaseTick(
    uint32_t period_us,
    bms_hal_timer_callback_t callback,
    void *user_arg);
bms_status_t BMS_HAL_Timer_StopBaseTick(void);
uint32_t BMS_HAL_Timer_GetTickMs(void);

#ifdef __cplusplus
}
#endif

#endif
