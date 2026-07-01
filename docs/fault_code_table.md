# Fault Code Table

This table maps stable BMS fault codes to their meaning and supporting detail
registers. A fault code identifies the fault category; bitmaps and measurement
registers provide the detailed source.

## Fault Codes

| Code | Name | Severity Source | Meaning | Detail Source | Status |
|---|---|---|---|---|---|
| `0x0000` | No fault | `FAULT_REG.fault_severity` | No active primary fault | `FAULT_REG` | Implemented |
| `0x1001` | Cell overvoltage | Fault supervisor | One or more cells exceed high fault threshold | `MEAS_REG.cell_mV[]`, `FAULT_REG.active_fault_bitmap` | Implemented |
| `0x1002` | Cell undervoltage | Fault supervisor | One or more cells are below low fault threshold | `MEAS_REG.cell_mV[]`, `FAULT_REG.active_fault_bitmap` | Implemented |
| `0x1003` | Pack overvoltage | Fault supervisor | Pack voltage exceeds high pack fault threshold | `MEAS_REG.pack_mV` | Implemented |
| `0x1004` | Pack undervoltage | Fault supervisor | Pack voltage is below low pack fault threshold | `MEAS_REG.pack_mV` | Implemented |
| `0x2002` | Discharge overcurrent | Fault supervisor | Absolute current exceeds overcurrent fault threshold | `MEAS_REG.current_abs_mA` | Implemented |
| `0x2003` | Current sensor fault | Fault supervisor | Current sensor invalid or not responding | `MEAS_REG.current_valid` | Implemented |
| `0x3001` | Cell temperature high | Fault supervisor | One or more temperature channels exceed high fault threshold | `MEAS_REG.temperature_dC[]` | Implemented |
| `0x3003` | Temperature sensor fault | Fault supervisor | Temperature channel open, short, or implausible | `MEAS_REG.temperature_valid_bitmap` | Implemented |
| `0x4001` | ADC read failure | Fault supervisor | One or more expected ADC channels are not valid | `ACQ_REG.sensor_valid_bitmap` | Implemented |

## Warning Bitmap

| Bit Mask | Name | Meaning | Detail Source |
|---|---|---|---|
| `0x00000001` | `BMS_WARNING_CELL_LOW` | A cell is below low warning threshold | `MEAS_REG.cell_mV[]` |
| `0x00000002` | `BMS_WARNING_CELL_HIGH` | A cell is above high warning threshold | `MEAS_REG.cell_mV[]` |
| `0x00000004` | `BMS_WARNING_CELL_IMBALANCE` | Cell delta exceeds imbalance warning threshold | `MEAS_REG.cell_delta_mV` |
| `0x00000008` | `BMS_WARNING_OVERCURRENT` | Absolute current exceeds warning threshold | `MEAS_REG.current_abs_mA` |
| `0x00000010` | `BMS_WARNING_TEMPERATURE_HIGH` | A temperature channel exceeds warning threshold | `MEAS_REG.temperature_dC[]` |
| `0x00000020` | `BMS_WARNING_SENSOR_INVALID` | An expected sensor channel is missing or invalid | `ACQ_REG.sensor_valid_bitmap` |

## Active Fault Bitmap

| Bit Mask | Name | Meaning | Detail Source |
|---|---|---|---|
| `0x00000001` | `BMS_FAULT_CELL_UNDERVOLTAGE` | A cell is below low fault threshold | `MEAS_REG.cell_mV[]` |
| `0x00000002` | `BMS_FAULT_CELL_OVERVOLTAGE` | A cell is above high fault threshold | `MEAS_REG.cell_mV[]` |
| `0x00000004` | `BMS_FAULT_PACK_UNDERVOLTAGE` | Pack voltage is below low pack fault threshold | `MEAS_REG.pack_mV` |
| `0x00000008` | `BMS_FAULT_PACK_OVERVOLTAGE` | Pack voltage is above high pack fault threshold | `MEAS_REG.pack_mV` |
| `0x00000010` | `BMS_FAULT_OVERCURRENT` | Absolute current exceeds fault threshold | `MEAS_REG.current_abs_mA` |
| `0x00000020` | `BMS_FAULT_TEMPERATURE_HIGH` | A temperature channel exceeds fault threshold | `MEAS_REG.temperature_dC[]` |
| `0x00000040` | `BMS_FAULT_SENSOR_INVALID` | An expected sensor channel is missing or invalid | `ACQ_REG.sensor_valid_bitmap` |

## Acquisition Valid Bitmap

`ACQ_REG.sensor_valid_bitmap` is not a fault code. It tells which acquisition
channels have valid reads.

For analog-current profiles, the current 11-channel map is:

| Bit | Channel |
|---|---|
| 0 | Cell 1 ADC |
| 1 | Cell 2 ADC |
| 2 | Cell 3 ADC |
| 3 | Cell 4 ADC |
| 4 | Cell 5 ADC |
| 5 | Cell 6 ADC |
| 6 | Current ADC |
| 7 | Temperature 1 ADC |
| 8 | Temperature 2 ADC |
| 9 | Temperature 3 ADC |
| 10 | Temperature 4 ADC |

`0x000007FF` means all 11 channels have valid reads. If a bit is missing, the
primary fault may be `0x4001`, while this bitmap tells which channel caused the
failure.

For INA226 current profiles, the current ADC bit is not expected because current
comes from I2C. In that case, `MEAS_REG.current_valid` is the current-sensor
truth source, and a missing or failed INA226 read maps to primary fault
`0x2003`.
