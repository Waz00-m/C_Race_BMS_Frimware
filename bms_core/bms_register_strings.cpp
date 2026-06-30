#include "bms_register_strings.h"

const char *BMS_SystemMode_ToString(bms_system_mode_t value)
{
    switch (value) {
    case BMS_SYSTEM_MODE_BOOT_INIT:
        return "BOOT_INIT";
    case BMS_SYSTEM_MODE_WAKE_RESTORE:
        return "WAKE_RESTORE";
    case BMS_SYSTEM_MODE_ACTIVE_MONITORING:
        return "ACTIVE_MONITORING";
    case BMS_SYSTEM_MODE_IDLE_MONITORING:
        return "IDLE_MONITORING";
    case BMS_SYSTEM_MODE_SLEEP_READY:
        return "SLEEP_READY";
    case BMS_SYSTEM_MODE_SLEEP_MODE:
        return "SLEEP_MODE";
    case BMS_SYSTEM_MODE_DIAGNOSTIC_MODE:
        return "DIAGNOSTIC_MODE";
    case BMS_SYSTEM_MODE_FAULT_ACTIVE:
        return "FAULT_ACTIVE";
    case BMS_SYSTEM_MODE_SAFE_MONITORING:
        return "SAFE_MONITORING";
    default:
        return "UNKNOWN_MODE";
    }
}

const char *BMS_WakeCause_ToString(bms_wake_cause_t value)
{
    switch (value) {
    case BMS_WAKE_CAUSE_UNKNOWN:
        return "UNKNOWN";
    case BMS_WAKE_CAUSE_POWER_ON:
        return "POWER_ON";
    case BMS_WAKE_CAUSE_TIMER:
        return "TIMER";
    case BMS_WAKE_CAUSE_UART:
        return "UART";
    case BMS_WAKE_CAUSE_GPIO:
        return "GPIO";
    case BMS_WAKE_CAUSE_FAULT_ALERT:
        return "FAULT_ALERT";
    case BMS_WAKE_CAUSE_LOAD_OR_CHARGER:
        return "LOAD_OR_CHARGER";
    default:
        return "UNKNOWN_WAKE";
    }
}

const char *BMS_SchedulerStatus_ToString(bms_scheduler_status_t value)
{
    switch (value) {
    case BMS_SCHEDULER_STOPPED:
        return "STOPPED";
    case BMS_SCHEDULER_ACTIVE:
        return "ACTIVE";
    case BMS_SCHEDULER_IDLE:
        return "IDLE";
    case BMS_SCHEDULER_SLEEP_WINDOW:
        return "SLEEP_WINDOW";
    default:
        return "UNKNOWN_SCHEDULER";
    }
}

const char *BMS_SocMethod_ToString(bms_soc_method_t value)
{
    switch (value) {
    case BMS_SOC_METHOD_NOT_AVAILABLE:
        return "NOT_AVAILABLE";
    case BMS_SOC_METHOD_VOLTAGE_ONLY:
        return "VOLTAGE_ONLY";
    case BMS_SOC_METHOD_COULOMB_COUNTING:
        return "COULOMB_COUNTING";
    case BMS_SOC_METHOD_HYBRID:
        return "HYBRID";
    default:
        return "UNKNOWN_SOC_METHOD";
    }
}

const char *BMS_SohMethod_ToString(bms_soh_method_t value)
{
    switch (value) {
    case BMS_SOH_NOT_AVAILABLE:
        return "NOT_AVAILABLE";
    case BMS_SOH_BASIC_CAPACITY_BASED:
        return "BASIC_CAPACITY_BASED";
    case BMS_SOH_RESISTANCE_TREND_BASED:
        return "RESISTANCE_TREND_BASED";
    case BMS_SOH_MODEL_BASED:
        return "MODEL_BASED";
    default:
        return "UNKNOWN_SOH_METHOD";
    }
}

const char *BMS_FaultSeverity_ToString(bms_fault_severity_t value)
{
    switch (value) {
    case BMS_FAULT_SEVERITY_NONE:
        return "NONE";
    case BMS_FAULT_SEVERITY_INFO:
        return "INFO";
    case BMS_FAULT_SEVERITY_WARNING:
        return "WARNING";
    case BMS_FAULT_SEVERITY_LIMITING:
        return "LIMITING";
    case BMS_FAULT_SEVERITY_CRITICAL:
        return "CRITICAL";
    default:
        return "UNKNOWN_SEVERITY";
    }
}

const char *BMS_SleepDecision_ToString(bms_sleep_decision_t value)
{
    switch (value) {
    case BMS_SLEEP_DECISION_NOT_EVALUATED:
        return "NOT_EVALUATED";
    case BMS_SLEEP_DECISION_ALLOWED:
        return "ALLOWED";
    case BMS_SLEEP_DECISION_DENIED:
        return "DENIED";
    default:
        return "UNKNOWN_SLEEP_DECISION";
    }
}

const char *BMS_SleepReason_ToString(bms_sleep_reason_t value)
{
    switch (value) {
    case BMS_SLEEP_REASON_NOT_EVALUATED:
        return "NOT_EVALUATED";
    case BMS_SLEEP_REASON_ALLOWED:
        return "SLEEP_ALLOWED";
    case BMS_SLEEP_REASON_DENIED_LOAD_ACTIVE:
        return "SLEEP_DENIED_LOAD_ACTIVE";
    case BMS_SLEEP_REASON_DENIED_FAULT_ACTIVE:
        return "SLEEP_DENIED_FAULT_ACTIVE";
    default:
        return "UNKNOWN_SLEEP_REASON";
    }
}
