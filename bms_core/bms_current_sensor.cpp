#include "bms_current_sensor.h"

#include <math.h>
#include <stdint.h>

#include "bms_board_config.h"
#include "bms_i2c_hal.h"
#include "bms_measurement_config.h"

#ifndef BMS_INA226_I2C_ADDRESS
#define BMS_INA226_I2C_ADDRESS (0x40U)
#endif

#ifndef BMS_INA226_SHUNT_OHM
#define BMS_INA226_SHUNT_OHM (0.00025f)
#endif

#ifndef BMS_INA226_MAX_EXPECTED_CURRENT_MA
#define BMS_INA226_MAX_EXPECTED_CURRENT_MA (120000L)
#endif

#ifndef BMS_INA226_CURRENT_LSB_UA
#define BMS_INA226_CURRENT_LSB_UA (0.0f)
#endif

#ifndef BMS_INA226_CONFIG_REGISTER
#define BMS_INA226_CONFIG_REGISTER (0x4127U)
#endif

static const uint8_t BMS_INA226_REG_CONFIG = 0x00U;
static const uint8_t BMS_INA226_REG_CURRENT = 0x04U;
static const uint8_t BMS_INA226_REG_CALIBRATION = 0x05U;

static bool g_current_filter_ready = false;
static float g_filtered_current_mA = 0.0f;
static bool g_current_no_load_latched = true;
static bool g_ina226_ready = false;

static void BMS_CurrentSensor_ResetFilter(void)
{
    g_current_filter_ready = false;
    g_filtered_current_mA = 0.0f;
    g_current_no_load_latched = true;
}

static int32_t BMS_CurrentSensor_LimitMilliAmps(float current_mA)
{
    if (current_mA > 2147483000.0f) {
        return INT32_MAX;
    }

    if (current_mA < -2147483000.0f) {
        return INT32_MIN;
    }

    return (int32_t)lroundf(current_mA);
}

static float BMS_CurrentSensor_ApplyAdcCorrection(uint16_t adc_mV)
{
    return ((float)adc_mV * BMS_CURRENT_ADC_GAIN_CORRECTION) +
           BMS_CURRENT_ADC_OFFSET_MV;
}

static bool BMS_CurrentSensor_AdcIsValid(float corrected_adc_mV)
{
    return (corrected_adc_mV >= (float)BMS_ADC_LOW_VALID_MV) &&
           (corrected_adc_mV <= (float)BMS_CURRENT_ADC_HIGH_VALID_MV);
}

static float BMS_CurrentSensor_ConvertIna240MilliAmps(float corrected_adc_mV)
{
    const float delta_mV = corrected_adc_mV - BMS_CURRENT_ZERO_MV;
    return delta_mV / (BMS_CURRENT_INA_GAIN * BMS_CURRENT_SHUNT_OHM);
}

static float BMS_CurrentSensor_ConvertAcs772MilliAmps(float corrected_adc_mV)
{
    const float delta_mV = corrected_adc_mV - BMS_CURRENT_ZERO_MV;
    return (delta_mV * 1000.0f * BMS_CURRENT_SENSOR_POLARITY) /
           BMS_CURRENT_HALL_SENSITIVITY_MV_PER_A;
}

static float BMS_CurrentSensor_ConvertRawMilliAmps(float corrected_adc_mV)
{
#if BMS_CURRENT_SENSOR_TYPE == BMS_CURRENT_SENSOR_ANALOG_ACS772
    return BMS_CurrentSensor_ConvertAcs772MilliAmps(corrected_adc_mV);
#elif BMS_CURRENT_SENSOR_TYPE == BMS_CURRENT_SENSOR_ANALOG_INA240
    return BMS_CurrentSensor_ConvertIna240MilliAmps(corrected_adc_mV);
#elif BMS_CURRENT_SENSOR_TYPE == BMS_CURRENT_SENSOR_INA226
    (void)corrected_adc_mV;
    return 0.0f;
#else
#error "Unsupported BMS_CURRENT_SENSOR_TYPE."
#endif
}

static int32_t BMS_CurrentSensor_FilterAndApplyDeadband(float current_mA)
{
    current_mA = (current_mA * BMS_CURRENT_READING_GAIN) +
                 BMS_CURRENT_OFFSET_MA;

    if (!g_current_filter_ready) {
        g_filtered_current_mA = current_mA;
        g_current_filter_ready = true;
    } else {
        g_filtered_current_mA =
            g_filtered_current_mA +
            (BMS_CURRENT_SMOOTH_ALPHA *
             (current_mA - g_filtered_current_mA));
    }

    const float abs_current_mA = fabsf(g_filtered_current_mA);

    if (g_current_no_load_latched) {
        if (abs_current_mA > (float)BMS_CURRENT_NOLOAD_ENTER_MA) {
            g_current_no_load_latched = false;
        }
    } else {
        if (abs_current_mA < (float)BMS_CURRENT_NOLOAD_EXIT_MA) {
            g_current_no_load_latched = true;
        }
    }

    if (g_current_no_load_latched) {
        return 0L;
    }

    return BMS_CurrentSensor_LimitMilliAmps(g_filtered_current_mA);
}

static float BMS_CurrentSensor_Ina226CurrentLsbMilliAmps(void)
{
    if (BMS_INA226_CURRENT_LSB_UA > 0.0f) {
        return BMS_INA226_CURRENT_LSB_UA / 1000.0f;
    }

    return (float)BMS_INA226_MAX_EXPECTED_CURRENT_MA / 32768.0f;
}

