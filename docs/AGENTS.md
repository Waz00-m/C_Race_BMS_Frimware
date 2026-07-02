# BMS Firmware Coding Instructions

This repository is for a Drone BMS firmware effort that is moving from a
Prototype-0 ESP32 monitoring program into a portable, layered BMS firmware
library. Treat this file as the primary project memory for Codex and other
coding agents.

The current workspace contains:

- `p0_bms_dashboard.py`: Python/Tkinter dashboard that reads Prototype-0 CSV
  telemetry over USB serial and logs it to `p0_bms_log.csv`.
- `p0_bms_log.csv`: Existing telemetry log data. Do not rewrite or delete this
  file unless explicitly asked.
- `Drone_BMS_Firmware/`: Portable C/C++ firmware library and ESP32 first
  platform target. This folder is the main implementation target.

## Project Goal

Create a professional Drone BMS firmware platform with ESP32 as the first
hardware target, while keeping the BMS core portable across future MCUs such as
STM32, NXP, TI, or other automotive/industrial controllers.

The firmware must behave like a small embedded operating system for the battery.
It must not remain a monolithic Arduino loop that reads sensors and prints
values directly.

The target architecture is:

- State-driven
- Scheduler-based
- Register-owned
- HAL-isolated
- Sensor-agnostic
- Tester-friendly
- Fault-code-driven
- Designed for active, idle, sleep, diagnostic, and fault behavior

## Current Implementation Position

The project has completed a first Stage 15 measurement-validation
implementation and has started Stage 16 as a separate PC UART tester
foundation with firmware-side ADC injection. The next implementation target
should be chosen after hardware
validation of the active profile, INA226 profile, configurator-generated
profiles, config/NVM diagnostic commands, Stage 15 validity/reason outputs, and
the Stage 16 tester command/response loop.

Prototype telemetry tooling exists through `p0_bms_dashboard.py`, but the
portable firmware library now has its staged ESP32 foundation, board-profile
layer, drag/drop configurator workflow tools, current-sensor backend layer,
INA226 I2C current path, a first config/NVM service, a first measurement
validation truth layer, and a separate tester firmware scaffold.

Stage 1 proved:

- The firmware project structure exists.
- The BMS context can initialize.
- Register defaults are created in one central context.
- The Arduino wrapper calls `BMS_App_Init()` and `BMS_App_Run()`.
- A platform UART HAL can print `BMS INIT OK`.
- No real ADC formulas are implemented yet.
- No deep sleep implementation is implemented yet.
- No advanced SoC or SoH algorithm is implemented yet.

Stage 2 proved:

- A register snapshot can be captured from the initialized context.
- Boot output can print default `SYS_REG`, `ACQ_REG`, `MEAS_REG`, `EST_REG`,
  `FAULT_REG`, `DIAG_REG`, and `CFG_REG` values.
- Readable enum names are available for debug output.
- App/telemetry-style debug output reads a snapshot, not partially updated live
  registers.

Stage 3 proved:

- ESP32 hardware timer HAL can generate a 1 ms base tick.
- Core scheduler active profile can generate task due flags.
- ISR callback only increments scheduler time, updates counters, and marks due
  work.
- Foreground app loop consumes scheduler due flags.
- Scheduler heartbeat output proves current, voltage, temperature, estimation,
  fault, telemetry, diagnostic, and sleep-policy task timing.

Stage 4 proved:

- A fake measurement service can update `MEAS_REG` through controlled service
  functions.
- Scheduler due flags can drive fake current, voltage, and temperature updates.
- Safe fake values can be read through register snapshots and printed in a
  measurement heartbeat.
- No real ADC formulas or ESP32 ADC APIs are used yet.

Stage 5 proved:

- ADC HAL interface exists for core-facing ADC reads.
- ESP32 ADC adapter owns Arduino `analogRead()` and `analogReadMilliVolts()`
  calls.
- Voltage, current, and NTC temperature conversion paths are separated in the
  measurement service.
- `ACQ_REG` records raw ADC values, ADC millivolts, sample counters, and valid
  bitmap.
- `MEAS_REG` can now be updated from real ESP32 ADC readings.

Stage 6 proved:

- Fault-code definitions exist for voltage, current, temperature, and ADC faults.
- Fault supervisor checks measurement and acquisition registers.
- Warning and active fault bitmaps are updated from measured values.
- Primary fault code, fault severity, latched bitmap, and event counter are
  updated.
