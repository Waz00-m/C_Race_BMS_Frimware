#include "bms_measurement_validation.h"

#include <stdint.h>
#include <string.h>

#include "bms_adc_hal.h"
#include "bms_current_sensor.h"
#include "bms_measurement_config.h"

#ifndef BMS_VALIDATION_CELL_MIN_MV
#define BMS_VALIDATION_CELL_MIN_MV (500U)
#endif

#ifndef BMS_VALIDATION_CELL_MAX_MV
#define BMS_VALIDATION_CELL_MAX_MV (5000U)
#endif

#ifndef BMS_VALIDATION_CELL_STEP_MAX_MV
#define BMS_VALIDATION_CELL_STEP_MAX_MV (1500U)
#endif

#ifndef BMS_VALIDATION_TAP_STEP_MAX_MV
#define BMS_VALIDATION_TAP_STEP_MAX_MV (6000UL)
#endif

#ifndef BMS_VALIDATION_CURRENT_ABS_MAX_MA
#define BMS_VALIDATION_CURRENT_ABS_MAX_MA (500000UL)
#endif

#ifndef BMS_VALIDATION_STUCK_SAMPLE_LIMIT
#define BMS_VALIDATION_STUCK_SAMPLE_LIMIT (2000U)
#endif

static bool g_previous_voltage_ready = false;
static uint32_t g_previous_tap_mV[BMS_NUM_CELLS];
static uint16_t g_previous_cell_mV[BMS_NUM_CELLS];
static bool g_previous_adc_ready[BMS_ACQ_CHANNEL_COUNT];
static uint16_t g_previous_adc_mV[BMS_ACQ_CHANNEL_COUNT];
static uint16_t g_stuck_count[BMS_ACQ_CHANNEL_COUNT];

uint32_t BMS_MeasurementValidation_AllCellMask(void)
{
    return (1UL << BMS_NUM_CELLS) - 1UL;
}

uint32_t BMS_MeasurementValidation_AllTemperatureMask(void)
{
    return (1UL << BMS_NUM_TEMPERATURES) - 1UL;
}

static bms_adc_channel_t BMS_MeasurementValidation_CellAdcChannel(
    uint8_t cell_index)
{
    return (bms_adc_channel_t)((uint8_t)BMS_ADC_CHANNEL_CELL_1 + cell_index);
}

static bms_adc_channel_t BMS_MeasurementValidation_TempAdcChannel(
    uint8_t temp_index)
{
    return (bms_adc_channel_t)((uint8_t)BMS_ADC_CHANNEL_TEMP_1 + temp_index);
}

static uint32_t BMS_MeasurementValidation_AbsDiffU32(
    uint32_t a,
    uint32_t b)
{
    return (a > b) ? (a - b) : (b - a);
}

static bool BMS_MeasurementValidation_AdcBitIsSet(
    const bms_acq_reg_t *acq,
    bms_adc_channel_t channel)
{
    return (acq->sensor_valid_bitmap & (1UL << (uint8_t)channel)) != 0UL;
}

static bool BMS_MeasurementValidation_UpdateStuck(
    bms_context_t *ctx,
    bms_adc_channel_t channel)
{
    bms_acq_reg_t *acq = &ctx->regs.acq;
    const uint8_t index = (uint8_t)channel;
    const uint16_t adc_mV = acq->adc_mV[index];
    const uint32_t mask = (1UL << index);

    if (ctx->regs.diag.adc_injection_enabled &&
        ((ctx->regs.diag.adc_injection_bitmap & mask) != 0UL)) {
        g_previous_adc_ready[index] = false;
        g_stuck_count[index] = 0U;
        acq->stuck_bitmap &= ~mask;
        return false;
    }

    if (!g_previous_adc_ready[index]) {
        g_previous_adc_ready[index] = true;
        g_previous_adc_mV[index] = adc_mV;
        g_stuck_count[index] = 0U;
        acq->stuck_bitmap &= ~mask;
        return false;
    }

    if (adc_mV == g_previous_adc_mV[index]) {
        if (g_stuck_count[index] < UINT16_MAX) {
            g_stuck_count[index]++;
        }
    } else {
        g_stuck_count[index] = 0U;
        g_previous_adc_mV[index] = adc_mV;
    }

    if (g_stuck_count[index] >= BMS_VALIDATION_STUCK_SAMPLE_LIMIT) {
        acq->stuck_bitmap |= mask;
        return true;
    }

    acq->stuck_bitmap &= ~mask;
    return false;
}

