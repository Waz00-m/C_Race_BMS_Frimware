#ifndef BMS_REGISTERS_H
#define BMS_REGISTERS_H

#include "bms_types.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    bms_system_mode_t system_mode;
    uint8_t sub_state;
    uint32_t uptime_ms;
    bms_wake_cause_t wake_cause;
    bms_scheduler_status_t scheduler_status;
    uint32_t reset_reason;
} bms_sys_reg_t;

typedef struct {
    uint16_t raw_adc[BMS_ACQ_CHANNEL_COUNT];
    uint16_t adc_mV[BMS_ACQ_CHANNEL_COUNT];
    uint32_t filter_ready_bitmap;
    uint32_t sample_counter[BMS_ACQ_CHANNEL_COUNT];
    uint32_t sensor_valid_bitmap;
    uint32_t stuck_bitmap;
} bms_acq_reg_t;

typedef struct {
    uint32_t tap_mV[BMS_NUM_CELLS];
    uint32_t tap_valid_bitmap;
    uint16_t cell_mV[BMS_NUM_CELLS];
    uint32_t cell_valid_bitmap;
    uint32_t voltage_invalid_reason_bitmap;
    uint32_t pack_mV;
    int32_t current_mA;
    uint32_t current_abs_mA;
    bool current_valid;
    uint32_t current_invalid_reason_bitmap;
    int16_t temperature_dC[BMS_NUM_TEMPERATURES];
    uint32_t temperature_valid_bitmap;
    uint32_t temperature_invalid_reason_bitmap;
    uint8_t min_cell_index;
    uint8_t max_cell_index;
    uint16_t cell_delta_mV;
} bms_meas_reg_t;

typedef struct {
    uint16_t soc_dP;
    uint16_t soh_dP;
    uint16_t dod_dP;
    int32_t c_rate_mC;
    int32_t power_W;
    uint32_t used_mAh;
    uint32_t used_mWh;
    bool soc_valid;
    bool soh_valid;
    bms_soc_method_t soc_method;
    bms_soh_method_t soh_method;
} bms_est_reg_t;

typedef struct {
    uint32_t warning_bitmap;
    uint32_t active_fault_bitmap;
    uint32_t latched_fault_bitmap;
    uint16_t primary_fault_code;
    bms_fault_severity_t fault_severity;
    uint32_t event_counter;
} bms_fault_reg_t;

typedef struct {
    bool diagnostic_active;
    uint16_t command_id;
    uint16_t target_service;
    uint16_t test_id;
    uint16_t response_code;
    uint32_t override_token;
    bool adc_injection_enabled;
    uint32_t adc_injection_bitmap;
    uint16_t adc_injection_mV[BMS_ACQ_CHANNEL_COUNT];
} bms_diag_reg_t;

typedef struct {
    bool sleep_allowed;
    bms_sleep_decision_t decision;
    bms_sleep_reason_t reason;
    uint32_t evaluated_count;
    uint32_t last_eval_uptime_ms;
    uint32_t load_active_threshold_mA;
} bms_sleep_reg_t;

typedef struct {
    uint32_t config_version;
    uint32_t config_crc;
    bool config_dirty;
    uint32_t voltage_divider_ratio_ppm[BMS_NUM_CELLS];
    int32_t voltage_gain_ppm[BMS_NUM_CELLS];
    int32_t voltage_offset_mV[BMS_NUM_CELLS];
    int32_t ntc_adc_gain_ppm[BMS_NUM_TEMPERATURES];
    int16_t ntc_adc_offset_mV[BMS_NUM_TEMPERATURES];
    uint16_t voltage_thresholds_mV[BMS_THRESHOLD_COUNT];
    int32_t current_thresholds_mA[BMS_THRESHOLD_COUNT];
    int16_t temperature_thresholds_dC[BMS_THRESHOLD_COUNT];
    uint16_t sample_period_ms[BMS_SAMPLE_PERIOD_COUNT];
    int32_t calibration_gain_ppm[BMS_CALIBRATION_CHANNEL_COUNT];
    int32_t calibration_offset[BMS_CALIBRATION_CHANNEL_COUNT];
    uint32_t battery_capacity_mAh;
} bms_cfg_reg_t;

typedef struct {
    bms_sys_reg_t sys;
    bms_acq_reg_t acq;
    bms_meas_reg_t meas;
    bms_est_reg_t est;
    bms_fault_reg_t fault;
    bms_diag_reg_t diag;
    bms_sleep_reg_t sleep;
    bms_cfg_reg_t cfg;
} bms_register_map_t;

#ifdef __cplusplus
}
#endif

#endif
