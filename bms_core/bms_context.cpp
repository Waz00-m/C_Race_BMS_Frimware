#include "bms_context.h"

#include <string.h>

#include "bms_fault_codes.h"
#include "bms_measurement_config.h"
#include "bms_sleep_policy.h"

static void BMS_Context_InitConfigDefaults(bms_cfg_reg_t *cfg)
{
    memset(cfg, 0, sizeof(*cfg));

    cfg->config_version = BMS_CONFIG_VERSION;
    cfg->battery_capacity_mAh = 22000UL;

    for (uint8_t i = 0U; i < BMS_NUM_CELLS; ++i) {
        cfg->voltage_divider_ratio_ppm[i] =
            BMS_DEFAULT_VOLTAGE_DIVIDER_RATIO_PPM[i];
        cfg->voltage_gain_ppm[i] = BMS_DEFAULT_VOLTAGE_GAIN_PPM[i];
        cfg->voltage_offset_mV[i] = BMS_DEFAULT_VOLTAGE_OFFSET_MV[i];
    }

    for (uint8_t i = 0U; i < BMS_NUM_TEMPERATURES; ++i) {
        cfg->ntc_adc_gain_ppm[i] = BMS_NTC_ADC_GAIN_PPM[i];
        cfg->ntc_adc_offset_mV[i] = BMS_NTC_ADC_OFFSET_MV[i];
    }

    cfg->voltage_thresholds_mV[
        BMS_VOLTAGE_THRESHOLD_CELL_LOW_WARNING_MV] = 3300U;
    cfg->voltage_thresholds_mV[
        BMS_VOLTAGE_THRESHOLD_CELL_LOW_FAULT_MV] = 3000U;
    cfg->voltage_thresholds_mV[
        BMS_VOLTAGE_THRESHOLD_CELL_HIGH_WARNING_MV] = 4200U;
    cfg->voltage_thresholds_mV[
        BMS_VOLTAGE_THRESHOLD_CELL_HIGH_FAULT_MV] = 4250U;
    cfg->voltage_thresholds_mV[
        BMS_VOLTAGE_THRESHOLD_PACK_LOW_FAULT_MV] = 18000U;
    cfg->voltage_thresholds_mV[
        BMS_VOLTAGE_THRESHOLD_PACK_HIGH_FAULT_MV] = 25500U;
    cfg->voltage_thresholds_mV[
        BMS_VOLTAGE_THRESHOLD_CELL_IMBALANCE_WARNING_MV] = 80U;

    cfg->current_thresholds_mA[
        BMS_CURRENT_THRESHOLD_OVERCURRENT_WARNING_MA] = 110000L;
    cfg->current_thresholds_mA[
        BMS_CURRENT_THRESHOLD_OVERCURRENT_FAULT_MA] = 120000L;

    cfg->temperature_thresholds_dC[
        BMS_TEMPERATURE_THRESHOLD_HIGH_WARNING_DC] = 500;
    cfg->temperature_thresholds_dC[
        BMS_TEMPERATURE_THRESHOLD_HIGH_FAULT_DC] = 600;

    for (uint32_t i = 0U; i < BMS_CALIBRATION_CHANNEL_COUNT; ++i) {
        cfg->calibration_gain_ppm[i] = 1000000L;
        cfg->calibration_offset[i] = 0L;
    }
}

static void BMS_Context_InitRegisterDefaults(bms_register_map_t *regs)
{
    memset(regs, 0, sizeof(*regs));

    regs->sys.system_mode = BMS_SYSTEM_MODE_BOOT_INIT;
    regs->sys.sub_state = 0U;
    regs->sys.uptime_ms = 0UL;
    regs->sys.wake_cause = BMS_WAKE_CAUSE_POWER_ON;
    regs->sys.scheduler_status = BMS_SCHEDULER_STOPPED;
    regs->sys.reset_reason = 0UL;

    regs->est.soc_dP = 0U;
    regs->est.soh_dP = 0U;
    regs->est.dod_dP = 0U;
    regs->est.soc_valid = false;
    regs->est.soh_valid = false;
    regs->est.soc_method = BMS_SOC_METHOD_NOT_AVAILABLE;
    regs->est.soh_method = BMS_SOH_NOT_AVAILABLE;

    regs->fault.primary_fault_code = 0x0000U;
    regs->fault.fault_severity = BMS_FAULT_SEVERITY_NONE;

    regs->sleep.sleep_allowed = false;
    regs->sleep.decision = BMS_SLEEP_DECISION_NOT_EVALUATED;
    regs->sleep.reason = BMS_SLEEP_REASON_NOT_EVALUATED;
    regs->sleep.load_active_threshold_mA =
        BMS_SLEEP_POLICY_DEFAULT_LOAD_ACTIVE_THRESHOLD_MA;

    BMS_Context_InitConfigDefaults(&regs->cfg);
}

bms_status_t BMS_Context_Init(bms_context_t *ctx)
{
    if (ctx == NULL) {
        return BMS_STATUS_INVALID_ARGUMENT;
    }

    memset(ctx, 0, sizeof(*ctx));
    BMS_Context_InitRegisterDefaults(&ctx->regs);

    ctx->magic = BMS_CONTEXT_MAGIC;
    ctx->initialized = true;

    return BMS_STATUS_OK;
}

void BMS_Context_Deinit(bms_context_t *ctx)
{
    if (ctx == NULL) {
        return;
    }

    memset(ctx, 0, sizeof(*ctx));
}

bool BMS_Context_IsInitialized(const bms_context_t *ctx)
{
    return (ctx != NULL) &&
           (ctx->magic == BMS_CONTEXT_MAGIC) &&
           (ctx->initialized == true);
}

bms_status_t BMS_Context_ResetConfigDefaults(bms_context_t *ctx)
{
    if (!BMS_Context_IsInitialized(ctx)) {
        return BMS_STATUS_NOT_INITIALIZED;
    }

    BMS_Context_InitConfigDefaults(&ctx->regs.cfg);

    return BMS_STATUS_OK;
}

const bms_register_map_t *BMS_Context_GetRegisters(const bms_context_t *ctx)
{
    if (!BMS_Context_IsInitialized(ctx)) {
        return NULL;
    }

    return &ctx->regs;
}

bms_register_map_t *BMS_Context_GetMutableRegisters(bms_context_t *ctx)
{
    if (!BMS_Context_IsInitialized(ctx)) {
        return NULL;
    }

    return &ctx->regs;
}