- Fault reporting is visible in the serial heartbeat.

Stage 7 proved:

- UART HAL supports non-blocking receive.
- Diagnostic service parses newline-terminated commands through a fixed buffer.
- Diagnostic task is scheduler-driven at the active profile diagnostic period.
- Commands can query snapshot, voltage, current, temperature, and fault state.
- Fault-code table documentation exists for current implemented codes and
  bitmaps.

Stage 8 proved:

- Sleep policy service exists in portable core code.
- `SLEEP_REG` records sleep decision, reason, threshold, and evaluation count.
- Scheduler sleep-policy task evaluates sleep eligibility in foreground code.
- Firmware reports `SLEEP_DENIED_FAULT_ACTIVE`,
  `SLEEP_DENIED_LOAD_ACTIVE`, and `SLEEP_ALLOWED`.
- Diagnostic command `GET,SLEEP` can query sleep policy state.
- ESP32 deep sleep entry remains intentionally stubbed/not implemented.

Stage 9 proved:

- Board profiles can select hardware-specific values outside the portable core.
- `BMS_BOARD_PROTOTYPE0_PROFILE0` is the calibrated Prototype-0 analog-current
  baseline.
- `BMS_BOARD_PROTOTYPE0_PROFILE1` is reserved for the INA226 current-sensor
  variant.
- `BMS_BOARD_CONFIG_FILE` can include an external generated profile.

Stage 10 proved:

- `bms_board_configurator.py` can generate board profile headers and a local
  PlatformIO user config.
- The configurator can build, upload, and clean through PlatformIO without
  editing the portable core.

Stage 11 proved:

- Current-sensor conversion is separated from the measurement scheduler.
- Analog INA240 and analog ACS772 backends are selectable by board profile.
- Shared analog current filtering, gain/offset correction, and no-load
  hysteresis live in the current-sensor backend.

Stage 12 proved:

- I2C HAL interface exists.
- ESP32 Wire-backed I2C adapter exists.
- INA226 current backend can configure calibration and read current over I2C.
- `BMS_BOARD_PROTOTYPE0_PROFILE1` can build as an INA226 current profile.
- Missing INA226 hardware reports invalid current instead of stopping firmware
  initialization.

Stage 12.5 proved:

- Configurator drag/drop hardware blocks can fill detailed profile fields.
- Generated profiles now include a small manifest file.
- Generated profile cleanup can delete selected generated profile files.
- Generated profile build-cache cleanup can remove selected `.pio/build/<env>`
  directories.

Stage 13 proved:

- NVM HAL interface exists.
- ESP32 Preferences-backed NVM adapter exists.
- Portable config service can calculate CRC, load, save, and reset `CFG_REG`.
- Voltage and NTC measurement calibration values are now read from `CFG_REG`.
- Diagnostic commands can query and explicitly save/load/reset config.

Stage 14 proved:

- Diagnostic `CFG,SET,...` commands can edit runtime config without rebuilding.
- Voltage divider ratio, voltage gain, voltage offset, NTC ADC gain, NTC ADC
  offset, capacity, and threshold edits are range checked inside `bms_config`.
- User-facing diagnostic channel indexes are one-based.
- `CFG_REG.config_dirty` reports unsaved config edits.
- `CFG,SAVE` remains the explicit flash-write action.

Stage 15 proved:

- `bms_measurement_validation` validates voltage taps, reconstructed cells,
  current, and temperature before fault logic trusts them.
- `MEAS_REG` exposes tap validity, cell validity, and invalid-reason bitmaps.
- `ACQ_REG.stuck_bitmap` exposes repeated ADC readings for analog channels.
- Invalid measurement state can raise `BMS_FAULT_CODE_MEASUREMENT_INVALID`
  instead of turning bad readings into voltage/current/temperature faults.
- Diagnostic responses and dashboard parsing expose validity and reason fields
  for bench validation.

Stage 16 started:

- Tester firmware lives separately in
  `tester_firmware/pc_uart_tester/` and
  `tester_firmware/micropython_uart_tester/`.
- The immediate tester is PC Python based and sends diagnostic UART commands.
- A browser GUI is available for the PC tester in
  `tester_firmware/pc_uart_tester/pc_bms_tester_gui.py`.
