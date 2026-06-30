#include "bms_app.h"

#include <stdio.h>

#include "bms_app_config.h"
#include "bms_adc_hal.h"
#include "bms_diagnostic.h"
#include "bms_display_hal.h"
#include "bms_fault_supervisor.h"
#include "bms_lock_hal.h"
#include "bms_measurement.h"
#include "bms_register_snapshot.h"
#include "bms_register_strings.h"
#include "bms_scheduler.h"
#include "bms_sleep_policy.h"
#include "bms_timer_hal.h"
#include "bms_uart_hal.h"

static bms_context_t g_bms_context;
static bms_scheduler_t g_bms_scheduler;
static bms_diagnostic_t g_bms_diagnostic;
static uint16_t g_scheduler_telemetry_heartbeat_accum = 0U;

static void BMS_App_SendLine(const char *line)
{
    BMS_HAL_UART_Send(line);
    BMS_HAL_UART_Send("\r\n");
}

static bool BMS_App_TemperatureIsValid(
    const bms_meas_reg_t *meas,
    uint8_t index)
{
    return (index < BMS_NUM_TEMPERATURES) &&
           ((meas->temperature_valid_bitmap & (1UL << index)) != 0UL);
}

static void BMS_App_FormatTemperature(
    const bms_meas_reg_t *meas,
    uint8_t index,
    char *text,
    size_t text_size)
{
    if ((text == NULL) || (text_size == 0U)) {
        return;
    }

    if (!BMS_App_TemperatureIsValid(meas, index)) {
        (void)snprintf(text, text_size, "FAULT");
        return;
    }

    (void)snprintf(
        text,
        text_size,
        "%d",
        (int)meas->temperature_dC[index]);
}

static void BMS_App_PrintRegisterSnapshot(void)
{
    bms_register_snapshot_t snapshot;
    const bms_status_t status =
        BMS_RegisterSnapshot_Capture(&g_bms_context, &snapshot);

    if (status != BMS_STATUS_OK) {
        BMS_App_SendLine("REGISTER SNAPSHOT FAILED");
        return;
    }

    const bms_register_map_t *regs = &snapshot.regs;
    char line[192];

    BMS_App_SendLine("BMS REGISTER SNAPSHOT");

    (void)snprintf(
        line,
        sizeof(line),
        "SYS: mode=%s uptime_ms=%lu wake=%s scheduler=%s reset=%lu",
        BMS_SystemMode_ToString(regs->sys.system_mode),
        (unsigned long)regs->sys.uptime_ms,
        BMS_WakeCause_ToString(regs->sys.wake_cause),
        BMS_SchedulerStatus_ToString(regs->sys.scheduler_status),
        (unsigned long)regs->sys.reset_reason);
    BMS_App_SendLine(line);

    (void)snprintf(
        line,
        sizeof(line),
        "ACQ: valid=0x%08lX filter_ready=0x%08lX channels=%u",
        (unsigned long)regs->acq.sensor_valid_bitmap,
        (unsigned long)regs->acq.filter_ready_bitmap,
        (unsigned)BMS_ACQ_CHANNEL_COUNT);
    BMS_App_SendLine(line);

    (void)snprintf(
        line,
        sizeof(line),
        "MEAS: pack_mV=%lu current_mA=%ld current_abs_mA=%lu min_cell=%u max_cell=%u delta_mV=%u",
        (unsigned long)regs->meas.pack_mV,
        (long)regs->meas.current_mA,
        (unsigned long)regs->meas.current_abs_mA,
        (unsigned)regs->meas.min_cell_index,
        (unsigned)regs->meas.max_cell_index,
        (unsigned)regs->meas.cell_delta_mV);
    BMS_App_SendLine(line);

    (void)snprintf(
        line,
        sizeof(line),
        "EST: soc_dP=%u soc_valid=%u soc_method=%s soh_valid=%u soh_method=%s",
        (unsigned)regs->est.soc_dP,
        (unsigned)regs->est.soc_valid,
        BMS_SocMethod_ToString(regs->est.soc_method),
        (unsigned)regs->est.soh_valid,
        BMS_SohMethod_ToString(regs->est.soh_method));
    BMS_App_SendLine(line);

    (void)snprintf(
        line,
        sizeof(line),
        "FAULT: warn=0x%08lX active=0x%08lX latched=0x%08lX primary=0x%04X severity=%s events=%lu",
        (unsigned long)regs->fault.warning_bitmap,
        (unsigned long)regs->fault.active_fault_bitmap,
        (unsigned long)regs->fault.latched_fault_bitmap,
        (unsigned)regs->fault.primary_fault_code,
        BMS_FaultSeverity_ToString(regs->fault.fault_severity),
        (unsigned long)regs->fault.event_counter);
    BMS_App_SendLine(line);

    (void)snprintf(
        line,
        sizeof(line),
        "DIAG: active=%u cmd=%u target=%u test=%u response=%u override=%lu",
        (unsigned)regs->diag.diagnostic_active,
        (unsigned)regs->diag.command_id,
        (unsigned)regs->diag.target_service,
        (unsigned)regs->diag.test_id,
        (unsigned)regs->diag.response_code,
        (unsigned long)regs->diag.override_token);
    BMS_App_SendLine(line);

    (void)snprintf(
        line,
        sizeof(line),
        "SLEEP: decision=%s reason=%s allowed=%u load_mA=%lu threshold_mA=%lu evals=%lu",
        BMS_SleepDecision_ToString(regs->sleep.decision),
        BMS_SleepReason_ToString(regs->sleep.reason),
        (unsigned)regs->sleep.sleep_allowed,
        (unsigned long)regs->meas.current_abs_mA,
        (unsigned long)regs->sleep.load_active_threshold_mA,
        (unsigned long)regs->sleep.evaluated_count);
    BMS_App_SendLine(line);

    (void)snprintf(
        line,
        sizeof(line),
        "CFG: version=%lu capacity_mAh=%lu crc=0x%08lX",
        (unsigned long)regs->cfg.config_version,
        (unsigned long)regs->cfg.battery_capacity_mAh,
        (unsigned long)regs->cfg.config_crc);
    BMS_App_SendLine(line);
}

