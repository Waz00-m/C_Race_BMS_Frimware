#include "bms_nvm_hal.h"

#include <Preferences.h>

static const char *BMS_NVM_NAMESPACE = "bms";
static const char *BMS_NVM_CONFIG_KEY = "cfg";

static Preferences g_preferences;
static bool g_nvm_initialized = false;

bms_status_t BMS_HAL_NVM_Init(void)
{
    if (g_nvm_initialized) {
        return BMS_STATUS_OK;
    }

    if (!g_preferences.begin(BMS_NVM_NAMESPACE, false)) {
        return BMS_STATUS_HAL_ERROR;
    }

    g_nvm_initialized = true;

    return BMS_STATUS_OK;
}

bms_status_t BMS_HAL_NVM_ReadConfig(void *data, uint16_t length)
{
    if ((data == nullptr) || (length == 0U)) {
        return BMS_STATUS_INVALID_ARGUMENT;
    }

    bms_status_t status = BMS_HAL_NVM_Init();
    if (status != BMS_STATUS_OK) {
        return status;
    }

    const size_t stored_length = g_preferences.getBytesLength(
        BMS_NVM_CONFIG_KEY);
    if (stored_length == 0U) {
        return BMS_STATUS_NO_DATA;
    }

    if (stored_length != (size_t)length) {
        return BMS_STATUS_CONFIG_ERROR;
    }

    const size_t read_length = g_preferences.getBytes(
        BMS_NVM_CONFIG_KEY,
        data,
        length);
    if (read_length != (size_t)length) {
        return BMS_STATUS_HAL_ERROR;
    }

    return BMS_STATUS_OK;
}

bms_status_t BMS_HAL_NVM_WriteConfig(const void *data, uint16_t length)
{
    if ((data == nullptr) || (length == 0U)) {
        return BMS_STATUS_INVALID_ARGUMENT;
    }

    bms_status_t status = BMS_HAL_NVM_Init();
    if (status != BMS_STATUS_OK) {
        return status;
    }

    const size_t written_length = g_preferences.putBytes(
        BMS_NVM_CONFIG_KEY,
        data,
        length);
    if (written_length != (size_t)length) {
        return BMS_STATUS_HAL_ERROR;
    }

    return BMS_STATUS_OK;
}

bms_status_t BMS_HAL_NVM_EraseConfig(void)
{
    bms_status_t status = BMS_HAL_NVM_Init();
    if (status != BMS_STATUS_OK) {
        return status;
    }

    g_preferences.remove(BMS_NVM_CONFIG_KEY);

    return BMS_STATUS_OK;
}
