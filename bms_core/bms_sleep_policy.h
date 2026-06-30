#ifndef BMS_SLEEP_POLICY_H
#define BMS_SLEEP_POLICY_H

#include "bms_context.h"

#ifdef __cplusplus
extern "C" {
#endif

#define BMS_SLEEP_POLICY_DEFAULT_LOAD_ACTIVE_THRESHOLD_MA (2000UL)

bms_status_t BMS_SleepPolicy_Init(bms_context_t *ctx);
bms_status_t BMS_SleepPolicy_Evaluate(bms_context_t *ctx);

#ifdef __cplusplus
}
#endif

#endif
