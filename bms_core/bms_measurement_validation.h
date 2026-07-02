#ifndef BMS_MEASUREMENT_VALIDATION_H
#define BMS_MEASUREMENT_VALIDATION_H

#include "bms_context.h"

#ifdef __cplusplus
extern "C" {
#endif

enum {
    BMS_MEAS_VALIDATION_REASON_NONE = 0UL,
    BMS_MEAS_VALIDATION_REASON_ADC_MISSING = (1UL << 0),
    BMS_MEAS_VALIDATION_REASON_ADC_RANGE = (1UL << 1),
    BMS_MEAS_VALIDATION_REASON_TAP_RANGE = (1UL << 2),
    BMS_MEAS_VALIDATION_REASON_TAP_ORDER = (1UL << 3),
    BMS_MEAS_VALIDATION_REASON_CELL_RANGE = (1UL << 4),
    BMS_MEAS_VALIDATION_REASON_TAP_STEP = (1UL << 5),
    BMS_MEAS_VALIDATION_REASON_CELL_STEP = (1UL << 6),
    BMS_MEAS_VALIDATION_REASON_STUCK_ADC = (1UL << 7),
    BMS_MEAS_VALIDATION_REASON_CURRENT_SENSOR = (1UL << 8),
    BMS_MEAS_VALIDATION_REASON_CURRENT_RANGE = (1UL << 9),
    BMS_MEAS_VALIDATION_REASON_TEMPERATURE_SENSOR = (1UL << 10),
    BMS_MEAS_VALIDATION_REASON_TEMPERATURE_RANGE = (1UL << 11)
};

bms_status_t BMS_MeasurementValidation_Init(bms_context_t *ctx);
bms_status_t BMS_MeasurementValidation_UpdateVoltage(bms_context_t *ctx);
bms_status_t BMS_MeasurementValidation_UpdateCurrent(bms_context_t *ctx);
bms_status_t BMS_MeasurementValidation_UpdateTemperature(bms_context_t *ctx);
uint32_t BMS_MeasurementValidation_AllCellMask(void);
uint32_t BMS_MeasurementValidation_AllTemperatureMask(void);

#ifdef __cplusplus
}
#endif

#endif
