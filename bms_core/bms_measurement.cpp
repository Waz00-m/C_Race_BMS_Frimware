#include "bms_measurement.h"

#include <math.h>
#include <stdint.h>

#include "bms_adc_hal.h"
#include "bms_current_sensor.h"
#include "bms_measurement_config.h"

static bms_adc_channel_t BMS_Measurement_CellAdcChannel(uint8_t cell_index)
{
    return (bms_adc_channel_t)((uint8_t)BMS_ADC_CHANNEL_CELL_1 + cell_index);
}

static bms_adc_channel_t BMS_Measurement_TempAdcChannel(uint8_t temp_index)
{
    return (bms_adc_channel_t)((uint8_t)BMS_ADC_CHANNEL_TEMP_1 + temp_index);
}

static void BMS_Measurement_RecalculateCellSummary(bms_meas_reg_t *meas)
{
    uint16_t min_mV = meas->cell_mV[0U];
    uint16_t max_mV = meas->cell_mV[0U];
    uint8_t min_index = 0U;
    uint8_t max_index = 0U;
    uint32_t pack_mV = 0UL;

    for (uint8_t i = 0U; i < BMS_NUM_CELLS; ++i) {
        const uint16_t cell_mV = meas->cell_mV[i];
        pack_mV += cell_mV;

        if (cell_mV < min_mV) {
            min_mV = cell_mV;
            min_index = i;
        }

        if (cell_mV > max_mV) {
            max_mV = cell_mV;
            max_index = i;
        }
    }

    meas->pack_mV = pack_mV;
    meas->min_cell_index = min_index;
    meas->max_cell_index = max_index;
    meas->cell_delta_mV = (uint16_t)(max_mV - min_mV);
}

static bms_status_t BMS_Measurement_ReadAdc(
    bms_context_t *ctx,
    bms_adc_channel_t channel,
    uint16_t *adc_mV)
{
    uint16_t raw = 0U;
    uint16_t millivolts = 0U;

    bms_status_t status = BMS_HAL_ADC_ReadRaw(channel, &raw);
    if (status != BMS_STATUS_OK) {
        return status;
    }

    status = BMS_HAL_ADC_ReadMilliVolts(channel, &millivolts);
    if (status != BMS_STATUS_OK) {
        return status;
    }

    const uint8_t index = (uint8_t)channel;
    ctx->regs.acq.raw_adc[index] = raw;
    ctx->regs.acq.adc_mV[index] = millivolts;
    ctx->regs.acq.sample_counter[index]++;
    ctx->regs.acq.sensor_valid_bitmap |= (1UL << index);
    ctx->regs.acq.filter_ready_bitmap |= (1UL << index);

    if (adc_mV != NULL) {
        *adc_mV = millivolts;
    }

    return BMS_STATUS_OK;
}

static uint16_t BMS_Measurement_ConvertTapToMilliVolts(
    uint16_t adc_mV,
    uint8_t cell_index,
    const bms_cfg_reg_t *cfg)
{
    uint32_t ratio_ppm = BMS_DEFAULT_VOLTAGE_DIVIDER_RATIO_PPM[cell_index];
    int32_t gain_ppm = BMS_DEFAULT_VOLTAGE_GAIN_PPM[cell_index];
    int32_t offset_mV = BMS_DEFAULT_VOLTAGE_OFFSET_MV[cell_index];

    if (cfg != NULL) {
        if (cfg->voltage_divider_ratio_ppm[cell_index] != 0UL) {
            ratio_ppm = cfg->voltage_divider_ratio_ppm[cell_index];
        }
        if (cfg->voltage_gain_ppm[cell_index] != 0L) {
            gain_ppm = cfg->voltage_gain_ppm[cell_index];
        }
        offset_mV = cfg->voltage_offset_mV[cell_index];
    }

    int64_t tap_mV = (int64_t)adc_mV * (int64_t)ratio_ppm;

    tap_mV = tap_mV / 1000000LL;
    tap_mV = (tap_mV * (int64_t)gain_ppm) / 1000000LL;
    tap_mV += offset_mV;

    if (tap_mV < 0LL) {
        return 0U;
    }

    if (tap_mV > UINT16_MAX) {
        return UINT16_MAX;
    }

    return (uint16_t)tap_mV;
}

static uint32_t BMS_Measurement_AllTemperatureValidMask(void)
{
    return (1UL << BMS_NUM_TEMPERATURES) - 1UL;
}

