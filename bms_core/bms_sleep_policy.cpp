#include "bms_sleep_policy.h"

bms_status_t BMS_SleepPolicy_Init(bms_context_t *ctx)
{
    if (!BMS_Context_IsInitialized(ctx)) {
        return BMS_STATUS_NOT_INITIALIZED;
    }

    ctx->regs.sleep.sleep_allowed = false;
    ctx->regs.sleep.decision = BMS_SLEEP_DECISION_NOT_EVALUATED;
    ctx->regs.sleep.reason = BMS_SLEEP_REASON_NOT_EVALUATED;
    ctx->regs.sleep.evaluated_count = 0UL;
    ctx->regs.sleep.last_eval_uptime_ms = 0UL;

    if (ctx->regs.sleep.load_active_threshold_mA == 0UL) {
        ctx->regs.sleep.load_active_threshold_mA =
            BMS_SLEEP_POLICY_DEFAULT_LOAD_ACTIVE_THRESHOLD_MA;
    }

    return BMS_STATUS_OK;
}

bms_status_t BMS_SleepPolicy_Evaluate(bms_context_t *ctx)
{
    if (!BMS_Context_IsInitialized(ctx)) {
        return BMS_STATUS_NOT_INITIALIZED;
    }

    bms_sleep_reg_t *sleep = &ctx->regs.sleep;
    sleep->evaluated_count++;
    sleep->last_eval_uptime_ms = ctx->regs.sys.uptime_ms;

    if (ctx->regs.fault.active_fault_bitmap != 0UL) {
        sleep->sleep_allowed = false;
        sleep->decision = BMS_SLEEP_DECISION_DENIED;
        sleep->reason = BMS_SLEEP_REASON_DENIED_FAULT_ACTIVE;
        return BMS_STATUS_OK;
    }

    if (ctx->regs.meas.current_abs_mA > sleep->load_active_threshold_mA) {
        sleep->sleep_allowed = false;
        sleep->decision = BMS_SLEEP_DECISION_DENIED;
        sleep->reason = BMS_SLEEP_REASON_DENIED_LOAD_ACTIVE;
        return BMS_STATUS_OK;
    }

    sleep->sleep_allowed = true;
    sleep->decision = BMS_SLEEP_DECISION_ALLOWED;
    sleep->reason = BMS_SLEEP_REASON_ALLOWED;

    return BMS_STATUS_OK;
}