static void BMS_App_PrintSchedulerProfile(void)
{
    const bms_scheduler_profile_t *profile =
        BMS_Scheduler_GetProfile(BMS_SCHEDULER_PROFILE_ACTIVE);

    if (profile == NULL) {
        BMS_App_SendLine("SCHED PROFILE: unavailable");
        return;
    }

    char line[192];
    (void)snprintf(
        line,
        sizeof(line),
        "SCHED PROFILE ACTIVE: current=%ums voltage=%ums temp=%ums est=%ums fault=%ums telemetry=%ums diag=%ums sleep_policy=%ums",
        (unsigned)profile->period_ms[BMS_SCHEDULER_TASK_CURRENT],
        (unsigned)profile->period_ms[BMS_SCHEDULER_TASK_VOLTAGE],
        (unsigned)profile->period_ms[BMS_SCHEDULER_TASK_TEMPERATURE],
        (unsigned)profile->period_ms[BMS_SCHEDULER_TASK_ESTIMATION],
        (unsigned)profile->period_ms[BMS_SCHEDULER_TASK_FAULT],
        (unsigned)profile->period_ms[BMS_SCHEDULER_TASK_TELEMETRY],
        (unsigned)profile->period_ms[BMS_SCHEDULER_TASK_DIAGNOSTIC],
        (unsigned)profile->period_ms[BMS_SCHEDULER_TASK_SLEEP_POLICY]);
    BMS_App_SendLine(line);
}

static void BMS_App_PrintSchedulerHeartbeat(const bms_scheduler_due_t *due)
{
    if (due == NULL) {
        return;
    }

    char line[192];
    (void)snprintf(
        line,
        sizeof(line),
        "SCHED: tick_ms=%lu total current=%lu voltage=%lu temp=%lu est=%lu fault=%lu telemetry=%lu diag=%lu sleep_policy=%lu",
        (unsigned long)due->tick_ms,
        (unsigned long)due->total_count[BMS_SCHEDULER_TASK_CURRENT],
        (unsigned long)due->total_count[BMS_SCHEDULER_TASK_VOLTAGE],
        (unsigned long)due->total_count[BMS_SCHEDULER_TASK_TEMPERATURE],
        (unsigned long)due->total_count[BMS_SCHEDULER_TASK_ESTIMATION],
        (unsigned long)due->total_count[BMS_SCHEDULER_TASK_FAULT],
        (unsigned long)due->total_count[BMS_SCHEDULER_TASK_TELEMETRY],
        (unsigned long)due->total_count[BMS_SCHEDULER_TASK_DIAGNOSTIC],
        (unsigned long)due->total_count[BMS_SCHEDULER_TASK_SLEEP_POLICY]);
    BMS_App_SendLine(line);
}

