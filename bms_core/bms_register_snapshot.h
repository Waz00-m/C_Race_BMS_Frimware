#ifndef BMS_REGISTER_SNAPSHOT_H
#define BMS_REGISTER_SNAPSHOT_H

#include "bms_context.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    bms_register_map_t regs;
    uint32_t source_magic;
    bool source_initialized;
} bms_register_snapshot_t;

bms_status_t BMS_RegisterSnapshot_Capture(
    const bms_context_t *ctx,
    bms_register_snapshot_t *snapshot);

#ifdef __cplusplus
}
#endif

#endif