- The MicroPython tester remains a later embedded-port scaffold.
- The tester parses `RESP,...` responses and checks Stage 15 validity fields.
- Known faults must be excluded only through explicit tester-side toggles and
  fault-code values; do not hardcode bench faults as expected behavior.
- The PC tester may use `GET,INJECT` and `DIAG,ADC,...` for volatile
  firmware-side ADC stimulus. This is not a replacement for later external
  tester hardware.
- PC tester profiles and generated JSON/PDF reports live under
  `tester_firmware/pc_uart_tester/`; generated report files are not source.
- The PC tester GUI, PC CLI, and MicroPython scaffold should share the
  fault-code exclusion model based on `GET,FAULT CODES=[...]`.

Do not skip ahead into CAN, balancing, high-current validation, production
sleep behavior, or real SoH until the staged foundation and hardware truth are
validated.

## Hard Rules

These rules are non-negotiable.

- Do not use `millis()` in `bms_core/`.
- Do not use `delay()` in `bms_core/`.
- Do not use `Serial` in `bms_core/`.
- Do not use `analogRead()` in `bms_core/`.
- Do not include `Arduino.h` in `bms_core/`.
- Do not include ESP32 driver headers in `bms_core/`.
- Do not allocate memory in an ISR.
- Do not allocate memory in fast runtime paths.
- Do not perform ADC reads in an ISR.
- Do not perform UART prints in an ISR.
- Do not update displays in an ISR.
- Do not calculate SoC, faults, or measurements in an ISR.
- Do not scatter global measurement variables across modules.
- Do not let multiple modules write the same register group casually.
- Do not fake SoH as a real value.
- Do not put platform-specific code outside platform adapter files.

Allowed platform-specific code locations:

- `Drone_BMS_Firmware/app/main.cpp` for the Arduino entry wrapper only.
- `Drone_BMS_Firmware/bms_platform/esp32/` for ESP32 HAL implementations.

The BMS core must call abstract HAL functions only.

## Required Architectural Boundary

The core library is portable. The platform layer is not.

Core code may include:

- `bms_types.h`
- `bms_status.h`
- `bms_registers.h`
- `bms_context.h`
- Other `bms_core/` headers
- `bms_hal/` interface headers
- Standard C/C++ headers where appropriate

Core code must not include:

- `Arduino.h`
- `driver/adc.h`
- `esp_sleep.h`
- `HardwareSerial.h`
- STM32 HAL headers
- NXP SDK headers
- TI driver headers

Platform code may include platform APIs. For ESP32 Arduino, this is allowed
inside `bms_platform/esp32/`:

- `Arduino.h`
- `Serial`
- ESP32 timer APIs
- ESP32 sleep APIs
- ESP32 ADC APIs
- Critical section primitives

## Directory Ownership

Use this ownership model when adding files.

`Drone_BMS_Firmware/app/`

- Owns the top-level application lifecycle.
- Provides `BMS_App_Init()` and `BMS_App_Run()`.
- Keeps the Arduino `setup()` and `loop()` wrappers thin.
- Must not become a monolithic firmware file.

`Drone_BMS_Firmware/bms_core/`

- Owns portable BMS logic.
- Owns runtime context, register map, scheduler, state machine, measurement
  service, estimation service, fault supervisor, sleep policy, diagnostics, and
  telemetry.
- Must remain independent of ESP32 and Arduino.

`Drone_BMS_Firmware/bms_hal/`

- Owns abstract HAL function declarations and interface contracts.
- Provides functions such as timer, UART, ADC, GPIO, power, NVM, watchdog, and
  lock interfaces.
- Must not contain platform-specific implementation code.

`Drone_BMS_Firmware/bms_platform/esp32/`

- Owns ESP32 implementations of HAL interfaces.
- May call Arduino and ESP32 APIs.
- Must keep platform details from leaking into `bms_core/`.

`Drone_BMS_Firmware/docs/`

- Owns architecture notes, stage notes, fault tables, diagrams, and review
  material.

The existing `p0_bms_dashboard.py` is a host-side tool. It is not part of the
embedded firmware core.

## Stage Plan

Follow this order unless the user explicitly changes it.

### Stage 1 - Skeleton Compiles

Files:

- `bms_types.h`
- `bms_status.h`
- `bms_registers.h`
- `bms_context.h`
- `bms_context.cpp`
- `bms_app.h`
- `bms_app.cpp`
- `main.cpp`
- Minimal UART HAL interface and ESP32 implementation