static void BMS_App_PrintMeasurementHeartbeat(void)
{
    bms_register_snapshot_t snapshot;
    const bms_status_t status =
        BMS_RegisterSnapshot_Capture(&g_bms_context, &snapshot);

    if (status != BMS_STATUS_OK) {
        BMS_App_SendLine("MEAS: snapshot unavailable");
        return;
    }

    const bms_meas_reg_t *meas = &snapshot.regs.meas;
    char line[224];
    char temp0[12];
    char temp1[12];
    char temp2[12];
    char temp3[12];

    BMS_App_FormatTemperature(meas, 0U, temp0, sizeof(temp0));
    BMS_App_FormatTemperature(meas, 1U, temp1, sizeof(temp1));
    BMS_App_FormatTemperature(meas, 2U, temp2, sizeof(temp2));
    BMS_App_FormatTemperature(meas, 3U, temp3, sizeof(temp3));

    (void)snprintf(
        line,
        sizeof(line),
        "MEAS: pack_mV=%lu current_mA=%ld current_valid=%u temp_dC=[%s,%s,%s,%s] temp_valid=0x%08lX cell_mV=[%u,%u,%u,%u,%u,%u]",
        (unsigned long)meas->pack_mV,
        (long)meas->current_mA,
        (unsigned)meas->current_valid,
        temp0,
        temp1,
        temp2,
        temp3,
        (unsigned long)meas->temperature_valid_bitmap,
        (unsigned)meas->cell_mV[0],
        (unsigned)meas->cell_mV[1],
        (unsigned)meas->cell_mV[2],
        (unsigned)meas->cell_mV[3],
        (unsigned)meas->cell_mV[4],
        (unsigned)meas->cell_mV[5]);
    BMS_App_SendLine(line);

    (void)snprintf(
        line,
        sizeof(line),
        "ACQ: adc_mV cell=[%u,%u,%u,%u,%u,%u] current=%u temp=[%u,%u,%u,%u] valid=0x%08lX",
        (unsigned)snapshot.regs.acq.adc_mV[BMS_ADC_CHANNEL_CELL_1],
        (unsigned)snapshot.regs.acq.adc_mV[BMS_ADC_CHANNEL_CELL_2],
        (unsigned)snapshot.regs.acq.adc_mV[BMS_ADC_CHANNEL_CELL_3],
        (unsigned)snapshot.regs.acq.adc_mV[BMS_ADC_CHANNEL_CELL_4],
        (unsigned)snapshot.regs.acq.adc_mV[BMS_ADC_CHANNEL_CELL_5],
        (unsigned)snapshot.regs.acq.adc_mV[BMS_ADC_CHANNEL_CELL_6],
        (unsigned)snapshot.regs.acq.adc_mV[BMS_ADC_CHANNEL_CURRENT],
        (unsigned)snapshot.regs.acq.adc_mV[BMS_ADC_CHANNEL_TEMP_1],
        (unsigned)snapshot.regs.acq.adc_mV[BMS_ADC_CHANNEL_TEMP_2],
        (unsigned)snapshot.regs.acq.adc_mV[BMS_ADC_CHANNEL_TEMP_3],
        (unsigned)snapshot.regs.acq.adc_mV[BMS_ADC_CHANNEL_TEMP_4],
        (unsigned long)snapshot.regs.acq.sensor_valid_bitmap);
    BMS_App_SendLine(line);

    (void)snprintf(
        line,
        sizeof(line),
        "FAULT: warn=0x%08lX active=0x%08lX latched=0x%08lX primary=0x%04X severity=%s events=%lu",
        (unsigned long)snapshot.regs.fault.warning_bitmap,
        (unsigned long)snapshot.regs.fault.active_fault_bitmap,
        (unsigned long)snapshot.regs.fault.latched_fault_bitmap,
        (unsigned)snapshot.regs.fault.primary_fault_code,
        BMS_FaultSeverity_ToString(snapshot.regs.fault.fault_severity),
        (unsigned long)snapshot.regs.fault.event_counter);
    BMS_App_SendLine(line);

    (void)snprintf(
        line,
        sizeof(line),
        "SLEEP: decision=%s reason=%s allowed=%u load_mA=%lu threshold_mA=%lu evals=%lu",
        BMS_SleepDecision_ToString(snapshot.regs.sleep.decision),
        BMS_SleepReason_ToString(snapshot.regs.sleep.reason),
        (unsigned)snapshot.regs.sleep.sleep_allowed,
        (unsigned long)snapshot.regs.meas.current_abs_mA,
        (unsigned long)snapshot.regs.sleep.load_active_threshold_mA,
        (unsigned long)snapshot.regs.sleep.evaluated_count);
    BMS_App_SendLine(line);
}

