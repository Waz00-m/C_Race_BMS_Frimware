#ifndef BMS_FAULT_SUPERVISOR_H
#define BMS_FAULT_SUPERVISOR_H

#include "bms_context.h"

#ifdef __cplusplus
extern "C" {
#endif

bms_status_t BMS_FaultSupervisor_Init(bms_context_t *ctx);
bms_status_t BMS_FaultSupervisor_Update(bms_context_t *ctx);

#ifdef __cplusplus
}
#endif

#endif
