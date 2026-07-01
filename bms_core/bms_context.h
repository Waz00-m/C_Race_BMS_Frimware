#ifndef BMS_CONTEXT_H
#define BMS_CONTEXT_H

#include "bms_registers.h"
#include "bms_status.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    uint32_t magic;
    bool initialized;
    bms_register_map_t regs;
} bms_context_t;

bms_status_t BMS_Context_Init(bms_context_t *ctx);
void BMS_Context_Deinit(bms_context_t *ctx);
bool BMS_Context_IsInitialized(const bms_context_t *ctx);
bms_status_t BMS_Context_ResetConfigDefaults(bms_context_t *ctx);
const bms_register_map_t *BMS_Context_GetRegisters(const bms_context_t *ctx);
bms_register_map_t *BMS_Context_GetMutableRegisters(bms_context_t *ctx);

#ifdef __cplusplus
}
#endif

#endif
