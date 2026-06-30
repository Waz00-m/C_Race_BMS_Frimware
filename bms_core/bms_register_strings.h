#ifndef BMS_REGISTER_STRINGS_H
#define BMS_REGISTER_STRINGS_H

#include "bms_types.h"

#ifdef __cplusplus
extern "C" {
#endif

const char *BMS_SystemMode_ToString(bms_system_mode_t value);
const char *BMS_WakeCause_ToString(bms_wake_cause_t value);
const char *BMS_SchedulerStatus_ToString(bms_scheduler_status_t value);
const char *BMS_SocMethod_ToString(bms_soc_method_t value);
const char *BMS_SohMethod_ToString(bms_soh_method_t value);
const char *BMS_FaultSeverity_ToString(bms_fault_severity_t value);
const char *BMS_SleepDecision_ToString(bms_sleep_decision_t value);
const char *BMS_SleepReason_ToString(bms_sleep_reason_t value);

#ifdef __cplusplus
}
#endif

#endif