Goal:

- Project structure exists.
- BMS context initializes.
- UART prints `BMS INIT OK`.
- Core has no platform dependencies.

### Stage 2 - Register Map Works

Register groups:

- `SYS_REG`
- `ACQ_REG`
- `MEAS_REG`
- `EST_REG`
- `FAULT_REG`
- `DIAG_REG`
- `CFG_REG`

Goal:

- Default register values are initialized.
- A snapshot/accessor can print or expose default values.
- One writer owns each group.

### Stage 3 - Scheduler Works

Files:

- `bms_scheduler.h`
- `bms_scheduler.cpp`
- `bms_timer_hal.h`
- `esp32_timer_hal.cpp`

Goal:

- Timer HAL provides the timebase.
- Scheduler profiles generate task flags.
- ISR only updates ticks, counters, and due flags.

Active profile target:

- Current every 5 ms
- Voltage every 20 ms
- Temperature every 250 ms
- Estimation every 100 ms
- Fault check every 20 ms
- Telemetry every 100 ms
- Diagnostic service every 10 ms
- Sleep policy every 500 ms

Idle profile target:

- Current every 500 ms
- Voltage every 1000 ms
- Temperature every 2000 ms
- Estimation every 1000 ms
- Fault check every 500 ms
- Telemetry every 2000 ms
- Diagnostic service every 20 ms
- Sleep policy every 1000 ms

`0 ms` means disabled for a task in that profile.

### Stage 4 - Fake Measurement Works

Goal:

- Fake safe values update `MEAS_REG`.
- Telemetry snapshot prints those values.
- No ESP32 ADC conversion yet.

Initial fake values:

- Cell voltage: 4200 mV
- Current: 0 mA
- Temperature: 250 dC

### Stage 5 - Real ESP32 ADC Works

Goal:

- ADC source interfaces connect to ESP32 implementation.
- Raw ADC becomes engineering values.
- Voltage, current, and temperature conversion paths are separated.

Do not implement this before Stages 1 to 4 are stable.

### Stage 6 - Fault Supervisor Works

Goal:

- Fault supervisor checks validated values.
- Fault bitmaps and primary fault code update.
- Telemetry reports warning/fault state.

Initial fault families:

- Overvoltage
- Undervoltage
- Overcurrent
- Overtemperature
- Sensor invalid

### Stage 7 - Diagnostic UART Works

Goal:

- Internal tester/manual serial commands request data.
- Diagnostic service owns command parsing and response logic.

Initial commands:

- `GET,SNAPSHOT`
- `GET,VOLT`
- `GET,CURRENT`
- `GET,TEMP`
- `GET,FAULT`

Packet proposal:

- Request: `$BMS,<CMD>,<TARGET>,<VALUE>,<CRC>`
- Response: `$BMSR,<STATUS>,<FAULT_CODE>,<PAYLOAD>,<CRC>`

### Stage 8 - Sleep Policy Stub Works

Goal:

- Sleep allowed/denied logic exists.
- ESP32 deep sleep can remain stubbed.
- System can report sleep reasons.

Initial reasons:

- `SLEEP_DENIED_LOAD_ACTIVE`
- `SLEEP_DENIED_FAULT_ACTIVE`
- `SLEEP_ALLOWED`

## Runtime Register Map

The BMS firmware must not use scattered global variables for live battery
state. Use a central runtime register map inside `BMS_Context`.

Register groups:

- `SYS_REG`
- `ACQ_REG`
- `MEAS_REG`
- `EST_REG`
- `FAULT_REG`
- `DIAG_REG`
- `CFG_REG`

Ownership rule:

- One register group has one controlled writer.
- Other modules read through controlled accessors or snapshots.
- Telemetry and diagnostics must read snapshots, not half-updated live data.

Expected group responsibilities:

`SYS_REG`

- System mode
- Sub-state
- Uptime
- Wake cause
- Scheduler status
- Reset reason

`ACQ_REG`

- Raw ADC values
- ADC millivolts
- Filter-ready bitmap
- Sample counters
- Sensor-valid bitmap

`MEAS_REG`

- Cell voltages
- Pack voltage
- Current
- Absolute current
- Temperatures
- Minimum cell index
- Maximum cell index
- Cell delta

`EST_REG`

