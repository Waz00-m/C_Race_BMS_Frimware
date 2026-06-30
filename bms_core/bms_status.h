#ifndef BMS_STATUS_H
#define BMS_STATUS_H

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    BMS_STATUS_OK = 0,
    BMS_STATUS_ERROR = -1,
    BMS_STATUS_INVALID_ARGUMENT = -2,
    BMS_STATUS_NOT_INITIALIZED = -3,
    BMS_STATUS_ALREADY_INITIALIZED = -4,
    BMS_STATUS_HAL_ERROR = -5,
    BMS_STATUS_CONFIG_ERROR = -6,
    BMS_STATUS_NO_DATA = -7
} bms_status_t;

static inline const char *BMS_Status_ToString(bms_status_t status)
{
    switch (status) {
    case BMS_STATUS_OK:
        return "OK";
    case BMS_STATUS_ERROR:
        return "ERROR";
    case BMS_STATUS_INVALID_ARGUMENT:
        return "INVALID_ARGUMENT";
    case BMS_STATUS_NOT_INITIALIZED:
        return "NOT_INITIALIZED";
    case BMS_STATUS_ALREADY_INITIALIZED:
        return "ALREADY_INITIALIZED";
    case BMS_STATUS_HAL_ERROR:
        return "HAL_ERROR";
    case BMS_STATUS_CONFIG_ERROR:
        return "CONFIG_ERROR";
    case BMS_STATUS_NO_DATA:
        return "NO_DATA";
    default:
        return "UNKNOWN_STATUS";
    }
}

#ifdef __cplusplus
}
#endif

#endif