static bool BMS_MeasurementValidation_AdcIsValid(
    bms_context_t *ctx,
    bms_adc_channel_t channel,
    uint16_t high_valid_mV,
    uint32_t *reason)
{
    bool valid = true;
    bms_acq_reg_t *acq = &ctx->regs.acq;
    const uint8_t index = (uint8_t)channel;

    if (!BMS_MeasurementValidation_AdcBitIsSet(acq, channel)) {
        *reason |= BMS_MEAS_VALIDATION_REASON_ADC_MISSING;
        valid = false;
    }

    if ((acq->adc_mV[index] < BMS_ADC_LOW_VALID_MV) ||
        (acq->adc_mV[index] > high_valid_mV)) {
        *reason |= BMS_MEAS_VALIDATION_REASON_ADC_RANGE;
        valid = false;
    }

    if (BMS_MeasurementValidation_UpdateStuck(ctx, channel)) {
        *reason |= BMS_MEAS_VALIDATION_REASON_STUCK_ADC;
        valid = false;
    }

    return valid;
}

static bool BMS_MeasurementValidation_TapInRange(
    uint32_t tap_mV,
    uint8_t cell_index)
{
#if BMS_VOLTAGE_INPUT_MODE == BMS_VOLTAGE_MODE_CUMULATIVE_TAPS
    const uint32_t min_mV =
        (uint32_t)BMS_VALIDATION_CELL_MIN_MV * (uint32_t)(cell_index + 1U);
    const uint32_t max_mV =
        (uint32_t)BMS_VALIDATION_CELL_MAX_MV * (uint32_t)(cell_index + 1U);
#else
    const uint32_t min_mV = BMS_VALIDATION_CELL_MIN_MV;
    const uint32_t max_mV = BMS_VALIDATION_CELL_MAX_MV;
#endif

    return (tap_mV >= min_mV) && (tap_mV <= max_mV);
}

static bool BMS_MeasurementValidation_CellInRange(uint16_t cell_mV)
{
    return (cell_mV >= BMS_VALIDATION_CELL_MIN_MV) &&
           (cell_mV <= BMS_VALIDATION_CELL_MAX_MV);
}

bms_status_t BMS_MeasurementValidation_Init(bms_context_t *ctx)
{
    if (!BMS_Context_IsInitialized(ctx)) {
        return BMS_STATUS_NOT_INITIALIZED;
    }

    memset(g_previous_tap_mV, 0, sizeof(g_previous_tap_mV));
    memset(g_previous_cell_mV, 0, sizeof(g_previous_cell_mV));
    memset(g_previous_adc_ready, 0, sizeof(g_previous_adc_ready));
    memset(g_previous_adc_mV, 0, sizeof(g_previous_adc_mV));
    memset(g_stuck_count, 0, sizeof(g_stuck_count));
    g_previous_voltage_ready = false;

    ctx->regs.acq.stuck_bitmap = 0UL;
    ctx->regs.meas.tap_valid_bitmap = 0UL;
    ctx->regs.meas.cell_valid_bitmap = 0UL;
    ctx->regs.meas.voltage_invalid_reason_bitmap =
        BMS_MEAS_VALIDATION_REASON_ADC_MISSING;
    ctx->regs.meas.current_invalid_reason_bitmap =
        BMS_MEAS_VALIDATION_REASON_CURRENT_SENSOR;
    ctx->regs.meas.temperature_invalid_reason_bitmap =
        BMS_MEAS_VALIDATION_REASON_TEMPERATURE_SENSOR;

    return BMS_STATUS_OK;
}