- SoC
- SoH placeholder
- DoD
- C-rate
- Power
- Used Ah
- Used Wh
- SoC valid flag
- SoH valid flag
- SoC method
- SoH method

`FAULT_REG`

- Warning bitmap
- Active fault bitmap
- Latched fault bitmap
- Primary fault code
- Fault severity
- Event counter

`DIAG_REG`

- Diagnostic active flag
- Command ID
- Target service
- Test ID
- Response code
- Override token

`CFG_REG`

- Config version
- Config CRC
- Voltage thresholds
- Current thresholds
- Temperature thresholds
- Sample periods
- Calibration gains
- Calibration offsets
- Battery capacity

## State Model

The core state model includes:

- `BOOT_INIT`
- `WAKE_RESTORE`
- `ACTIVE_MONITORING`
- `IDLE_MONITORING`
- `SLEEP_READY`
- `SLEEP_MODE`
- `DIAGNOSTIC_MODE`
- `FAULT_ACTIVE`
- `SAFE_MONITORING`

Do not describe sleep as "after measurement the MCU sleeps."

Correct model:

After measurement, the state manager evaluates system condition and sleep
policy. Sleep is entered only after idle/no-load stability, no critical fault,
no diagnostic override, communication idle, snapshot saved, wake sources armed,
and sensor standby request completed or safely bypassed.

Important active/sleep rule:

- Fast current sampling belongs to active monitoring.
- Meaningful sleep is not useful while current must be sampled every 5 ms.
- Sleep mode uses a different scheduler profile where fast periodic work is
  disabled or reduced to wake windows.

## Timer And Scheduler Rules

The BMS core must use a BMS timer HAL.

Core-facing timer functions should follow this style:

- `BMS_HAL_Timer_GetTickMs()`
- `BMS_HAL_Timer_StartBaseTick()`
- `BMS_HAL_Timer_StopBaseTick()`

Timeouts must use the BMS timebase, not `millis()`.

ISR rule:

- Increment tick.
- Update task counters.
- Set due flags.
- Exit quickly.

ISR must not:

- Read ADC.
- Send UART data.
- Update display.
- Allocate memory.
- Calculate measurements.
- Calculate SoC.
- Run fault algorithms.
- Parse diagnostic commands.

Actual work runs in foreground services called by `BMS_App_Run()` or
`BMS_Run(ctx)`.

## Measurement Pipeline

Raw data is not trusted directly.

The measurement path is:

Physical signal
-> HAL read
-> Filter
-> Calibration
-> Validation
-> Engineering conversion
-> Register update
-> Estimation, fault, telemetry, diagnostic outputs

Voltage path:

- ADC value
- Divider ratio correction
- Cell voltage calculation
- Tap order/range validation
- `MEAS_REG.cell_mV[]`

Current path:

- ADC or millivolt value
- Zero reference correction
- Gain correction
- Shunt/Hall/AFE conversion
- `MEAS_REG.current_mA`
- No-load hysteresis

Temperature path:

- ADC value
- NTC resistance
- Beta conversion
- Open/short detection
- `MEAS_REG.temperature_dC[]`

Validation happens before values are trusted.

## SoC And SoH Rules

SoC can be implemented at a basic level after the skeleton is stable.

Acceptable early SoC approaches:

- Voltage lookup table
- Coulomb counting structure
- Hybrid method later

SoH must not be faked.

Initial SoH behavior:

- Include SoH fields in `EST_REG`.
- Set `soh_valid = false`.
- Set `soh_method = BMS_SOH_NOT_AVAILABLE`.
- Do not print fake 100 percent health.

Real SoH needs evidence such as:

- Usable capacity trend
- Internal resistance trend
- Cycle count
- Charge/discharge history
- Voltage abuse history
- Temperature stress history
- Aging model or test data

## Fault Code System

Fault codes must be stable, diagnostic-friendly identifiers.

Ranges:

- `0x0000`: No fault
- `0x1xxx`: Voltage faults
- `0x2xxx`: Current faults
- `0x3xxx`: Temperature faults
- `0x4xxx`: ADC/acquisition faults
- `0x5xxx`: Communication faults
- `0x6xxx`: Scheduler/system faults
- `0x7xxx`: Sleep/wake faults
- `0x8xxx`: Diagnostic faults
- `0x9xxx`: Latched/repeated/critical faults

Initial examples:

