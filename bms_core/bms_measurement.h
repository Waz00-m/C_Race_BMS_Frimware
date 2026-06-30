#ifndef BMS_MEASUREMENT_H
#define BMS_MEASUREMENT_H

#include "bms_context.h"

#ifdef __cplusplus
extern "C" {
#endif

#define BMS_FAKE_CELL_MV (4200U)
#define BMS_FAKE_CURRENT_MA (0L)
#define BMS_FAKE_TEMPERATURE_DC (250)

bms_status_t BMS_Measurement_Init(bms_context_t *ctx);
bms_status_t BMS_Measurement_UpdateCurrent(bms_context_t *ctx);
bms_status_t BMS_Measurement_UpdateVoltage(bms_context_t *ctx);
bms_status_t BMS_Measurement_UpdateTemperature(bms_context_t *ctx);
bms_status_t BMS_Measurement_UpdateFakeCurrent(bms_context_t *ctx);
bms_status_t BMS_Measurement_UpdateFakeVoltage(bms_context_t *ctx);
bms_status_t BMS_Measurement_UpdateFakeTemperature(bms_context_t *ctx);

#ifdef __cplusplus
}
#endif

#endif
