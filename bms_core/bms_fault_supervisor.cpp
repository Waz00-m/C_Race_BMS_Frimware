#include "bms_fault_supervisor.h"

#include "bms_fault_codes.h"

static uint32_t BMS_FaultSupervisor_ExpectedSensorMask(void)
{
    return (1UL << BMS_ACQ_CHANNEL_COUNT) - 1UL;
}

static void BMS_FaultSupervisor_SetPrimaryIfEmpty(
    bms_fault_reg_t *fault,
    bms_fault_code_t code)
{
    if (fault->primary_fault_code == BMS_FAULT_CODE_NONE) {
        fault->primary_fault_code = (uint16_t)code;
    }
}

static void BMS_FaultSupervisor_CheckSensorValidity(
    const bms_acq_reg_t *acq,
    bms_fault_reg_t *fault)
{
    const uint32_t expected = BMS_FaultSupervisor_ExpectedSensorMask();
    if ((acq->sensor_valid_bitmap & expected) != expected) {
        fault->warning_bitmap |= BMS_WARNING_SENSOR_INVALID;
        fault->active_fault_bitmap |= BMS_FAULT_SENSOR_INVALID;
        BMS_FaultSupervisor_SetPrimaryIfEmpty(
            fault,
            BMS_FAULT_CODE_ADC_READ_FAILURE);
    }
}

static void BMS_FaultSupervisor_CheckVoltage(
    const bms_meas_reg_t *meas,
    const bms_cfg_reg_t *cfg,
    bms_fault_reg_t *fault)
{
    const uint16_t low_warn =
        cfg->voltage_thresholds_mV[BMS_VOLTAGE_THRESHOLD_CELL_LOW_WARNING_MV];
    const uint16_t low_fault =
        cfg->voltage_thresholds_mV[BMS_VOLTAGE_THRESHOLD_CELL_LOW_FAULT_MV];
    const uint16_t high_warn =
        cfg->voltage_thresholds_mV[BMS_VOLTAGE_THRESHOLD_CELL_HIGH_WARNING_MV];
    const uint16_t high_fault =
        cfg->voltage_thresholds_mV[BMS_VOLTAGE_THRESHOLD_CELL_HIGH_FAULT_MV];
    const uint16_t imbalance_warn =
        cfg->voltage_thresholds_mV[
            BMS_VOLTAGE_THRESHOLD_CELL_IMBALANCE_WARNING_MV];

    for (uint8_t i = 0U; i < BMS_NUM_CELLS; ++i) {
        const uint16_t cell_mV = meas->cell_mV[i];

        if (cell_mV < low_warn) {
            fault->warning_bitmap |= BMS_WARNING_CELL_LOW;
        }

        if (cell_mV < low_fault) {
            fault->active_fault_bitmap |= BMS_FAULT_CELL_UNDERVOLTAGE;
            BMS_FaultSupervisor_SetPrimaryIfEmpty(
                fault,
                BMS_FAULT_CODE_CELL_UNDERVOLTAGE);
        }

        if (cell_mV > high_warn) {
            fault->warning_bitmap |= BMS_WARNING_CELL_HIGH;
        }

        if (cell_mV > high_fault) {
            fault->active_fault_bitmap |= BMS_FAULT_CELL_OVERVOLTAGE;
            BMS_FaultSupervisor_SetPrimaryIfEmpty(
                fault,
                BMS_FAULT_CODE_CELL_OVERVOLTAGE);
        }
    }

    if (meas->cell_delta_mV > imbalance_warn) {
        fault->warning_bitmap |= BMS_WARNING_CELL_IMBALANCE;
    }

    if (meas->pack_mV <
        cfg->voltage_thresholds_mV[BMS_VOLTAGE_THRESHOLD_PACK_LOW_FAULT_MV]) {
        fault->active_fault_bitmap |= BMS_FAULT_PACK_UNDERVOLTAGE;
        BMS_FaultSupervisor_SetPrimaryIfEmpty(
            fault,
            BMS_FAULT_CODE_PACK_UNDERVOLTAGE);
    }

    if (meas->pack_mV >
        cfg->voltage_thresholds_mV[BMS_VOLTAGE_THRESHOLD_PACK_HIGH_FAULT_MV]) {
        fault->active_fault_bitmap |= BMS_FAULT_PACK_OVERVOLTAGE;
        BMS_FaultSupervisor_SetPrimaryIfEmpty(
            fault,
            BMS_FAULT_CODE_PACK_OVERVOLTAGE);
    }
}

