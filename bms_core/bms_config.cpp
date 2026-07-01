#include "bms_config.h"

#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include "bms_fault_codes.h"
#include "bms_nvm_hal.h"

#define BMS_CONFIG_RECORD_MAGIC (0x424D5343UL)
#define BMS_CONFIG_RECORD_VERSION (1UL)

typedef struct {
    uint32_t magic;
    uint32_t record_version;
    uint32_t config_version;
    uint32_t config_size;
    bms_cfg_reg_t cfg;
    uint32_t crc;
} bms_config_record_t;

static uint32_t BMS_Config_CrcUpdate(
    uint32_t hash,
    const uint8_t *data,
    size_t length)
{
    for (size_t i = 0U; i < length; ++i) {
        hash ^= (uint32_t)data[i];
        hash *= 16777619UL;
    }

    return hash;
}

uint32_t BMS_Config_CalculateCrc(const bms_cfg_reg_t *cfg)
{
    if (cfg == NULL) {
        return 0UL;
    }

    const uint8_t *bytes = (const uint8_t *)cfg;
    const size_t crc_offset = offsetof(bms_cfg_reg_t, config_crc);
    uint32_t hash = 2166136261UL;

    hash = BMS_Config_CrcUpdate(hash, bytes, crc_offset);
    hash = BMS_Config_CrcUpdate(
        hash,
        bytes + crc_offset + sizeof(cfg->config_crc),
        sizeof(*cfg) - crc_offset - sizeof(cfg->config_crc));

    return hash;
}

void BMS_Config_RefreshCrc(bms_context_t *ctx)
{
    if (!BMS_Context_IsInitialized(ctx)) {
        return;
    }

    ctx->regs.cfg.config_crc = BMS_Config_CalculateCrc(&ctx->regs.cfg);
}

static bool BMS_Config_RecordIsValid(const bms_config_record_t *record)
{
    if (record == NULL) {
        return false;
    }

    if (record->magic != BMS_CONFIG_RECORD_MAGIC) {
        return false;
    }

    if (record->record_version != BMS_CONFIG_RECORD_VERSION) {
        return false;
    }

    if (record->config_version != BMS_CONFIG_VERSION) {
        return false;
    }

    if (record->config_size != sizeof(bms_cfg_reg_t)) {
        return false;
    }

    if (record->crc != BMS_Config_CalculateCrc(&record->cfg)) {
        return false;
    }

    if (record->cfg.config_crc != record->crc) {
        return false;
    }

    return true;
}

static bool BMS_Config_ValueInRange(
    int32_t value,
    int32_t min_value,
    int32_t max_value)
{
    return (value >= min_value) && (value <= max_value);
}

static bms_status_t BMS_Config_CheckEditableContext(bms_context_t *ctx)
{
    if (!BMS_Context_IsInitialized(ctx)) {
        return BMS_STATUS_NOT_INITIALIZED;
    }

    return BMS_STATUS_OK;
}

static void BMS_Config_MarkDirty(bms_context_t *ctx)
{
    ctx->regs.cfg.config_dirty = true;
    BMS_Config_RefreshCrc(ctx);
}

bms_status_t BMS_Config_Load(bms_context_t *ctx)
{
    if (!BMS_Context_IsInitialized(ctx)) {
        return BMS_STATUS_NOT_INITIALIZED;
    }

    bms_config_record_t record;
    memset(&record, 0, sizeof(record));

    const bms_status_t status = BMS_HAL_NVM_ReadConfig(
        &record,
        (uint16_t)sizeof(record));
    if (status != BMS_STATUS_OK) {
        return status;
    }

    if (!BMS_Config_RecordIsValid(&record)) {
        return BMS_STATUS_CONFIG_ERROR;
    }

    ctx->regs.cfg = record.cfg;
    ctx->regs.cfg.config_dirty = false;
    BMS_Config_RefreshCrc(ctx);

    return BMS_STATUS_OK;
}

bms_status_t BMS_Config_Save(bms_context_t *ctx)
{
    if (!BMS_Context_IsInitialized(ctx)) {
        return BMS_STATUS_NOT_INITIALIZED;
    }

    BMS_Config_RefreshCrc(ctx);
    ctx->regs.cfg.config_dirty = false;
    BMS_Config_RefreshCrc(ctx);

    bms_config_record_t record;
    memset(&record, 0, sizeof(record));
    record.magic = BMS_CONFIG_RECORD_MAGIC;
    record.record_version = BMS_CONFIG_RECORD_VERSION;
    record.config_version = BMS_CONFIG_VERSION;
    record.config_size = sizeof(bms_cfg_reg_t);
    record.cfg = ctx->regs.cfg;
    record.crc = ctx->regs.cfg.config_crc;

    return BMS_HAL_NVM_WriteConfig(&record, (uint16_t)sizeof(record));
}

bms_status_t BMS_Config_EraseStored(void)
{
    return BMS_HAL_NVM_EraseConfig();
}

