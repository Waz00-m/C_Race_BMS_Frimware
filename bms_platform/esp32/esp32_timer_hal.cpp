#include "bms_timer_hal.h"

#include <Arduino.h>
#include <esp_arduino_version.h>

static hw_timer_t *g_base_tick_timer = NULL;
static volatile uint32_t g_timer_tick_ms = 0UL;
static bms_hal_timer_callback_t g_timer_callback = NULL;
static void *g_timer_callback_arg = NULL;

static void IRAM_ATTR BMS_ESP32_TimerISR(void)
{
    g_timer_tick_ms++;

    if (g_timer_callback != NULL) {
        g_timer_callback(g_timer_callback_arg);
    }
}

bms_status_t BMS_HAL_Timer_Init(void)
{
    g_timer_tick_ms = 0UL;
    return BMS_STATUS_OK;
}

bms_status_t BMS_HAL_Timer_StartBaseTick(
    uint32_t period_us,
    bms_hal_timer_callback_t callback,
    void *user_arg)
{
    if ((period_us == 0UL) || (callback == NULL)) {
        return BMS_STATUS_INVALID_ARGUMENT;
    }

    if (g_base_tick_timer != NULL) {
        (void)BMS_HAL_Timer_StopBaseTick();
    }

    g_timer_callback = callback;
    g_timer_callback_arg = user_arg;

#if ESP_ARDUINO_VERSION_MAJOR >= 3
    g_base_tick_timer = timerBegin(1000000UL);
    if (g_base_tick_timer == NULL) {
        return BMS_STATUS_HAL_ERROR;
    }

    timerAttachInterrupt(g_base_tick_timer, &BMS_ESP32_TimerISR);
    timerAlarm(g_base_tick_timer, period_us, true, 0U);
#else
    g_base_tick_timer = timerBegin(0U, 80U, true);
    if (g_base_tick_timer == NULL) {
        return BMS_STATUS_HAL_ERROR;
    }

    timerAttachInterrupt(g_base_tick_timer, &BMS_ESP32_TimerISR, true);
    timerAlarmWrite(g_base_tick_timer, period_us, true);
    timerAlarmEnable(g_base_tick_timer);
#endif

    return BMS_STATUS_OK;
}

bms_status_t BMS_HAL_Timer_StopBaseTick(void)
{
    if (g_base_tick_timer != NULL) {
        timerEnd(g_base_tick_timer);
        g_base_tick_timer = NULL;
    }

    g_timer_callback = NULL;
    g_timer_callback_arg = NULL;

    return BMS_STATUS_OK;
}

uint32_t BMS_HAL_Timer_GetTickMs(void)
{
    return g_timer_tick_ms;
}