static bms_status_t BMS_CurrentSensor_ConfigureIna226(void)
{
#if BMS_CURRENT_SENSOR_TYPE == BMS_CURRENT_SENSOR_INA226
    const float current_lsb_mA =
        BMS_CurrentSensor_Ina226CurrentLsbMilliAmps();
    const float current_lsb_A = current_lsb_mA / 1000.0f;

    if ((BMS_INA226_SHUNT_OHM <= 0.0f) ||
        (current_lsb_A <= 0.0f)) {
        g_ina226_ready = false;
        return BMS_STATUS_CONFIG_ERROR;
    }

    const float calibration_f =
        0.00512f / (current_lsb_A * BMS_INA226_SHUNT_OHM);
    uint32_t calibration = (uint32_t)lroundf(calibration_f);

    if (calibration == 0UL) {
        calibration = 1UL;
    }

    if (calibration > UINT16_MAX) {
        calibration = UINT16_MAX;
    }

    bms_status_t status = BMS_HAL_I2C_WriteRegister16(
        (uint8_t)BMS_INA226_I2C_ADDRESS,
        BMS_INA226_REG_CONFIG,
        (uint16_t)BMS_INA226_CONFIG_REGISTER);
    if (status != BMS_STATUS_OK) {
        g_ina226_ready = false;
        return status;
    }

    status = BMS_HAL_I2C_WriteRegister16(
        (uint8_t)BMS_INA226_I2C_ADDRESS,
        BMS_INA226_REG_CALIBRATION,
        (uint16_t)calibration);
    if (status != BMS_STATUS_OK) {
        g_ina226_ready = false;
        return status;
    }

    g_ina226_ready = true;
    return BMS_STATUS_OK;
#else
    g_ina226_ready = false;
    return BMS_STATUS_OK;
#endif
}

bms_status_t BMS_CurrentSensor_Init(void)
{
    BMS_CurrentSensor_ResetFilter();

#if BMS_CURRENT_SENSOR_TYPE == BMS_CURRENT_SENSOR_INA226
    const bms_status_t status = BMS_CurrentSensor_ConfigureIna226();
    if (status == BMS_STATUS_CONFIG_ERROR) {
        return status;
    }
#endif

    return BMS_STATUS_OK;
}

bool BMS_CurrentSensor_UsesAdc(void)
{
#if BMS_CURRENT_SENSOR_TYPE == BMS_CURRENT_SENSOR_INA226
    return false;
#else
    return true;
#endif
}

bms_status_t BMS_CurrentSensor_ConvertAdcMilliVolts(
    uint16_t adc_mV,
    int32_t *current_mA,
    bool *current_valid)
{
    if ((current_mA == NULL) || (current_valid == NULL)) {
        return BMS_STATUS_INVALID_ARGUMENT;
    }

#if BMS_CURRENT_SENSOR_TYPE == BMS_CURRENT_SENSOR_INA226
    (void)adc_mV;
    *current_mA = 0L;
    *current_valid = false;
    return BMS_STATUS_CONFIG_ERROR;
#else
    const float corrected_adc_mV =
        BMS_CurrentSensor_ApplyAdcCorrection(adc_mV);

    if (!BMS_CurrentSensor_AdcIsValid(corrected_adc_mV)) {
        *current_valid = false;
        *current_mA = 0L;
        BMS_CurrentSensor_ResetFilter();
        return BMS_STATUS_OK;
    }

    const float raw_current_mA =
        BMS_CurrentSensor_ConvertRawMilliAmps(corrected_adc_mV);

    *current_mA = BMS_CurrentSensor_FilterAndApplyDeadband(raw_current_mA);
    *current_valid = true;

    return BMS_STATUS_OK;
#endif
}

bms_status_t BMS_CurrentSensor_ReadDigitalMilliAmps(
    int32_t *current_mA,
    bool *current_valid)
{
    if ((current_mA == NULL) || (current_valid == NULL)) {
        return BMS_STATUS_INVALID_ARGUMENT;
    }

    *current_mA = 0L;
    *current_valid = false;

#if BMS_CURRENT_SENSOR_TYPE == BMS_CURRENT_SENSOR_INA226
    if (!g_ina226_ready) {
        const bms_status_t config_status = BMS_CurrentSensor_ConfigureIna226();
        if (config_status != BMS_STATUS_OK) {
            BMS_CurrentSensor_ResetFilter();
            return BMS_STATUS_OK;
        }
    }

    uint16_t current_reg = 0U;
    const bms_status_t status = BMS_HAL_I2C_ReadRegister16(
        (uint8_t)BMS_INA226_I2C_ADDRESS,
        BMS_INA226_REG_CURRENT,
        &current_reg);
    if (status != BMS_STATUS_OK) {
        g_ina226_ready = false;
        BMS_CurrentSensor_ResetFilter();
        return BMS_STATUS_OK;
    }

    const int16_t raw_current = (int16_t)current_reg;
    const float current_lsb_mA =
        BMS_CurrentSensor_Ina226CurrentLsbMilliAmps();
    const float raw_current_mA =
        (float)raw_current *
        current_lsb_mA *
        BMS_CURRENT_SENSOR_POLARITY;

    *current_mA = BMS_CurrentSensor_FilterAndApplyDeadband(raw_current_mA);
    *current_valid = true;

    return BMS_STATUS_OK;
#else
    return BMS_STATUS_CONFIG_ERROR;
#endif
}
