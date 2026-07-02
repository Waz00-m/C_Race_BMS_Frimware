# Stage 14 And Stage 15 Plan

This note is a handoff for continuing after Stage 15.

## Current Position

Completed foundation:

- Stage 1-8: core firmware foundation, scheduler, ADC, faults, diagnostics,
  sleep-policy stub.
- Stage 9-10: board profiles and Python board configurator.
- Stage 11-12: current sensor abstraction, ACS772, INA226, I2C HAL.
- Stage 12.5: drag/drop configurator workflow and placeholder hardware blocks.
- Stage 13: config/NVM foundation with explicit diagnostic save/load/reset.
- Stage 14: runtime config editing through diagnostic `CFG,SET,...` commands.
- Stage 15: first measurement validation and fault truth layer.

Stage 13 added:

```text
GET,CFG
CFG,SAVE
CFG,LOAD
CFG,RESET
```

Stage 14 now allows controlled runtime edits without automatic flash writes.

## Stage 14 - Runtime Config Editing And Calibration Workflow

Status: implemented for the first diagnostic workflow.

Goal:

Allow calibration/config values to be edited through diagnostics and/or the
Python tools without editing source headers every time.

### Why This Stage Matters

Board-profile headers still define factory defaults, and Stage 13 can persist
`CFG_REG`. Stage 14 added the controlled path for modifying individual config
fields at runtime.

Stage 14 should make calibration practical.

### Implemented Features

- Diagnostic commands for controlled config edits.
- Editing voltage calibration values:
  - voltage divider ratio ppm
  - voltage gain ppm
  - voltage offset mV
- Editing NTC calibration values:
  - ADC gain ppm
  - ADC offset mV
- Editing threshold values:
  - cell low/high warning
  - cell low/high fault
  - pack low/high fault
  - overcurrent warning/fault
  - temperature warning/fault
- Editing battery capacity.
- Range checks before accepting edits.
- Dirty-state reporting after edits.
- `CFG,SAVE` remains the only flash-write action.

Still later:

- Runtime edits for analog current zero/gain/offset and no-load thresholds.
- Dashboard/configurator forms that send the diagnostic commands.

### Diagnostic Commands

Implemented command shape:

```text
CFG,SET,VOLT_RATIO,<index>,<ppm>
CFG,SET,VOLT_GAIN,<index>,<ppm>
CFG,SET,VOLT_OFFSET,<index>,<mV>
CFG,SET,NTC_GAIN,<index>,<ppm>
CFG,SET,NTC_OFFSET,<index>,<mV>
CFG,SET,CAPACITY,<mAh>
CFG,SET,THRESHOLD,<name>,<value>
GET,CFG
CFG,SAVE
CFG,LOAD
CFG,RESET
```

Indexes should be zero-based internally or one-based in user-facing commands,
but choose one and document it clearly. Stage 14 uses one-based user-facing
indexes.

### Expected Output

Example:

```text
>>> CFG,SET,VOLT_RATIO,1,1132427
RESP,CFG,SET,STATUS=OK,FIELD=VOLT_RATIO,INDEX=1,VALUE=1132427,DIRTY=1,CRC=0x12345678

>>> CFG,SAVE
RESP,CFG,SAVE,STATUS=OK,CRC=0x12345678,DIRTY=0
```

### Hard Rules

- Do not write flash automatically from the scheduler.
- Do not allow invalid config ranges into `CFG_REG`.
- Do not add Arduino/ESP32/Preferences calls to `bms_core/`.
- Do not bypass `bms_config`.
- Do not make calibration changes directly in measurement code.

### Validation

Build:

```powershell
pio run -e esp32dev
pio run -e esp32dev_profile1
```

Runtime:

1. Upload Profile0.
2. Send `GET,CFG`.
3. Send one safe `CFG,SET,...` command.
4. Confirm `GET,CFG` reports the changed value.
5. Send `CFG,SAVE`.
6. Reboot ESP32.
7. Confirm `GET,CFG` still reports the saved value.
8. Send `CFG,RESET`.
9. Reboot and confirm board-profile defaults are restored.

## Stage 15 - Measurement Validation And Fault Truth Layer

Status: implemented as the first validation layer. Hardware confirmation and
threshold tuning are still required.

Goal:

Stop treating every converted measurement as trustworthy. Add validation before
fault decisions depend on voltage/current/temperature values.

### Why This Stage Matters

The firmware can already measure, convert, report, and fault. But for real BMS
behavior, converted values must pass sanity checks before they can drive fault
state or protection decisions.

This is especially important because Prototype-0 has already shown noisy or
wrong cell values during calibration.

### Implemented Features

- Add measurement validation service in portable core.
- Validate voltage taps:
  - cumulative tap order must be monotonic
  - tap values must be within physical range
  - cell values must be within plausible range
  - sudden jumps should be detected
  - missing/stuck ADC channels should be detected
- Validate current:
  - current sensor valid flag
  - plausible current range
  - ADC range/stuck checks for analog current profiles
- Validate temperature:
  - open/short NTC/PTC detection
  - plausible temperature range
  - missing/stuck channel detection
- Add tap/cell validation bitmaps.
- Add invalid-reason bitmaps.
- Ensure fault supervisor uses validated values, not raw conversions.
- Add fault code `0x4002` for measurement invalid.

### Files

New files:

```text
bms_core/bms_measurement_validation.h
bms_core/bms_measurement_validation.cpp
```

Register additions:

```text
MEAS_REG.cell_valid_bitmap
MEAS_REG.tap_valid_bitmap
MEAS_REG.current_valid
MEAS_REG.temperature_valid_bitmap
ACQ_REG.stuck_bitmap
ACQ_REG.timeout_bitmap
```

`ACQ_REG.timeout_bitmap` remains future work. Do not add all fields blindly.
Add only what the validation logic requires.

### Expected Output

Telemetry and diagnostics should make validation visible, for example:

```text
MEAS: pack_mV=21260 cell_valid=0x3F tap_valid=0x3F ...
RESP,VOLT,...,VALID=0x3F,TAP_VALID=0x3F
RESP,FAULT,...,PRIMARY=0x4002
```

### Hard Rules

- Fault supervisor should not trust unvalidated cell values.
- Do not hide invalid readings by forcing them to safe-looking values.
- Do not add MOSFET/protection output behavior yet.
- Do not add balancing yet.
- Do not fake SoH.

### Validation

Hardware:

1. Run with ESP32 disconnected/floating and confirm invalid channels are flagged.
2. Run on Prototype-0 PCB and confirm stable valid channels are accepted.
3. Use `GET,TAPS`, `GET,VOLT`, `GET,TEMP`, `GET,CURRENT`, and `GET,FAULT`.

Build:

```powershell
pio run -e esp32dev
pio run -e esp32dev_profile1
```

Boundary check:

```powershell
rg -n "Arduino\.h|Serial|analogRead|millis\(|delay\(|Preferences|Wire\." bms_core bms_hal bms_boards -S
```

Expected result: no platform calls in `bms_core`.

## After Stage 15

Good candidates after Stage 15:

- Stage 16: tester foundation. Started as a PC UART tester in
  `tester_firmware/pc_uart_tester/`; MicroPython embedded scaffold remains in
  `tester_firmware/micropython_uart_tester/` for later porting. PC GUI now
  supports firmware-side ADC injection through `GET,INJECT` and
  `DIAG,ADC,...`.
- Stage 17: dashboard/configurator calibration UI.
- Stage 18: SoC coulomb-counting structure.
- Stage 19: AFE backend scaffold for LTC6811/BQ76952.
