#include "bms_scheduler.h"

#include <string.h>

#include "bms_lock_hal.h"

static const bms_scheduler_profile_t k_active_profile = {
    {
        5U,
        20U,
        250U,
        100U,
        20U,
        100U,
        10U,
        500U,
    }
};

static const bms_scheduler_profile_t k_idle_profile = {
    {
        500U,
        1000U,
        2000U,
        1000U,
        500U,
        2000U,
        20U,
        1000U,
    }
};

static const bms_scheduler_profile_t k_sleep_profile = {
    {
        0U,
        0U,
        0U,
        0U,
        0U,
        0U,
        0U,
        0U,
    }
};

static void BMS_Scheduler_ResetRuntimeCounters(bms_scheduler_t *scheduler)
{
    scheduler->tick_ms = 0UL;
    scheduler->due_flags = 0UL;

    for (uint8_t task = 0U; task < BMS_SCHEDULER_TASK_COUNT; ++task) {
        scheduler->elapsed_ms[task] = 0U;
        scheduler->due_count[task] = 0U;
        scheduler->total_count[task] = 0UL;
    }
}

const bms_scheduler_profile_t *BMS_Scheduler_GetProfile(
    bms_scheduler_profile_id_t profile_id)
{
    switch (profile_id) {
    case BMS_SCHEDULER_PROFILE_ACTIVE:
        return &k_active_profile;
    case BMS_SCHEDULER_PROFILE_IDLE:
        return &k_idle_profile;
    case BMS_SCHEDULER_PROFILE_SLEEP:
        return &k_sleep_profile;
    default:
        return NULL;
    }
}

uint32_t BMS_Scheduler_TaskMask(bms_scheduler_task_id_t task_id)
{
    if (task_id >= BMS_SCHEDULER_TASK_COUNT) {
        return 0UL;
    }

    return (1UL << (uint8_t)task_id);
}

const char *BMS_SchedulerTask_ToString(bms_scheduler_task_id_t task_id)
{
    switch (task_id) {
    case BMS_SCHEDULER_TASK_CURRENT:
        return "CURRENT";
    case BMS_SCHEDULER_TASK_VOLTAGE:
        return "VOLTAGE";
    case BMS_SCHEDULER_TASK_TEMPERATURE:
        return "TEMPERATURE";
    case BMS_SCHEDULER_TASK_ESTIMATION:
        return "ESTIMATION";
    case BMS_SCHEDULER_TASK_FAULT:
        return "FAULT";
    case BMS_SCHEDULER_TASK_TELEMETRY:
        return "TELEMETRY";
    case BMS_SCHEDULER_TASK_DIAGNOSTIC:
        return "DIAGNOSTIC";
    case BMS_SCHEDULER_TASK_SLEEP_POLICY:
        return "SLEEP_POLICY";
    default:
        return "UNKNOWN_TASK";
    }
}

bms_status_t BMS_Scheduler_Init(bms_scheduler_t *scheduler)
{
    if (scheduler == NULL) {
        return BMS_STATUS_INVALID_ARGUMENT;
    }

    memset(scheduler, 0, sizeof(*scheduler));
    scheduler->status = BMS_SCHEDULER_STOPPED;
    scheduler->profile_id = BMS_SCHEDULER_PROFILE_ACTIVE;
    scheduler->profile = k_active_profile;
    scheduler->initialized = true;

    return BMS_STATUS_OK;
}

bms_status_t BMS_Scheduler_LoadProfile(
    bms_scheduler_t *scheduler,
    bms_scheduler_profile_id_t profile_id)
{
    if ((scheduler == NULL) || !scheduler->initialized) {
        return BMS_STATUS_NOT_INITIALIZED;
    }

    const bms_scheduler_profile_t *profile =
        BMS_Scheduler_GetProfile(profile_id);
    if (profile == NULL) {
        return BMS_STATUS_INVALID_ARGUMENT;
    }

    BMS_HAL_Lock_EnterCritical();
    scheduler->profile = *profile;
    scheduler->profile_id = profile_id;
    BMS_Scheduler_ResetRuntimeCounters(scheduler);
    BMS_HAL_Lock_ExitCritical();

    return BMS_STATUS_OK;
}

bms_status_t BMS_Scheduler_Start(bms_scheduler_t *scheduler)
{
    if ((scheduler == NULL) || !scheduler->initialized) {
        return BMS_STATUS_NOT_INITIALIZED;
    }

    BMS_HAL_Lock_EnterCritical();
    scheduler->running = true;
    scheduler->status = BMS_SCHEDULER_ACTIVE;
    BMS_HAL_Lock_ExitCritical();

    return BMS_STATUS_OK;
}

bms_status_t BMS_Scheduler_Stop(bms_scheduler_t *scheduler)
{
    if ((scheduler == NULL) || !scheduler->initialized) {
        return BMS_STATUS_NOT_INITIALIZED;
    }

    BMS_HAL_Lock_EnterCritical();
    scheduler->running = false;
    scheduler->status = BMS_SCHEDULER_STOPPED;
    BMS_HAL_Lock_ExitCritical();

    return BMS_STATUS_OK;
}

void BMS_Scheduler_OnBaseTickIsr(void *scheduler_arg)
{
    bms_scheduler_t *scheduler = (bms_scheduler_t *)scheduler_arg;

    if ((scheduler == NULL) ||
        !scheduler->initialized ||
        !scheduler->running) {
        return;
    }

    scheduler->tick_ms++;

    for (uint8_t task = 0U; task < BMS_SCHEDULER_TASK_COUNT; ++task) {
        const uint16_t period_ms = scheduler->profile.period_ms[task];
        if (period_ms == 0U) {
            continue;
        }

        scheduler->elapsed_ms[task]++;
        if (scheduler->elapsed_ms[task] >= period_ms) {
            scheduler->elapsed_ms[task] = 0U;
            scheduler->due_flags |= BMS_Scheduler_TaskMask(
                (bms_scheduler_task_id_t)task);

            if (scheduler->due_count[task] < UINT16_MAX) {
                scheduler->due_count[task]++;
            }

            scheduler->total_count[task]++;
        }
    }
}

bms_status_t BMS_Scheduler_ConsumeDueFlags(
    bms_scheduler_t *scheduler,
    bms_scheduler_due_t *due)
{
    if ((scheduler == NULL) || (due == NULL)) {
        return BMS_STATUS_INVALID_ARGUMENT;
    }

    if (!scheduler->initialized) {
        return BMS_STATUS_NOT_INITIALIZED;
    }

    memset(due, 0, sizeof(*due));

    BMS_HAL_Lock_EnterCritical();
    due->tick_ms = scheduler->tick_ms;
    due->due_flags = scheduler->due_flags;

    for (uint8_t task = 0U; task < BMS_SCHEDULER_TASK_COUNT; ++task) {
        due->due_count[task] = scheduler->due_count[task];
        due->total_count[task] = scheduler->total_count[task];
        scheduler->due_count[task] = 0U;
    }

    scheduler->due_flags = 0UL;
    BMS_HAL_Lock_ExitCritical();

    return BMS_STATUS_OK;
}
