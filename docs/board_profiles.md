# Board Profiles

Stage 9 introduces board profiles so hardware values are not edited directly in
the portable core.

## Active Board

The active board profile is selected in `platformio.ini`:

```ini
build_flags =
    -D BMS_BOARD_PROTOTYPE0_PROFILE0
```

Current active profile:

```text
BMS_BOARD_PROTOTYPE0_PROFILE0
```

This is the calibrated Prototype-0 ESP32 board using:

- six cumulative voltage divider tap inputs
- analog INA240 current sensing on ESP32 ADC
- four 10k NTC thermistors
- SSD1306 OLED on ESP32 I2C

## Profile Files

```text
bms_boards/
  bms_board_config.h
  prototype0_common/
    bms_prototype0_common.h
  prototype0_profile0/
    bms_board_profile.h
  prototype0_profile1/
    bms_board_profile.h
```

`bms_board_config.h` selects exactly one built-in profile, or includes an
external generated profile when `BMS_BOARD_CONFIG_FILE` is provided.

`prototype0_common/bms_prototype0_common.h` owns values shared by the
Prototype-0 family:

- voltage divider ratios
- voltage gain/offset correction
- thermistor beta/circuit constants
- ESP32 ADC pins
- shared I2C pins and bus speed
- OLED pins and display limits

`prototype0_profile0/bms_board_profile.h` selects the analog INA240 current
path.

`prototype0_profile1/bms_board_profile.h` selects the INA226 digital current
path on the shared I2C bus.

## Changing Voltage Divider Values

For another board with the same cumulative tap approach but different resistor
values, copy a profile and update:

```cpp
BMS_DEFAULT_VOLTAGE_DIVIDER_RATIO_PPM[]
BMS_DEFAULT_VOLTAGE_GAIN_PPM[]
BMS_DEFAULT_VOLTAGE_OFFSET_MV[]
```

The ratio is stored in parts per million:

```text
ratio_ppm = actual_tap_voltage / adc_voltage * 1000000
```

## Changing The Current Sensor

Profile0 uses:

```cpp
#define BMS_CURRENT_SENSOR_TYPE BMS_CURRENT_SENSOR_ANALOG_INA240
```

and the analog current constants:

```cpp
BMS_CURRENT_ZERO_MV
BMS_CURRENT_SHUNT_OHM
BMS_CURRENT_INA_GAIN
BMS_CURRENT_READING_GAIN
BMS_CURRENT_OFFSET_MA
```

Analog ACS772 Hall sensors can be selected with:

```cpp
#define BMS_CURRENT_SENSOR_TYPE BMS_CURRENT_SENSOR_ANALOG_ACS772
```

and:

```cpp
BMS_CURRENT_ZERO_MV
BMS_CURRENT_HALL_SENSITIVITY_MV_PER_A
BMS_CURRENT_SENSOR_POLARITY
```

Profile1 uses:

```cpp
#define BMS_CURRENT_SENSOR_TYPE BMS_CURRENT_SENSOR_INA226
```

and:

```cpp
BMS_INA226_I2C_ADDRESS
BMS_INA226_SHUNT_OHM
BMS_INA226_MAX_EXPECTED_CURRENT_MA
BMS_INA226_CONFIG_REGISTER
```

The INA226 backend reads current through I2C instead of the ESP32 ADC current
channel. If the INA226 is absent or not responding, the firmware keeps running
and reports `MEAS_REG.current_valid = false`, allowing the fault supervisor to
raise the current sensor fault path.

## Changing Thermistor Values

For a different NTC part or divider:

```cpp
BMS_NTC_FIXED_RESISTOR_OHM
BMS_NTC_NOMINAL_RESISTANCE_OHM
BMS_NTC_BETA
BMS_NTC_TO_GROUND
BMS_NTC_ADC_GAIN_PPM[]
BMS_NTC_ADC_OFFSET_MV[]
```

The current Profile0 values are the calibrated Prototype-0 defaults.

## Generated Profiles

Stage 10 adds `bms_board_configurator.py`, which can generate custom profiles
under:

```text
bms_boards/generated/
```

Generated builds use:

```ini
-D BMS_BOARD_CONFIG_FILE=\"generated/<profile_folder>/bms_board_profile.h\"
```

The generated `platformio.user.ini` is a local user file. It is ignored by Git,
but generated board profile folders may be committed if they should be shared.
