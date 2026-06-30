#include "bms_lock_hal.h"

#include <Arduino.h>

static portMUX_TYPE g_bms_lock_mux = portMUX_INITIALIZER_UNLOCKED;

bms_status_t BMS_HAL_Lock_Init(void)
{
    return BMS_STATUS_OK;
}

void BMS_HAL_Lock_EnterCritical(void)
{
    portENTER_CRITICAL(&g_bms_lock_mux);
}

void BMS_HAL_Lock_ExitCritical(void)
{
    portEXIT_CRITICAL(&g_bms_lock_mux);
}