- `0x1001`: Cell overvoltage
- `0x1002`: Cell undervoltage
- `0x1003`: Pack overvoltage
- `0x1004`: Pack undervoltage
- `0x2001`: Charge overcurrent
- `0x2002`: Discharge overcurrent
- `0x2003`: Current sensor fault
- `0x3001`: Cell temperature high
- `0x3002`: MOSFET temperature high
- `0x3003`: Temperature sensor open/short
- `0x4001`: ADC read failure
- `0x4002`: Sensor timeout
- `0x5001`: UART timeout
- `0x5002`: CAN timeout
- `0x6001`: Scheduler overrun
- `0x6002`: Watchdog reset
- `0x7001`: Sleep entry failure
- `0x7002`: Wake restore failure
- `0x8001`: Invalid diagnostic command
- `0x8002`: Diagnostic override active

## Diagnostic Tester Direction

The diagnostic tester is a separate firmware project from the BMS target.

Tester job:

Inject known condition
-> send command
-> BMS measures/processes/stores/checks
-> tester requests snapshot/fault
-> tester compares expected and actual
-> tester prints PASS/FAIL

UART is the first internal diagnostic transport. Future CAN support should be
added through a transport adapter without changing the diagnostic service model.

## Python Dashboard Rules

`p0_bms_dashboard.py` is a Prototype-0 host tool. Keep it stable unless the user
asks for dashboard changes.

It currently expects serial CSV packets with this shape:

`BMSP0,PKT,TIME_MS,STATUS,MODE,WARN_HEX,FAULT_HEX,VPACK,CURRENT_A,POWER_W,C1,C2,C3,C4,C5,C6,T1,T2,T3,T4,MIN_CELL_NUM,MIN_CELL_V,MAX_CELL_NUM,MAX_CELL_V,DELTA_V,PEAK_A,USED_AH,USED_WH,SOC_EST`

Do not silently break that format. If the firmware telemetry protocol changes,
either preserve a compatibility output or update the dashboard deliberately.

The future firmware telemetry may use a cleaner packet protocol. When that
happens, update the dashboard as a separate explicit task.

## Coding Style

Use conservative embedded C/C++.

- Prefer fixed-width integer types.
- Prefer explicit units in names, such as `mV`, `mA`, `dC`, `mAh`, `mWh`.
- Prefer small structs with clear ownership.
- Prefer plain functions for core services until a stronger abstraction is
  clearly needed.
- Keep core headers C-compatible where practical by using `extern "C"`.
- Keep comments short and technical.
- Do not hide platform calls behind macros in core code.
- Avoid dynamic allocation in runtime firmware paths.
- Initialize context and register defaults deterministically.
- Use `static` for private file-scope data in `.cpp` files.

## Build And Verification

The first ESP32 target is Arduino-framework ESP32.

Preferred build command when PlatformIO is installed:

```powershell
pio run -d Drone_BMS_Firmware
```

If PlatformIO is not installed, perform structural checks:

- Confirm the files exist.
- Confirm `bms_core/` does not include `Arduino.h`.
- Confirm only app wrapper or ESP32 platform code includes `Arduino.h`.
- Confirm no `millis()`, `delay()`, `Serial`, or `analogRead()` calls exist in
  `bms_core/`.
- Confirm stage-specific code does not jump ahead.

## Agent Workflow

When Codex or another coding agent works here:

1. Read this file before editing.
2. Identify the active stage.
3. Keep edits scoped to the current stage unless the user asks otherwise.
4. Do not rewrite the Python dashboard while working on firmware skeletons.
5. Do not delete or rewrite telemetry logs.
6. Keep platform-specific code in platform folders.
7. Verify boundary rules with text search after editing.
8. Report what changed and what was not yet implemented.

For Stage 1, the correct final statement is similar to:

`Stage 1 skeleton is present. Context init and UART boot banner are wired. No scheduler, ADC, fault supervisor, diagnostic parser, or sleep policy has been implemented yet.`

## Current No-Go List

Do not implement these until their stage arrives:

- Production-tuned validation thresholds
- Moving average filters
- Deep sleep
- Wake-source policy
- CAN
- Cell balancing
- SoH algorithm
- Diagnostic override tokens
- Tester hardware stimulus beyond the Stage 16 UART scaffold
- OTA update infrastructure
- Production fault latching

This no-go list exists to keep the project from collapsing back into a large
monolithic firmware file.
