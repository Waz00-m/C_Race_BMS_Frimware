# Sensor Backends

Stage 11 starts the sensor backend layer. The goal is to keep measurement
orchestration portable while allowing different sensor-specific conversion
paths.

## Current Sensor Backends

Current sensor type is selected in the board profile:

```cpp
#define BMS_CURRENT_SENSOR_TYPE BMS_CURRENT_SENSOR_ANALOG_INA240
```

Supported now:

```cpp
BMS_CURRENT_SENSOR_ANALOG_INA240
BMS_CURRENT_SENSOR_ANALOG_ACS772
BMS_CURRENT_SENSOR_INA226
```

The conversion implementation lives in:

```text
bms_core/bms_current_sensor.cpp
```

For analog current sensors, the measurement service reads the ADC channel, then
asks the current-sensor backend to convert ADC millivolts into milliamps. For
INA226, the current-sensor backend reads the current register through the I2C
HAL.

## INA240 Analog Path

The INA240 path uses:

```cpp
BMS_CURRENT_ZERO_MV
BMS_CURRENT_SHUNT_OHM
BMS_CURRENT_INA_GAIN
```

Formula:

```text
current_mA = (adc_mV - zero_mV) / (ina_gain * shunt_ohm)
```

## ACS772 Analog Hall Path

The ACS772 path uses:

```cpp
BMS_CURRENT_ZERO_MV
BMS_CURRENT_HALL_SENSITIVITY_MV_PER_A
BMS_CURRENT_SENSOR_POLARITY
```

Formula:

```text
current_mA =
    (adc_mV - zero_mV) * 1000 * polarity / sensitivity_mV_per_A
```

ACS772 has multiple current ranges, so the sensitivity must be set for the
actual part used on the board.

Example sensitivities:

```text
10 mV/A
20 mV/A
40 mV/A
```

Check the exact device marking/datasheet before trusting current values.

## Shared Analog Current Processing

Both analog current backends use the shared post-processing values:

```cpp
BMS_CURRENT_ADC_HIGH_VALID_MV
BMS_CURRENT_ADC_GAIN_CORRECTION
BMS_CURRENT_ADC_OFFSET_MV
BMS_CURRENT_READING_GAIN
BMS_CURRENT_OFFSET_MA
BMS_CURRENT_SMOOTH_ALPHA
BMS_CURRENT_NOLOAD_ENTER_MA
BMS_CURRENT_NOLOAD_EXIT_MA
```

## INA226 Digital Path

The INA226 path uses:

```cpp
BMS_INA226_I2C_ADDRESS
BMS_INA226_SHUNT_OHM
BMS_INA226_MAX_EXPECTED_CURRENT_MA
BMS_INA226_CONFIG_REGISTER
```

The backend computes the INA226 calibration register from the selected shunt
resistance and expected current range:

```text
current_lsb_A = max_expected_current_A / 32768
calibration = 0.00512 / (current_lsb_A * shunt_ohm)
current_mA = signed_current_register * current_lsb_mA * polarity
```

`BMS_INA226_CURRENT_LSB_UA` can be defined by a board profile when a custom LSB
is wanted. If it is left at zero, the backend derives the LSB from
`BMS_INA226_MAX_EXPECTED_CURRENT_MA`.

INA226 failures do not stop the scheduler. If the I2C device is absent or a
read fails, the current backend reports `current_valid = false`. The fault
supervisor then reports the current sensor fault path through `0x2003`.

## Future Backends

AFE devices such as LTC6811 should be added as separate voltage/current backend
modules instead of changing the BMS core state machine or fault supervisor.
