#ifndef BMS_DISPLAY_HAL_H
#define BMS_DISPLAY_HAL_H

#include "bms_register_snapshot.h"
#include "bms_status.h"

#ifdef __cplusplus
extern "C" {
#endif

bms_status_t BMS_HAL_Display_Init(void);
bms_status_t BMS_HAL_Display_PollInput(void);
bms_status_t BMS_HAL_Display_Update(const bms_register_snapshot_t *snapshot);

#ifdef __cplusplus
}
#endif

#endif