bms_status_t BMS_App_Init(void)
{
    const bms_status_t uart_status = BMS_HAL_UART_Init();
    if (uart_status != BMS_STATUS_OK) {
        return uart_status;
    }

    const bms_status_t lock_status = BMS_HAL_Lock_Init();
    if (lock_status != BMS_STATUS_OK) {
        BMS_HAL_UART_Send("BMS LOCK HAL INIT FAILED\r\n");
        return lock_status;
    }

    const bms_status_t timer_status = BMS_HAL_Timer_Init();
    if (timer_status != BMS_STATUS_OK) {
        BMS_HAL_UART_Send("BMS TIMER HAL INIT FAILED\r\n");
        return timer_status;
    }

    const bms_status_t adc_status = BMS_HAL_ADC_Init();
    if (adc_status != BMS_STATUS_OK) {
        BMS_HAL_UART_Send("BMS ADC HAL INIT FAILED\r\n");
        return adc_status;
    }

    const bms_status_t display_status = BMS_HAL_Display_Init();
    if (display_status != BMS_STATUS_OK) {
        BMS_HAL_UART_Send("BMS DISPLAY INIT SKIPPED\r\n");
    }

    const bms_status_t status = BMS_Context_Init(&g_bms_context);
    if (status != BMS_STATUS_OK) {
        BMS_HAL_UART_Send("BMS INIT FAILED\r\n");
        return status;
    }

    const bms_status_t measurement_status =
        BMS_Measurement_Init(&g_bms_context);
    if (measurement_status != BMS_STATUS_OK) {
        BMS_HAL_UART_Send("BMS MEASUREMENT INIT FAILED\r\n");
        return measurement_status;
    }

    const bms_status_t fault_status =
        BMS_FaultSupervisor_Init(&g_bms_context);
    if (fault_status != BMS_STATUS_OK) {
        BMS_HAL_UART_Send("BMS FAULT SUPERVISOR INIT FAILED\r\n");
        return fault_status;
    }

    const bms_status_t diagnostic_status =
        BMS_Diagnostic_Init(&g_bms_diagnostic, &g_bms_context);
    if (diagnostic_status != BMS_STATUS_OK) {
        BMS_HAL_UART_Send("BMS DIAGNOSTIC INIT FAILED\r\n");
        return diagnostic_status;
    }

    const bms_status_t sleep_status =
        BMS_SleepPolicy_Init(&g_bms_context);
    if (sleep_status != BMS_STATUS_OK) {
        BMS_HAL_UART_Send("BMS SLEEP POLICY INIT FAILED\r\n");
        return sleep_status;
    }

    bms_status_t scheduler_status = BMS_Scheduler_Init(&g_bms_scheduler);
    if (scheduler_status != BMS_STATUS_OK) {
        BMS_HAL_UART_Send("BMS SCHEDULER INIT FAILED\r\n");
        return scheduler_status;
    }

    scheduler_status = BMS_Scheduler_LoadProfile(
        &g_bms_scheduler,
        BMS_SCHEDULER_PROFILE_ACTIVE);
    if (scheduler_status != BMS_STATUS_OK) {
        BMS_HAL_UART_Send("BMS SCHEDULER PROFILE FAILED\r\n");
        return scheduler_status;
    }

    scheduler_status = BMS_Scheduler_Start(&g_bms_scheduler);
    if (scheduler_status != BMS_STATUS_OK) {
        BMS_HAL_UART_Send("BMS SCHEDULER START FAILED\r\n");
        return scheduler_status;
    }

    g_bms_context.regs.sys.system_mode = BMS_SYSTEM_MODE_ACTIVE_MONITORING;
    g_bms_context.regs.sys.scheduler_status = BMS_SCHEDULER_ACTIVE;

    (void)BMS_Measurement_UpdateCurrent(&g_bms_context);
    (void)BMS_Measurement_UpdateVoltage(&g_bms_context);
    (void)BMS_Measurement_UpdateTemperature(&g_bms_context);
    (void)BMS_FaultSupervisor_Update(&g_bms_context);
    (void)BMS_SleepPolicy_Evaluate(&g_bms_context);

    char line[128];
    (void)snprintf(
        line,
        sizeof(line),
        "%s,MODE=%s,CELLS=%u,TEMPS=%u",
        BMS_APP_INIT_BANNER,
        BMS_SystemMode_ToString(g_bms_context.regs.sys.system_mode),
        (unsigned)BMS_NUM_CELLS,
        (unsigned)BMS_NUM_TEMPERATURES);

    BMS_App_SendLine(line);
    BMS_App_PrintRegisterSnapshot();
    BMS_App_PrintSchedulerProfile();

    const bms_status_t start_tick_status = BMS_HAL_Timer_StartBaseTick(
        BMS_SCHEDULER_BASE_TICK_US,
        BMS_Scheduler_OnBaseTickIsr,
        &g_bms_scheduler);
    if (start_tick_status != BMS_STATUS_OK) {
        BMS_HAL_UART_Send("BMS TIMER START FAILED\r\n");
        (void)BMS_Scheduler_Stop(&g_bms_scheduler);
        g_bms_context.regs.sys.scheduler_status = BMS_SCHEDULER_STOPPED;
        return start_tick_status;
    }

    BMS_App_SendLine("BMS SCHEDULER TICK STARTED");
    BMS_App_SendLine("DIAG READY: HELP, GET,SNAPSHOT, GET,VOLT, GET,CURRENT, GET,TEMP, GET,FAULT, GET,SLEEP, GET,TAPS");
    return BMS_STATUS_OK;
}

