#ifndef BMS_DIAGNOSTIC_H
#define BMS_DIAGNOSTIC_H

#include "bms_context.h"

#ifdef __cplusplus
extern "C" {
#endif

#define BMS_DIAGNOSTIC_COMMAND_BUFFER_SIZE (128U)

typedef enum {
    BMS_DIAG_COMMAND_NONE = 0,
    BMS_DIAG_COMMAND_HELP,
    BMS_DIAG_COMMAND_GET_SNAPSHOT,
    BMS_DIAG_COMMAND_GET_VOLT,
    BMS_DIAG_COMMAND_GET_CURRENT,
    BMS_DIAG_COMMAND_GET_TEMP,
    BMS_DIAG_COMMAND_GET_FAULT,
    BMS_DIAG_COMMAND_GET_SLEEP,
    BMS_DIAG_COMMAND_GET_TAPS,
    BMS_DIAG_COMMAND_GET_CFG,
    BMS_DIAG_COMMAND_GET_INJECT,
    BMS_DIAG_COMMAND_CFG_SET,
    BMS_DIAG_COMMAND_CFG_SAVE,
    BMS_DIAG_COMMAND_CFG_LOAD,
    BMS_DIAG_COMMAND_CFG_RESET,
    BMS_DIAG_COMMAND_ADC_INJECT
} bms_diag_command_id_t;

typedef enum {
    BMS_DIAG_RESPONSE_OK = 0,
    BMS_DIAG_RESPONSE_INVALID_COMMAND = 1,
    BMS_DIAG_RESPONSE_BUFFER_OVERFLOW = 2
} bms_diag_response_code_t;

typedef struct {
    bool initialized;
    char command_buffer[BMS_DIAGNOSTIC_COMMAND_BUFFER_SIZE];
    uint8_t command_length;
} bms_diagnostic_t;

bms_status_t BMS_Diagnostic_Init(bms_diagnostic_t *diag, bms_context_t *ctx);
bms_status_t BMS_Diagnostic_Poll(bms_diagnostic_t *diag, bms_context_t *ctx);

#ifdef __cplusplus
}
#endif

#endif
