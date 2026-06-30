#ifndef BMS_UART_HAL_H
#define BMS_UART_HAL_H

#include <stdint.h>

#include "bms_status.h"

#ifdef __cplusplus
extern "C" {
#endif

bms_status_t BMS_HAL_UART_Init(void);
bms_status_t BMS_HAL_UART_Send(const char *text);
bms_status_t BMS_HAL_UART_ReadByte(uint8_t *byte);

#ifdef __cplusplus
}
#endif

#endif