static bool BMS_Measurement_ConvertTemperatureDeciC(
    uint16_t adc_mV,
    uint8_t temp_index,
    const bms_cfg_reg_t *cfg,
    int16_t *temperature_dC)
{
    if (temperature_dC == NULL) {
        return false;
    }

    float adc = (float)adc_mV;

    if (temp_index < BMS_NUM_TEMPERATURES) {
        int32_t gain_ppm = BMS_NTC_ADC_GAIN_PPM[temp_index];
        int16_t offset_mV = BMS_NTC_ADC_OFFSET_MV[temp_index];

        if (cfg != NULL) {
            if (cfg->ntc_adc_gain_ppm[temp_index] != 0L) {
                gain_ppm = cfg->ntc_adc_gain_ppm[temp_index];
            }
            offset_mV = cfg->ntc_adc_offset_mV[temp_index];
        }

        adc = (adc * (float)gain_ppm) / 1000000.0f;
        adc += (float)offset_mV;
    }

    if ((adc < (float)BMS_ADC_LOW_VALID_MV) ||
        (adc > (float)BMS_ADC_HIGH_VALID_MV)) {
        *temperature_dC = BMS_TEMPERATURE_INVALID_DC;
        return false;
    }

    if (adc < 1.0f) {
        adc = 1.0f;
    }

    if (adc > (BMS_NTC_SUPPLY_MV - 1.0f)) {
        adc = BMS_NTC_SUPPLY_MV - 1.0f;
    }

    float ntc_ohm = 0.0f;

#if BMS_NTC_TO_GROUND
    ntc_ohm = BMS_NTC_FIXED_RESISTOR_OHM * adc /
              (BMS_NTC_SUPPLY_MV - adc);
#else
    ntc_ohm = BMS_NTC_FIXED_RESISTOR_OHM *
              (BMS_NTC_SUPPLY_MV - adc) / adc;
#endif

    if ((ntc_ohm < BMS_NTC_MIN_VALID_OHM) ||
        (ntc_ohm > BMS_NTC_MAX_VALID_OHM)) {
        *temperature_dC = BMS_TEMPERATURE_INVALID_DC;
        return false;
    }

    const float inv_temp =
        (1.0f / BMS_NTC_NOMINAL_TEMP_K) +
        (logf(ntc_ohm / BMS_NTC_NOMINAL_RESISTANCE_OHM) / BMS_NTC_BETA);
    const float temp_k = 1.0f / inv_temp;
    const float temp_c = temp_k - 273.15f;
    const int16_t next_dC = (int16_t)lroundf(temp_c * 10.0f);

    if ((next_dC < BMS_TEMP_SENSOR_MIN_VALID_DC) ||
        (next_dC > BMS_TEMP_SENSOR_MAX_VALID_DC)) {
        *temperature_dC = BMS_TEMPERATURE_INVALID_DC;
        return false;
    }

    *temperature_dC = next_dC;
    return true;
}

bms_status_t BMS_Measurement_Init(bms_context_t *ctx)
{
    if (!BMS_Context_IsInitialized(ctx)) {
        return BMS_STATUS_NOT_INITIALIZED;
    }

    return BMS_CurrentSensor_Init();
}

bms_status_t BMS_Measurement_UpdateFakeCurrent(bms_context_t *ctx)
{
    if (!BMS_Context_IsInitialized(ctx)) {
        return BMS_STATUS_NOT_INITIALIZED;
    }

    bms_meas_reg_t *meas = &ctx->regs.meas;
    meas->current_mA = BMS_FAKE_CURRENT_MA;
    meas->current_abs_mA = 0UL;
    meas->current_valid = true;

    return BMS_STATUS_OK;
}

bms_status_t BMS_Measurement_UpdateFakeVoltage(bms_context_t *ctx)
{
    if (!BMS_Context_IsInitialized(ctx)) {
        return BMS_STATUS_NOT_INITIALIZED;
    }

    bms_meas_reg_t *meas = &ctx->regs.meas;

    for (uint8_t i = 0U; i < BMS_NUM_CELLS; ++i) {
        meas->cell_mV[i] = BMS_FAKE_CELL_MV;
    }

    BMS_Measurement_RecalculateCellSummary(meas);

    return BMS_STATUS_OK;
}

bms_status_t BMS_Measurement_UpdateFakeTemperature(bms_context_t *ctx)
{
    if (!BMS_Context_IsInitialized(ctx)) {
        return BMS_STATUS_NOT_INITIALIZED;
    }

    bms_meas_reg_t *meas = &ctx->regs.meas;

    for (uint8_t i = 0U; i < BMS_NUM_TEMPERATURES; ++i) {
        meas->temperature_dC[i] = BMS_FAKE_TEMPERATURE_DC;
    }
    meas->temperature_valid_bitmap = BMS_Measurement_AllTemperatureValidMask();

    return BMS_STATUS_OK;
}

