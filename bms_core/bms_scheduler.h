#ifndef BMS_SCHEDULER_H
#define BMS_SCHEDULER_H

#include "bms_status.h"
#include "bms_types.h"

#ifdef __cplusplus
extern "C" {
#endif

#define BMS_SCHEDULER_BASE_TICK_US (1000UL)
#define BMS_SCHEDULER_TELEMETRY_HEARTBEAT_DIVIDER (5U)

typedef enum {
    BMS_SCHEDULER_TASK_CURRENT = 0,
    BMS_SCHEDULER_TASK_VOLTAGE,
    BMS_SCHEDULER_TASK_TEMPERATURE,
    BMS_SCHEDULER_TASK_ESTIMATION,
    BMS_SCHEDULER_TASK_FAULT,
    BMS_SCHEDULER_TASK_TELEMETRY,
    BMS_SCHEDULER_TASK_DIAGNOSTIC,
    BMS_SCHEDULER_TASK_SLEEP_POLICY,
    BMS_SCHEDULER_TASK_COUNT
} bms_scheduler_task_id_t;

typedef enum {
    BMS_SCHEDULER_PROFILE_ACTIVE = 0,
    BMS_SCHEDULER_PROFILE_IDLE,
    BMS_SCHEDULER_PROFILE_SLEEP
} bms_scheduler_profile_id_t;

typedef struct {
    uint16_t period_ms[BMS_SCHEDULER_TASK_COUNT];
} bms_scheduler_profile_t;

typedef struct {
    uint32_t tick_ms;
    uint32_t due_flags;
    uint16_t due_count[BMS_SCHEDULER_TASK_COUNT];
    uint32_t total_count[BMS_SCHEDULER_TASK_COUNT];
} bms_scheduler_due_t;

typedef struct {
    bool initialized;
    volatile bool running;
    bms_scheduler_status_t status;
    bms_scheduler_profile_id_t profile_id;
    bms_scheduler_profile_t profile;
    volatile uint32_t tick_ms;
    volatile uint32_t due_flags;
    volatile uint16_t elapsed_ms[BMS_SCHEDULER_TASK_COUNT];
    volatile uint16_t due_count[BMS_SCHEDULER_TASK_COUNT];
    volatile uint32_t total_count[BMS_SCHEDULER_TASK_COUNT];
} bms_scheduler_t;

bms_status_t BMS_Scheduler_Init(bms_scheduler_t *scheduler);
bms_status_t BMS_Scheduler_LoadProfile(
    bms_scheduler_t *scheduler,
    bms_scheduler_profile_id_t profile_id);
bms_status_t BMS_Scheduler_Start(bms_scheduler_t *scheduler);
bms_status_t BMS_Scheduler_Stop(bms_scheduler_t *scheduler);
void BMS_Scheduler_OnBaseTickIsr(void *scheduler_arg);
bms_status_t BMS_Scheduler_ConsumeDueFlags(
    bms_scheduler_t *scheduler,
    bms_scheduler_due_t *due);

const bms_scheduler_profile_t *BMS_Scheduler_GetProfile(
    bms_scheduler_profile_id_t profile_id);
const char *BMS_SchedulerTask_ToString(bms_scheduler_task_id_t task_id);
uint32_t BMS_Scheduler_TaskMask(bms_scheduler_task_id_t task_id);

#ifdef __cplusplus
}
#endif

#endif