bms_status_t BMS_Config_ResetToDefaults(bms_context_t *ctx)
{
    if (!BMS_Context_IsInitialized(ctx)) {
        return BMS_STATUS_NOT_INITIALIZED;
    }

    bms_status_t status = BMS_HAL_NVM_EraseConfig();
    if (status != BMS_STATUS_OK) {
        return status;
    }

    status = BMS_Context_ResetConfigDefaults(ctx);
    if (status != BMS_STATUS_OK) {
        return status;
    }

    BMS_Config_RefreshCrc(ctx);

    return BMS_STATUS_OK;
}

bms_status_t BMS_Config_SetVoltageRatioPpm(
    bms_context_t *ctx,
    uint8_t index,
    uint32_t value)
{
    bms_status_t status = BMS_Config_CheckEditableContext(ctx);
    if (status != BMS_STATUS_OK) {
        return status;
    }

    if ((index >= BMS_NUM_CELLS) ||
        (value < 100000UL) ||
        (value > 50000000UL)) {
        return BMS_STATUS_CONFIG_ERROR;
    }

    ctx->regs.cfg.voltage_divider_ratio_ppm[index] = value;
    BMS_Config_MarkDirty(ctx);

    return BMS_STATUS_OK;
}

bms_status_t BMS_Config_SetVoltageGainPpm(
    bms_context_t *ctx,
    uint8_t index,
    int32_t value)
{
    bms_status_t status = BMS_Config_CheckEditableContext(ctx);
    if (status != BMS_STATUS_OK) {
        return status;
    }

    if ((index >= BMS_NUM_CELLS) ||
        !BMS_Config_ValueInRange(value, 100000L, 5000000L)) {
        return BMS_STATUS_CONFIG_ERROR;
    }

    ctx->regs.cfg.voltage_gain_ppm[index] = value;
    BMS_Config_MarkDirty(ctx);

    return BMS_STATUS_OK;
}

bms_status_t BMS_Config_SetVoltageOffsetMv(
    bms_context_t *ctx,
    uint8_t index,
    int32_t value)
{
    bms_status_t status = BMS_Config_CheckEditableContext(ctx);
    if (status != BMS_STATUS_OK) {
        return status;
    }

    if ((index >= BMS_NUM_CELLS) ||
        !BMS_Config_ValueInRange(value, -2000L, 2000L)) {
        return BMS_STATUS_CONFIG_ERROR;
    }

    ctx->regs.cfg.voltage_offset_mV[index] = value;
    BMS_Config_MarkDirty(ctx);

    return BMS_STATUS_OK;
}

bms_status_t BMS_Config_SetNtcGainPpm(
    bms_context_t *ctx,
    uint8_t index,
    int32_t value)
{
    bms_status_t status = BMS_Config_CheckEditableContext(ctx);
    if (status != BMS_STATUS_OK) {
        return status;
    }

    if ((index >= BMS_NUM_TEMPERATURES) ||
        !BMS_Config_ValueInRange(value, 100000L, 5000000L)) {
        return BMS_STATUS_CONFIG_ERROR;
    }

    ctx->regs.cfg.ntc_adc_gain_ppm[index] = value;
    BMS_Config_MarkDirty(ctx);

    return BMS_STATUS_OK;
}

bms_status_t BMS_Config_SetNtcOffsetMv(
    bms_context_t *ctx,
    uint8_t index,
    int32_t value)
{
    bms_status_t status = BMS_Config_CheckEditableContext(ctx);
    if (status != BMS_STATUS_OK) {
        return status;
    }

    if ((index >= BMS_NUM_TEMPERATURES) ||
        (value < -1000L) ||
        (value > 1000L)) {
        return BMS_STATUS_CONFIG_ERROR;
    }

    ctx->regs.cfg.ntc_adc_offset_mV[index] = (int16_t)value;
    BMS_Config_MarkDirty(ctx);

    return BMS_STATUS_OK;
}

bms_status_t BMS_Config_SetCapacityMah(
    bms_context_t *ctx,
    uint32_t value)
{
    bms_status_t status = BMS_Config_CheckEditableContext(ctx);
    if (status != BMS_STATUS_OK) {
        return status;
    }

    if ((value < 100UL) || (value > 1000000UL)) {
        return BMS_STATUS_CONFIG_ERROR;
    }

    ctx->regs.cfg.battery_capacity_mAh = value;
    BMS_Config_MarkDirty(ctx);

    return BMS_STATUS_OK;
}

