#ifndef BMS_BOARD_CONFIG_H
#define BMS_BOARD_CONFIG_H

#include "bms_types.h"

#define BMS_CURRENT_SENSOR_ANALOG_INA240 (1U)
#define BMS_CURRENT_SENSOR_INA226 (2U)

#ifdef BMS_BOARD_CONFIG_FILE

#include BMS_BOARD_CONFIG_FILE

#else

#if defined(BMS_BOARD_PROTOTYPE0_PROFILE0) && \
    defined(BMS_BOARD_PROTOTYPE0_PROFILE1)
#error "Select only one BMS board profile."
#endif

#if !defined(BMS_BOARD_PROTOTYPE0_PROFILE0) && \
    !defined(BMS_BOARD_PROTOTYPE0_PROFILE1)
#define BMS_BOARD_PROTOTYPE0_PROFILE0 1
#endif

#if defined(BMS_BOARD_PROTOTYPE0_PROFILE1)
#include "prototype0_profile1/bms_board_profile.h"
#elif defined(BMS_BOARD_PROTOTYPE0_PROFILE0)
#include "prototype0_profile0/bms_board_profile.h"
#else
#error "No supported BMS board profile selected."
#endif

#endif

#ifndef BMS_BOARD_NAME
#error "Selected BMS board profile did not define BMS_BOARD_NAME."
#endif

#ifndef BMS_CURRENT_SENSOR_TYPE
#error "Selected BMS board profile did not define BMS_CURRENT_SENSOR_TYPE."
#endif

#endif
