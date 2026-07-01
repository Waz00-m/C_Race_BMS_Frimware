#include "bms_i2c_hal.h"

#include <Arduino.h>
#include <Wire.h>

#include "bms_board_config.h"

#ifndef BMS_I2C_SDA_PIN
#define BMS_I2C_SDA_PIN (21)
#endif

#ifndef BMS_I2C_SCL_PIN
#define BMS_I2C_SCL_PIN (22)
#endif

#ifndef BMS_I2C_CLOCK_HZ
#define BMS_I2C_CLOCK_HZ (400000UL)
#endif

static bool g_i2c_initialized = false;

bms_status_t BMS_HAL_I2C_Init(void)
{
    if (g_i2c_initialized) {
        return BMS_STATUS_OK;
    }

    if (!Wire.begin(BMS_I2C_SDA_PIN, BMS_I2C_SCL_PIN)) {
        return BMS_STATUS_HAL_ERROR;
    }

    Wire.setClock(BMS_I2C_CLOCK_HZ);
    g_i2c_initialized = true;

    return BMS_STATUS_OK;
}

bms_status_t BMS_HAL_I2C_WriteRegister16(
    uint8_t device_address,
    uint8_t register_address,
    uint16_t value)
{
    if (!g_i2c_initialized) {
        const bms_status_t status = BMS_HAL_I2C_Init();
        if (status != BMS_STATUS_OK) {
            return status;
        }
    }

    Wire.beginTransmission(device_address);
    Wire.write(register_address);
    Wire.write((uint8_t)((value >> 8U) & 0xFFU));
    Wire.write((uint8_t)(value & 0xFFU));

    const uint8_t result = Wire.endTransmission();
    if (result != 0U) {
        return BMS_STATUS_HAL_ERROR;
    }

    return BMS_STATUS_OK;
}

bms_status_t BMS_HAL_I2C_ReadRegister16(
    uint8_t device_address,
    uint8_t register_address,
    uint16_t *value)
{
    if (value == NULL) {
        return BMS_STATUS_INVALID_ARGUMENT;
    }

    if (!g_i2c_initialized) {
        const bms_status_t status = BMS_HAL_I2C_Init();
        if (status != BMS_STATUS_OK) {
            return status;
        }
    }

    Wire.beginTransmission(device_address);
    Wire.write(register_address);

    const uint8_t write_result = Wire.endTransmission(false);
    if (write_result != 0U) {
        return BMS_STATUS_HAL_ERROR;
    }

    const uint8_t received = Wire.requestFrom(
        (uint8_t)device_address,
        (uint8_t)2U);
    if (received != 2U) {
        return BMS_STATUS_NO_DATA;
    }

    const uint16_t high = (uint16_t)Wire.read();
    const uint16_t low = (uint16_t)Wire.read();
    *value = (uint16_t)((high << 8U) | low);

    return BMS_STATUS_OK;
}