bms_status_t BMS_MeasurementValidation_UpdateVoltage(bms_context_t *ctx)
{
    if (!BMS_Context_IsInitialized(ctx)) {
        return BMS_STATUS_NOT_INITIALIZED;
    }

    bms_meas_reg_t *meas = &ctx->regs.meas;
    uint32_t tap_valid = 0UL;
    uint32_t cell_valid = 0UL;
    uint32_t reason = BMS_MEAS_VALIDATION_REASON_NONE;

    for (uint8_t i = 0U; i < BMS_NUM_CELLS; ++i) {
        bool valid = BMS_MeasurementValidation_AdcIsValid(
            ctx,
            BMS_MeasurementValidation_CellAdcChannel(i),
            BMS_ADC_HIGH_VALID_MV,
            &reason);

        if (!BMS_MeasurementValidation_TapInRange(meas->tap_mV[i], i)) {
            reason |= BMS_MEAS_VALIDATION_REASON_TAP_RANGE;
            valid = false;
        }

        if (g_previous_voltage_ready &&
            (BMS_MeasurementValidation_AbsDiffU32(
                 meas->tap_mV[i],
                 g_previous_tap_mV[i]) > BMS_VALIDATION_TAP_STEP_MAX_MV)) {
            reason |= BMS_MEAS_VALIDATION_REASON_TAP_STEP;
            valid = false;
        }

        if (valid) {
            tap_valid |= (1UL << i);
        }
    }

    for (uint8_t i = 0U; i < BMS_NUM_CELLS; ++i) {
        bool valid = (tap_valid & (1UL << i)) != 0UL;

#if BMS_VOLTAGE_INPUT_MODE == BMS_VOLTAGE_MODE_CUMULATIVE_TAPS
        if (i > 0U) {
            if (meas->tap_mV[i] < meas->tap_mV[i - 1U]) {
                reason |= BMS_MEAS_VALIDATION_REASON_TAP_ORDER;
                valid = false;
            }

            if ((tap_valid & (1UL << (i - 1U))) == 0UL) {
                valid = false;
            }
        }
#endif

        if (!BMS_MeasurementValidation_CellInRange(meas->cell_mV[i])) {
            reason |= BMS_MEAS_VALIDATION_REASON_CELL_RANGE;
            valid = false;
        }

        if (g_previous_voltage_ready &&
            (BMS_MeasurementValidation_AbsDiffU32(
                 meas->cell_mV[i],
                 g_previous_cell_mV[i]) > BMS_VALIDATION_CELL_STEP_MAX_MV)) {
            reason |= BMS_MEAS_VALIDATION_REASON_CELL_STEP;
            valid = false;
        }

        if (valid) {
            cell_valid |= (1UL << i);
        }
    }

    for (uint8_t i = 0U; i < BMS_NUM_CELLS; ++i) {
        g_previous_tap_mV[i] = meas->tap_mV[i];
        g_previous_cell_mV[i] = meas->cell_mV[i];
    }
    g_previous_voltage_ready = true;

    meas->tap_valid_bitmap = tap_valid;
    meas->cell_valid_bitmap = cell_valid;
    meas->voltage_invalid_reason_bitmap = reason;

    return BMS_STATUS_OK;
}

bms_status_t BMS_MeasurementValidation_UpdateCurrent(bms_context_t *ctx)
{
    if (!BMS_Context_IsInitialized(ctx)) {
        return BMS_STATUS_NOT_INITIALIZED;
    }

    bms_meas_reg_t *meas = &ctx->regs.meas;
    uint32_t reason = BMS_MEAS_VALIDATION_REASON_NONE;

    if (!meas->current_valid) {
        reason |= BMS_MEAS_VALIDATION_REASON_CURRENT_SENSOR;
    }

    if (meas->current_abs_mA > BMS_VALIDATION_CURRENT_ABS_MAX_MA) {
        reason |= BMS_MEAS_VALIDATION_REASON_CURRENT_RANGE;
        meas->current_valid = false;
    }

    if (BMS_CurrentSensor_UsesAdc()) {
        if (!BMS_MeasurementValidation_AdcIsValid(
                ctx,
                BMS_ADC_CHANNEL_CURRENT,
                BMS_CURRENT_ADC_HIGH_VALID_MV,
                &reason)) {
            meas->current_valid = false;
        }
    }

    meas->current_invalid_reason_bitmap = reason;

    return BMS_STATUS_OK;
}

bms_status_t BMS_MeasurementValidation_UpdateTemperature(bms_context_t *ctx)
{
    if (!BMS_Context_IsInitialized(ctx)) {
        return BMS_STATUS_NOT_INITIALIZED;
    }

    bms_meas_reg_t *meas = &ctx->regs.meas;
    const uint32_t original_valid = meas->temperature_valid_bitmap;
    uint32_t valid_bitmap = 0UL;
    uint32_t reason = BMS_MEAS_VALIDATION_REASON_NONE;

    for (uint8_t i = 0U; i < BMS_NUM_TEMPERATURES; ++i) {
        bool valid = BMS_MeasurementValidation_AdcIsValid(
            ctx,
            BMS_MeasurementValidation_TempAdcChannel(i),
            BMS_ADC_HIGH_VALID_MV,
            &reason);

        if ((original_valid & (1UL << i)) == 0UL) {
            reason |= BMS_MEAS_VALIDATION_REASON_TEMPERATURE_SENSOR;
            valid = false;
        }

        if ((meas->temperature_dC[i] < BMS_TEMP_SENSOR_MIN_VALID_DC) ||
            (meas->temperature_dC[i] > BMS_TEMP_SENSOR_MAX_VALID_DC)) {
            reason |= BMS_MEAS_VALIDATION_REASON_TEMPERATURE_RANGE;
            valid = false;
        }

        if (valid) {
            valid_bitmap |= (1UL << i);
        }
    }

    meas->temperature_valid_bitmap = valid_bitmap;
    meas->temperature_invalid_reason_bitmap = reason;

    return BMS_STATUS_OK;
}
