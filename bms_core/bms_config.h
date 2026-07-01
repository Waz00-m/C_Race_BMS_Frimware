#ifndef BMS_CONFIG_H
#define BMS_CONFIG_H

#include "bms_context.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    BMS_CONFIG_THRESHOLD_CELL_LOW_WARN = 0,
    BMS_CONFIG_THRESHOLD_CELL_LOW_FAULT,
    BMS_CONFIG_THRESHOLD_CELL_HIGH_WARN,
    BMS_CONFIG_THRESHOLD_CELL_HIGH_FAULT,
    BMS_CONFIG_THRESHOLD_PACK_LOW_FAULT,
    BMS_CONFIG_THRESHOLD_PACK_HIGH_FAULT,
    BMS_CONFIG_THRESHOLD_CELL_IMBALANCE_WARN,
    BMS_CONFIG_THRESHOLD_OVERCURRENT_WARN,
    BMS_CONFIG_THRESHOLD_OVERCURRENT_FAULT,
    BMS_CONFIG_THRESHOLD_TEMP_HIGH_WARN,
    BMS_CONFIG_THRESHOLD_TEMP_HIGH_FAULT
} bms_config_threshold_id_t;

bms_status_t BMS_Config_Init(bms_context_t *ctx);
bms_status_t BMS_Config_Load(bms_context_t *ctx);
bms_status_t BMS_Config_Save(bms_context_t *ctx);
bms_status_t BMS_Config_ResetToDefaults(bms_context_t *ctx);
bms_status_t BMS_Config_EraseStored(void);
uint32_t BMS_Config_CalculateCrc(const bms_cfg_reg_t *cfg);
void BMS_Config_RefreshCrc(bms_context_t *ctx);
bms_status_t BMS_Config_SetVoltageRatioPpm(
    bms_context_t *ctx,
    uint8_t index,
    uint32_t value);
bms_status_t BMS_Config_SetVoltageGainPpm(
    bms_context_t *ctx,
    uint8_t index,
    int32_t value);
bms_status_t BMS_Config_SetVoltageOffsetMv(
    bms_context_t *ctx,
    uint8_t index,
    int32_t value);
bms_status_t BMS_Config_SetNtcGainPpm(
    bms_context_t *ctx,
    uint8_t index,
    int32_t value);
bms_status_t BMS_Config_SetNtcOffsetMv(
    bms_context_t *ctx,
    uint8_t index,
    int32_t value);
bms_status_t BMS_Config_SetCapacityMah(
    bms_context_t *ctx,
    uint32_t value);
bms_status_t BMS_Config_SetThreshold(
    bms_context_t *ctx,
    bms_config_threshold_id_t threshold,
    int32_t value);

#ifdef __cplusplus
}
#endif

#endif