bms_status_t BMS_Config_SetThreshold(
    bms_context_t *ctx,
    bms_config_threshold_id_t threshold,
    int32_t value)
{
    bms_status_t status = BMS_Config_CheckEditableContext(ctx);
    if (status != BMS_STATUS_OK) {
        return status;
    }

    bms_cfg_reg_t *cfg = &ctx->regs.cfg;

    switch (threshold) {
    case BMS_CONFIG_THRESHOLD_CELL_LOW_WARN:
        if (!BMS_Config_ValueInRange(value, 1000L, 5000L)) {
            return BMS_STATUS_CONFIG_ERROR;
        }
        cfg->voltage_thresholds_mV[
            BMS_VOLTAGE_THRESHOLD_CELL_LOW_WARNING_MV] = (uint16_t)value;
        break;
    case BMS_CONFIG_THRESHOLD_CELL_LOW_FAULT:
        if (!BMS_Config_ValueInRange(value, 1000L, 5000L)) {
            return BMS_STATUS_CONFIG_ERROR;
        }
        cfg->voltage_thresholds_mV[
            BMS_VOLTAGE_THRESHOLD_CELL_LOW_FAULT_MV] = (uint16_t)value;
        break;
    case BMS_CONFIG_THRESHOLD_CELL_HIGH_WARN:
        if (!BMS_Config_ValueInRange(value, 1000L, 5000L)) {
            return BMS_STATUS_CONFIG_ERROR;
        }
        cfg->voltage_thresholds_mV[
            BMS_VOLTAGE_THRESHOLD_CELL_HIGH_WARNING_MV] = (uint16_t)value;
        break;
    case BMS_CONFIG_THRESHOLD_CELL_HIGH_FAULT:
        if (!BMS_Config_ValueInRange(value, 1000L, 5000L)) {
            return BMS_STATUS_CONFIG_ERROR;
        }
        cfg->voltage_thresholds_mV[
            BMS_VOLTAGE_THRESHOLD_CELL_HIGH_FAULT_MV] = (uint16_t)value;
        break;
    case BMS_CONFIG_THRESHOLD_PACK_LOW_FAULT:
        if (!BMS_Config_ValueInRange(value, 6000L, 60000L)) {
            return BMS_STATUS_CONFIG_ERROR;
        }
        cfg->voltage_thresholds_mV[
            BMS_VOLTAGE_THRESHOLD_PACK_LOW_FAULT_MV] = (uint16_t)value;
        break;
    case BMS_CONFIG_THRESHOLD_PACK_HIGH_FAULT:
        if (!BMS_Config_ValueInRange(value, 6000L, 60000L)) {
            return BMS_STATUS_CONFIG_ERROR;
        }
        cfg->voltage_thresholds_mV[
            BMS_VOLTAGE_THRESHOLD_PACK_HIGH_FAULT_MV] = (uint16_t)value;
        break;
    case BMS_CONFIG_THRESHOLD_CELL_IMBALANCE_WARN:
        if (!BMS_Config_ValueInRange(value, 0L, 1000L)) {
            return BMS_STATUS_CONFIG_ERROR;
        }
        cfg->voltage_thresholds_mV[
            BMS_VOLTAGE_THRESHOLD_CELL_IMBALANCE_WARNING_MV] =
                (uint16_t)value;
        break;
    case BMS_CONFIG_THRESHOLD_OVERCURRENT_WARN:
        if (!BMS_Config_ValueInRange(value, 0L, 500000L)) {
            return BMS_STATUS_CONFIG_ERROR;
        }
        cfg->current_thresholds_mA[
            BMS_CURRENT_THRESHOLD_OVERCURRENT_WARNING_MA] = value;
        break;
    case BMS_CONFIG_THRESHOLD_OVERCURRENT_FAULT:
        if (!BMS_Config_ValueInRange(value, 0L, 500000L)) {
            return BMS_STATUS_CONFIG_ERROR;
        }
        cfg->current_thresholds_mA[
            BMS_CURRENT_THRESHOLD_OVERCURRENT_FAULT_MA] = value;
        break;
    case BMS_CONFIG_THRESHOLD_TEMP_HIGH_WARN:
        if (!BMS_Config_ValueInRange(value, -400L, 1200L)) {
            return BMS_STATUS_CONFIG_ERROR;
        }
        cfg->temperature_thresholds_dC[
            BMS_TEMPERATURE_THRESHOLD_HIGH_WARNING_DC] = (int16_t)value;
        break;
    case BMS_CONFIG_THRESHOLD_TEMP_HIGH_FAULT:
        if (!BMS_Config_ValueInRange(value, -400L, 1200L)) {
            return BMS_STATUS_CONFIG_ERROR;
        }
        cfg->temperature_thresholds_dC[
            BMS_TEMPERATURE_THRESHOLD_HIGH_FAULT_DC] = (int16_t)value;
        break;
    default:
        return BMS_STATUS_INVALID_ARGUMENT;
    }

    BMS_Config_MarkDirty(ctx);

    return BMS_STATUS_OK;
}

bms_status_t BMS_Config_Init(bms_context_t *ctx)
{
    if (!BMS_Context_IsInitialized(ctx)) {
        return BMS_STATUS_NOT_INITIALIZED;
    }

    BMS_Config_RefreshCrc(ctx);

    const bms_status_t nvm_status = BMS_HAL_NVM_Init();
    if (nvm_status != BMS_STATUS_OK) {
        return nvm_status;
    }

    const bms_status_t load_status = BMS_Config_Load(ctx);
    if ((load_status == BMS_STATUS_OK) ||
        (load_status == BMS_STATUS_NO_DATA) ||
        (load_status == BMS_STATUS_CONFIG_ERROR)) {
        return BMS_STATUS_OK;
    }

    return load_status;
}