void BMS_App_Run(void)
{
    if (!BMS_Context_IsInitialized(&g_bms_context)) {
        return;
    }

    bms_scheduler_due_t due;
    const bms_status_t status =
        BMS_Scheduler_ConsumeDueFlags(&g_bms_scheduler, &due);
    if (status != BMS_STATUS_OK) {
        return;
    }

    if (due.due_flags == 0UL) {
        return;
    }

    (void)BMS_HAL_Display_PollInput();

    g_bms_context.regs.sys.uptime_ms = due.tick_ms;
    g_bms_context.regs.sys.scheduler_status = g_bms_scheduler.status;

    if (due.due_count[BMS_SCHEDULER_TASK_CURRENT] > 0U) {
        (void)BMS_Measurement_UpdateCurrent(&g_bms_context);
    }

    if (due.due_count[BMS_SCHEDULER_TASK_VOLTAGE] > 0U) {
        (void)BMS_Measurement_UpdateVoltage(&g_bms_context);
    }

    if (due.due_count[BMS_SCHEDULER_TASK_TEMPERATURE] > 0U) {
        (void)BMS_Measurement_UpdateTemperature(&g_bms_context);
    }

    if (due.due_count[BMS_SCHEDULER_TASK_FAULT] > 0U) {
        (void)BMS_FaultSupervisor_Update(&g_bms_context);
    }

    if (due.due_count[BMS_SCHEDULER_TASK_SLEEP_POLICY] > 0U) {
        (void)BMS_SleepPolicy_Evaluate(&g_bms_context);
    }

    if (due.due_count[BMS_SCHEDULER_TASK_DIAGNOSTIC] > 0U) {
        (void)BMS_Diagnostic_Poll(&g_bms_diagnostic, &g_bms_context);
    }

    if (due.due_count[BMS_SCHEDULER_TASK_TELEMETRY] > 0U) {
        g_scheduler_telemetry_heartbeat_accum +=
            due.due_count[BMS_SCHEDULER_TASK_TELEMETRY];

        if (g_scheduler_telemetry_heartbeat_accum >=
            BMS_SCHEDULER_TELEMETRY_HEARTBEAT_DIVIDER) {
            g_scheduler_telemetry_heartbeat_accum = 0U;
            BMS_App_PrintSchedulerHeartbeat(&due);
            BMS_App_PrintMeasurementHeartbeat();

            bms_register_snapshot_t snapshot;
            if (BMS_RegisterSnapshot_Capture(
                    &g_bms_context,
                    &snapshot) == BMS_STATUS_OK) {
                (void)BMS_HAL_Display_Update(&snapshot);
            }
        }
    }
}

const bms_context_t *BMS_App_GetContext(void)
{
    return &g_bms_context;
}
