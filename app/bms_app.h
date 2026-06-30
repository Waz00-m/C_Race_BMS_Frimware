#ifndef BMS_APP_H
#define BMS_APP_H

#include "bms_context.h"
#include "bms_status.h"

#ifdef __cplusplus
extern "C" {
#endif

bms_status_t BMS_App_Init(void);
void BMS_App_Run(void);
const bms_context_t *BMS_App_GetContext(void);

#ifdef __cplusplus
}
#endif

#endif
