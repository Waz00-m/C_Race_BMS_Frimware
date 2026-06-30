#include "bms_register_snapshot.h"

#include <string.h>

bms_status_t BMS_RegisterSnapshot_Capture(
    const bms_context_t *ctx,
    bms_register_snapshot_t *snapshot)
{
    if ((ctx == NULL) || (snapshot == NULL)) {
        return BMS_STATUS_INVALID_ARGUMENT;
    }

    if (!BMS_Context_IsInitialized(ctx)) {
        memset(snapshot, 0, sizeof(*snapshot));
        return BMS_STATUS_NOT_INITIALIZED;
    }

    snapshot->regs = ctx->regs;
    snapshot->source_magic = ctx->magic;
    snapshot->source_initialized = ctx->initialized;

    return BMS_STATUS_OK;
}