static void BMS_FaultSupervisor_CheckCurrent(
    const bms_meas_reg_t *meas,
    const bms_cfg_reg_t *cfg,
    bms_fault_reg_t *fault)
{
    if (!meas->current_valid) {
        fault->warning_bitmap |= BMS_WARNING_SENSOR_INVALID;
        fault->active_fault_bitmap |= BMS_FAULT_SENSOR_INVALID;
        BMS_FaultSupervisor_SetPrimaryIfEmpty(
            fault,
            BMS_FAULT_CODE_CURRENT_SENSOR_FAULT);
        return;
    }

    const int32_t warning_mA =
        cfg->current_thresholds_mA[BMS_CURRENT_THRESHOLD_OVERCURRENT_WARNING_MA];
    const int32_t fault_mA =
        cfg->current_thresholds_mA[BMS_CURRENT_THRESHOLD_OVERCURRENT_FAULT_MA];

    if ((int32_t)meas->current_abs_mA > warning_mA) {
        fault->warning_bitmap |= BMS_WARNING_OVERCURRENT;
    }

    if ((int32_t)meas->current_abs_mA > fault_mA) {
        fault->active_fault_bitmap |= BMS_FAULT_OVERCURRENT;
        BMS_FaultSupervisor_SetPrimaryIfEmpty(
            fault,
            BMS_FAULT_CODE_DISCHARGE_OVERCURRENT);
    }
}

static void BMS_FaultSupervisor_CheckTemperature(
    const bms_meas_reg_t *meas,
    const bms_cfg_reg_t *cfg,
    bms_fault_reg_t *fault)
{
    const int16_t warning_dC =
        cfg->temperature_thresholds_dC[
            BMS_TEMPERATURE_THRESHOLD_HIGH_WARNING_DC];
    const int16_t fault_dC =
        cfg->temperature_thresholds_dC[
            BMS_TEMPERATURE_THRESHOLD_HIGH_FAULT_DC];

    for (uint8_t i = 0U; i < BMS_NUM_TEMPERATURES; ++i) {
        if ((meas->temperature_valid_bitmap & (1UL << i)) == 0UL) {
            fault->warning_bitmap |= BMS_WARNING_SENSOR_INVALID;
            fault->active_fault_bitmap |= BMS_FAULT_SENSOR_INVALID;
            BMS_FaultSupervisor_SetPrimaryIfEmpty(
                fault,
                BMS_FAULT_CODE_TEMPERATURE_SENSOR_FAULT);
            continue;
        }

        const int16_t temp_dC = meas->temperature_dC[i];

        if (temp_dC > warning_dC) {
            fault->warning_bitmap |= BMS_WARNING_TEMPERATURE_HIGH;
        }

        if (temp_dC > fault_dC) {
            fault->active_fault_bitmap |= BMS_FAULT_TEMPERATURE_HIGH;
            BMS_FaultSupervisor_SetPrimaryIfEmpty(
                fault,
                BMS_FAULT_CODE_CELL_TEMPERATURE_HIGH);
        }
    }
}

bms_status_t BMS_FaultSupervisor_Init(bms_context_t *ctx)
{
    if (!BMS_Context_IsInitialized(ctx)) {
        return BMS_STATUS_NOT_INITIALIZED;
    }

    ctx->regs.fault.warning_bitmap = 0UL;
    ctx->regs.fault.active_fault_bitmap = 0UL;
    ctx->regs.fault.latched_fault_bitmap = 0UL;
    ctx->regs.fault.primary_fault_code = BMS_FAULT_CODE_NONE;
    ctx->regs.fault.fault_severity = BMS_FAULT_SEVERITY_NONE;
    ctx->regs.fault.event_counter = 0UL;

    return BMS_STATUS_OK;
}

bms_status_t BMS_FaultSupervisor_Update(bms_context_t *ctx)
{
    if (!BMS_Context_IsInitialized(ctx)) {
        return BMS_STATUS_NOT_INITIALIZED;
    }

    bms_fault_reg_t next = ctx->regs.fault;
    const uint32_t previous_active = ctx->regs.fault.active_fault_bitmap;

    next.warning_bitmap = 0UL;
    next.active_fault_bitmap = 0UL;
    next.primary_fault_code = BMS_FAULT_CODE_NONE;
    next.fault_severity = BMS_FAULT_SEVERITY_NONE;

    BMS_FaultSupervisor_CheckSensorValidity(&ctx->regs.acq, &next);
    BMS_FaultSupervisor_CheckVoltage(&ctx->regs.meas, &ctx->regs.cfg, &next);
    BMS_FaultSupervisor_CheckCurrent(&ctx->regs.meas, &ctx->regs.cfg, &next);
    BMS_FaultSupervisor_CheckTemperature(&ctx->regs.meas, &ctx->regs.cfg, &next);

    if (next.active_fault_bitmap != 0UL) {
        next.fault_severity = BMS_FAULT_SEVERITY_CRITICAL;
        next.latched_fault_bitmap |= next.active_fault_bitmap;
        ctx->regs.sys.system_mode = BMS_SYSTEM_MODE_FAULT_ACTIVE;
    } else if (next.warning_bitmap != 0UL) {
        next.fault_severity = BMS_FAULT_SEVERITY_WARNING;
        ctx->regs.sys.system_mode = BMS_SYSTEM_MODE_ACTIVE_MONITORING;
    } else {
        ctx->regs.sys.system_mode = BMS_SYSTEM_MODE_ACTIVE_MONITORING;
    }

    if (next.active_fault_bitmap != previous_active) {
        next.event_counter++;
    }

    ctx->regs.fault = next;

    return BMS_STATUS_OK;
}
