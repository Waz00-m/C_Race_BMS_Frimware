# Measurement Validation

Stage 15 adds the first measurement truth layer. The goal is to make validity
visible before fault decisions consume measured values.

## Runtime Fields

Voltage validation now writes:

```text
MEAS_REG.tap_valid_bitmap
MEAS_REG.cell_valid_bitmap
MEAS_REG.voltage_invalid_reason_bitmap
```

Current validation uses:

```text
MEAS_REG.current_valid
MEAS_REG.current_invalid_reason_bitmap
```

Temperature validation uses:

```text
MEAS_REG.temperature_valid_bitmap
MEAS_REG.temperature_invalid_reason_bitmap
```

Acquisition stuck-channel detection writes:

```text
ACQ_REG.stuck_bitmap
```

When diagnostic ADC injection is enabled for a channel, that channel is skipped
by stuck-ADC detection. The injected value is still range-checked and converted
normally, but holding a deliberate test value constant should not itself create
a `STUCK_ADC` reason.

## Invalid Reason Bits

Reason bits are shared across voltage, current, and temperature domains:

| Bit Mask | Name | Meaning |
|---|---|---|
| `0x00000001` | `ADC_MISSING` | Expected acquisition channel has not reported valid data. |
| `0x00000002` | `ADC_RANGE` | ADC millivolts are outside the valid ADC range. |
| `0x00000004` | `TAP_RANGE` | Voltage tap is outside broad physical bounds. |
| `0x00000008` | `TAP_ORDER` | Cumulative voltage taps are not monotonic. |
| `0x00000010` | `CELL_RANGE` | Reconstructed cell voltage is physically implausible. |
| `0x00000020` | `TAP_STEP` | Tap changed too far from the previous sample. |
| `0x00000040` | `CELL_STEP` | Cell voltage changed too far from the previous sample. |
| `0x00000080` | `STUCK_ADC` | ADC channel repeated exactly for the stuck-sample limit. |
| `0x00000100` | `CURRENT_SENSOR` | Current backend reported invalid current. |
| `0x00000200` | `CURRENT_RANGE` | Current magnitude is outside broad physical bounds. |
| `0x00000400` | `TEMPERATURE_SENSOR` | Temperature conversion reported invalid. |
| `0x00000800` | `TEMPERATURE_RANGE` | Temperature is outside broad physical bounds. |

## Diagnostics

Validation is visible through:

```text
GET,TAPS
GET,VOLT
GET,CURRENT
GET,TEMP
GET,FAULT
```

Example response shapes:

```text
RESP,TAPS,...,TAP_VALID=0x0000003F,CELL_VALID=0x0000003F,REASON=0x00000000
RESP,VOLT,...,VALID=0x0000003F,TAP_VALID=0x0000003F,REASON=0x00000000
RESP,CURRENT,...,VALID=1,REASON=0x00000000
RESP,TEMP,...,VALID=0x0000000F,REASON=0x00000000
```

The firmware dashboard also displays the validity bitmaps and decoded validation
reason text.

Stage 16 adds these diagnostic stimulus commands for PC tester work:

```text
GET,INJECT
DIAG,ADC,SET,CELL,<1-6>,<adc_mV>
DIAG,ADC,SET,CURRENT,<adc_mV>
DIAG,ADC,SET,TEMP,<1-4>,<adc_mV>
DIAG,ADC,ON
DIAG,ADC,OFF
DIAG,ADC,CLEAR,ALL
```

## Fault Integration

The fault supervisor now gates voltage fault decisions on:

```text
tap_valid_bitmap == all cells
cell_valid_bitmap == all cells
```

If voltage validation fails, the supervisor raises the sensor-invalid fault path
with primary fault code:

```text
0x4002 Measurement invalid
```

It does not convert invalid cells into undervoltage or overvoltage faults.

Current and temperature fault paths continue to use `current_valid` and
`temperature_valid_bitmap`, now with explicit invalid reason fields.

## Limits Of Stage 15

This is the first validation layer, not final production proof. Hardware testing
still needs to confirm the thresholds and reason behavior on:

- disconnected/floating ESP32 inputs
- Prototype-0 connected to the pack
- saved runtime voltage calibration
- INA226 profile hardware when available

No protection output, balancing, SoC, SoH, CAN, or tester firmware was added.