bms_status_t BMS_Measurement_UpdateCurrent(bms_context_t *ctx)
{
#if BMS_MEASUREMENT_BACKEND_REAL_ADC
    if (!BMS_Context_IsInitialized(ctx)) {
        return BMS_STATUS_NOT_INITIALIZED;
    }

    bool current_valid = false;
    int32_t current_mA = 0L;

    if (BMS_CurrentSensor_UsesAdc()) {
        uint16_t adc_mV = 0U;
        bms_status_t status = BMS_Measurement_ReadAdc(
            ctx,
            BMS_ADC_CHANNEL_CURRENT,
            &adc_mV);
        if (status != BMS_STATUS_OK) {
            return status;
        }

        status = BMS_CurrentSensor_ConvertAdcMilliVolts(
            adc_mV,
            &current_mA,
            &current_valid);
        if (status != BMS_STATUS_OK) {
            return status;
        }
    } else {
        const bms_status_t status =
            BMS_CurrentSensor_ReadDigitalMilliAmps(
                &current_mA,
                &current_valid);
        if (status != BMS_STATUS_OK) {
            return status;
        }
    }

    ctx->regs.meas.current_mA = current_mA;
    ctx->regs.meas.current_abs_mA =
        (current_mA < 0L) ? (uint32_t)(-current_mA) : (uint32_t)current_mA;
    ctx->regs.meas.current_valid = current_valid;

    return BMS_STATUS_OK;
#else
    return BMS_Measurement_UpdateFakeCurrent(ctx);
#endif
}

bms_status_t BMS_Measurement_UpdateVoltage(bms_context_t *ctx)
{
#if BMS_MEASUREMENT_BACKEND_REAL_ADC
    if (!BMS_Context_IsInitialized(ctx)) {
        return BMS_STATUS_NOT_INITIALIZED;
    }

    uint16_t tap_mV[BMS_NUM_CELLS] = {0U};

    for (uint8_t i = 0U; i < BMS_NUM_CELLS; ++i) {
        uint16_t adc_mV = 0U;
        const bms_status_t status = BMS_Measurement_ReadAdc(
            ctx,
            BMS_Measurement_CellAdcChannel(i),
            &adc_mV);
        if (status != BMS_STATUS_OK) {
            return status;
        }

        tap_mV[i] = BMS_Measurement_ConvertTapToMilliVolts(
            adc_mV,
            i,
            &ctx->regs.cfg);
    }

    bms_meas_reg_t *meas = &ctx->regs.meas;

    for (uint8_t i = 0U; i < BMS_NUM_CELLS; ++i) {
        meas->tap_mV[i] = tap_mV[i];

#if BMS_VOLTAGE_INPUT_MODE == BMS_VOLTAGE_MODE_CUMULATIVE_TAPS
        if (i == 0U) {
            meas->cell_mV[i] = tap_mV[i];
        } else if (tap_mV[i] >= tap_mV[i - 1U]) {
            meas->cell_mV[i] = (uint16_t)(tap_mV[i] - tap_mV[i - 1U]);
        } else {
            meas->cell_mV[i] = 0U;
        }
#else
        meas->cell_mV[i] = tap_mV[i];
#endif
    }

    BMS_Measurement_RecalculateCellSummary(meas);

    return BMS_STATUS_OK;
#else
    return BMS_Measurement_UpdateFakeVoltage(ctx);
#endif
}

bms_status_t BMS_Measurement_UpdateTemperature(bms_context_t *ctx)
{
#if BMS_MEASUREMENT_BACKEND_REAL_ADC
    if (!BMS_Context_IsInitialized(ctx)) {
        return BMS_STATUS_NOT_INITIALIZED;
    }

    bms_meas_reg_t *meas = &ctx->regs.meas;
    meas->temperature_valid_bitmap = 0UL;

    for (uint8_t i = 0U; i < BMS_NUM_TEMPERATURES; ++i) {
        uint16_t adc_mV = 0U;
        const bms_status_t status = BMS_Measurement_ReadAdc(
            ctx,
            BMS_Measurement_TempAdcChannel(i),
            &adc_mV);
        if (status != BMS_STATUS_OK) {
            return status;
        }

        int16_t temperature_dC = BMS_TEMPERATURE_INVALID_DC;
        if (BMS_Measurement_ConvertTemperatureDeciC(
                adc_mV,
                i,
                &ctx->regs.cfg,
                &temperature_dC)) {
            meas->temperature_valid_bitmap |= (1UL << i);
        }
        meas->temperature_dC[i] = temperature_dC;
    }

    return BMS_STATUS_OK;
#else
    return BMS_Measurement_UpdateFakeTemperature(ctx);
#endif
}
