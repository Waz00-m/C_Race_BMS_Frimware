 # History of Changes

This file tracks major firmware architecture updates. It is intentionally brief
so it can support external journal and document updates.

## 2026-06-30 - Stage 1 To Stage 8 Bring-Up

### Baseline

- Prototype-0 Arduino firmware was used only as a reference for what had already
  been proven on hardware.
- The new portable firmware library started from a clean architecture, not by
  copying the Prototype-0 `.ino` as the implementation base.

### Stage 1 - Skeleton

Added:

- PlatformIO ESP32 Arduino project structure under `Drone_BMS_Firmware/`.
- Thin Arduino `setup()` / `loop()` wrapper.
- `BMS_App_Init()` and `BMS_App_Run()`.
- Portable BMS types, status codes, register map structs, and context init.
- UART HAL interface and ESP32 UART adapter.

Removed or avoided from previous approach:

- BMS logic inside Arduino `loop()`.
- Direct `Serial` use inside `bms_core/`.
- Direct ESP32 or Arduino headers inside `bms_core/`.

### Stage 2 - Register Map Visibility

Added:

- Register snapshot capture API.
- Enum-to-string helpers for debug output.
- Boot-time default register snapshot printout.
- Real ESP32 serial validation of initialized register defaults.

Changed from Stage 1:

- Boot output now reports named modes and register groups instead of only the
  init banner.

### Stage 3 - Scheduler Bring-Up

Added:

- Timer HAL interface.
- ESP32 hardware timer adapter using a 1 ms base tick.
- Lock HAL interface and ESP32 critical-section adapter.
- Core scheduler profiles for active, idle, and sleep timing.
- ISR callback that only increments scheduler time, updates task counters, and
  marks due work.
- Foreground due-flag consumption in `BMS_App_Run()`.
- Low-rate scheduler heartbeat output proving task timing.

Changed from Stage 2:

- `SYS_REG.system_mode` now enters `ACTIVE_MONITORING` during app bring-up.
- `SYS_REG.scheduler_status` now reports `ACTIVE`.
- The app loop is no longer empty; it consumes scheduler flags and updates
  uptime.

Validation:

- Hardware serial output on COM3 confirmed active scheduler counters:
  current every 5 ms, voltage/fault every 20 ms, temperature every 250 ms,
  estimation/telemetry every 100 ms, diagnostic every 10 ms, and sleep policy
  every 500 ms.

### Stage 4 - Fake Measurement Service

Added:

- `bms_measurement.h/.cpp`.
- Fake current update service.
- Fake voltage update service.
- Fake temperature update service.
- Scheduler-driven foreground calls from `BMS_App_Run()`.
- Measurement heartbeat output read through register snapshots.

Changed from Stage 3:

- `MEAS_REG` is no longer all zero after initialization.
- Fake safe values are now written:
  - cell voltage = 4200 mV per cell
  - pack voltage = 25200 mV
  - current = 0 mA
  - temperature = 250 dC per sensor

Removed or avoided:

- No real ESP32 ADC conversion was added.
- No current shunt formula was added.
- No NTC formula was added.
- No OLED/display service was added.

Validation:

- Hardware serial output confirmed fake scheduled measurements:
  pack voltage = 25200 mV, current = 0 mA, temperature = 250 dC, and all six
  cells = 4200 mV.

### Stage 5 - Real ESP32 ADC Measurement Path

Added:

- `bms_adc_hal.h`.
- `esp32_adc_hal.cpp`.
- `esp32_pin_config.h`.
- `bms_measurement_config.h`.
- Core-facing ADC reads for raw ADC counts and ADC millivolts.
- Acquisition register updates for raw ADC, ADC mV, sample counters, valid
  bitmap, and filter-ready bitmap.
- Real ADC-backed voltage conversion path.
- Real ADC-backed current conversion path.
- Real ADC-backed NTC temperature conversion path.

Changed from Stage 4:

- `BMS_App_Run()` now calls generic measurement update functions instead of
  fake-only functions.
- Default measurement backend now uses ESP32 ADC reads.
- Measurement heartbeat now prints both engineering values and ADC mV values.

Removed or avoided:

- Direct Arduino ADC calls are kept out of `bms_core/`.
- Fault decisions were not added yet.
- Cell tap validation was not added yet.
- Moving-average filtering was not added yet.
- OLED/display service was not added yet.

Validation:

- Hardware serial output confirmed all 11 ADC channels were active:
  `ACQ_REG.sensor_valid_bitmap = 0x000007FF`.
- ADC millivolt values changed over time and `MEAS_REG` was updated from real
  ESP32 ADC reads.
- Engineering values were not treated as calibrated or safe; they were used to
  prove the data path only.

### Stage 6 - Fault Supervisor

Added:

- `bms_fault_codes.h`.
- `bms_fault_supervisor.h/.cpp`.
- Warning bit definitions.
- Active fault bit definitions.
- Stable primary fault code definitions.
- Default voltage/current/temperature thresholds in `CFG_REG`.
- Fault checks for:
  - cell undervoltage / overvoltage
  - pack undervoltage / overvoltage
  - cell imbalance warning
  - overcurrent warning / fault
  - high temperature warning / fault
  - missing sensor-valid bits
- Fault heartbeat output.

Changed from Stage 5:

- Scheduler fault task now runs the fault supervisor.
- `FAULT_REG` is updated continuously.
- `SYS_REG.system_mode` can move to `FAULT_ACTIVE` when active faults exist.
- Latched fault bitmap records active faults observed so far.

Removed or avoided:

- No protection output, MOSFET control, or battery disconnect was added.
- No production-grade latching/clearing policy was added.
- No diagnostic command parser was added yet.

### Stage 7 - Diagnostic UART

Added:

- Non-blocking UART byte receive in the UART HAL.
- ESP32 UART receive adapter using `Serial.available()` and `Serial.read()`.
- `bms_diagnostic.h/.cpp`.
- Fixed-size diagnostic command buffer.
- Newline-terminated command parser.
- Diagnostic scheduler task integration.
- Diagnostic boot readiness line.
- Commands:
  - `HELP`
  - `GET,SNAPSHOT`
  - `GET,VOLT`
  - `GET,CURRENT`
  - `GET,TEMP`
  - `GET,FAULT`
- `docs/fault_code_table.md`.

Changed from Stage 6:

- `DIAG_REG` now records command ID, response code, and active diagnostic
  status.
- Diagnostic queries can read register snapshots on demand instead of relying
  only on automatic heartbeat output.

Removed or avoided:

- No heap-based command parsing was added.
- No blocking UART wait was added.
- No diagnostic override or actuator-control behavior was added.

### Host Tooling - Firmware Dashboard

Added:

- `bms_firmware_dashboard.py`.
- Tkinter GUI for the staged portable firmware serial output.
- Serial port connect/disconnect controls.
- Buttons for diagnostic commands:
  - `HELP`
  - `GET,SNAPSHOT`
  - `GET,VOLT`
  - `GET,CURRENT`
  - `GET,TEMP`
  - `GET,FAULT`
- Parsers for scheduler heartbeat, measurement heartbeat, acquisition values,
  fault heartbeat, and `RESP,...` diagnostic responses.
- Decoding for warning/fault bitmaps and primary fault code names.
- CSV raw-line log file: `bms_firmware_dashboard_log.csv`.

Changed from serial-monitor-only workflow:

- Firmware values can now be viewed in grouped panels instead of reading the raw
  serial stream manually.
- Diagnostic command responses can be triggered from buttons.

### Stage 8 - Sleep Policy Stub

Added:

- `bms_sleep_policy.h/.cpp`.
- `SLEEP_REG` inside the runtime register map.
- Sleep decision enum and sleep reason enum.
- String helpers for sleep decision and sleep reason.
- Sleep policy default load-active threshold:
  - 2000 mA
- Scheduler-driven sleep policy evaluation.
- Sleep policy heartbeat output.
- Boot-time sleep policy register snapshot output.
- Diagnostic command:
  - `GET,SLEEP`
- Dashboard sleep command button and parsed sleep-policy display.

Changed from Stage 7:

- The scheduler sleep-policy task now performs foreground policy evaluation.
- The firmware can now report:
  - `SLEEP_DENIED_FAULT_ACTIVE`
  - `SLEEP_DENIED_LOAD_ACTIVE`
  - `SLEEP_ALLOWED`
- Sleep denial currently prioritizes active faults before load current.
- Diagnostic readiness now includes `GET,SLEEP`.

Removed or avoided:

- No ESP32 deep sleep entry was added.
- No wake-source arming was added.
- No sensor standby control was added.
- No scheduler profile transition into sleep mode was added.

Validation:

- PlatformIO build passed after the Stage 8 changes.
- Core boundary search still found no Arduino/ESP32 API calls in `bms_core/`.

### Calibration Tooling - Prototype-0 Voltage Taps

Added:

- `MEAS_REG.tap_mV[]` for cumulative voltage tap visibility.
- Diagnostic command:
  - `GET,TAPS`
- Dashboard button for `GET,TAPS`.
- Calibration readings and first-pass ratio calculations in
  `docs/next_objectives.md`.

Changed from Stage 8:

- Voltage tap debug data can now be requested directly instead of inferred from
  heartbeat lines.
- Voltage divider ratios were updated from the first `GET,TAPS` calibration
  capture.
- The temporary global voltage gain correction was reset to unity.
- Voltage divider ratios were updated again from the second `GET,TAPS`
  calibration capture.
- Voltage divider ratios were updated a third time from the next `GET,TAPS`
  calibration capture, mainly correcting VC4 and VC6.

Removed or avoided:

- Calibration is still considered first-pass only until a post-update
  `GET,TAPS` response is checked.

### Prototype-0 OLED Display Adapter

Added:

- `bms_display_hal.h`.
- `esp32_display_hal.cpp`.
- PlatformIO dependency for Adafruit SSD1306.
- Prototype-0 style OLED screens:
  - voltage page
  - current page
  - temperature page
- GPIO18 manual page button support.

Changed:

- `BMS_App_Init()` now initializes the display HAL as an optional peripheral.
- The app updates the OLED from a register snapshot during the existing
  telemetry heartbeat cadence.

Removed or avoided:

- No Adafruit, Wire, Arduino, or OLED code was added to `bms_core/`.
- Display failure does not stop the BMS firmware from running.

Still not implemented:

- Real ESP32 deep sleep and wake-source policy.
- SoC/SoH algorithms.

### Prototype-0 Current And Temperature Calibration Port

Added:

- Prototype-0 current defaults in the modular measurement config:
  - 1.650 V zero-current reference
  - 38.30 V/V effective INA gain
  - 1.000000 current reading gain
  - 0.060 current smoothing alpha
  - 2.0 A / 1.3 A no-load hysteresis thresholds
- Prototype-0 NTC validation defaults:
  - 10k fixed resistor
  - 10k nominal NTC
  - beta = 3435
  - valid ADC range = 20 mV to 3250 mV
  - valid NTC resistance range = 500 ohm to 200000 ohm
  - valid temperature range = -20.0 C to 100.0 C
- `MEAS_REG.current_valid`.
- `MEAS_REG.temperature_valid_bitmap`.
- Temperature sensor fault handling with primary fault code `0x3003`.
- Current sensor invalid handling with primary fault code `0x2003`.

Changed:

- Invalid NTC readings now appear as `FAULT` in heartbeat, `GET,TEMP`,
  dashboard, and OLED output instead of misleading negative values such as
  `-35.2 C`.
- `GET,CURRENT` now reports a current-valid flag.
- Dashboard temperature parsing now understands `FAULT`, `NAN`, and `INVALID`
  temperature tokens.

Removed or avoided:

- The blocking Prototype-0 101-sample current read was not copied into the
  core scheduler path.
- Calibration persistence commands from the monolithic sketch were not copied;
  persistent calibration still belongs in a future config/NVM service.

### Stage 9 - Board Configuration Profiles

Added:

- `bms_boards/` board profile layer.
- Board selector:
  - `bms_boards/bms_board_config.h`
- Active board profile:
  - `BMS_BOARD_PROTOTYPE0_PROFILE0`
- Prototype-0 shared hardware profile:
  - voltage divider ratios
  - voltage gain/offset arrays
  - current calibration constants
  - NTC constants
  - ESP32 ADC pins
  - OLED pins/address/display limits
- At Stage 9, placeholder profile:
  - `BMS_BOARD_PROTOTYPE0_PROFILE1`
  - reserved for the future INA226 current-sensor variant
- Board profile documentation:
  - `docs/board_profiles.md`

Changed:

- `platformio.ini` now explicitly selects `BMS_BOARD_PROTOTYPE0_PROFILE0`.
- `bms_measurement_config.h` now accepts board-profile overrides before using
  default fallback values.
- ESP32 ADC pin mapping now reads from the active board profile.
- ESP32 OLED pin/display constants now read from the active board profile.
- Boot banner now prints the compiled board name.

Removed or avoided:

- No behavior change was intended for Prototype-0 Profile0.
- At Stage 9, INA226 support was not implemented yet; Profile1 was guarded so
  it was not accidentally used with the analog INA240 current math.

### Stage 10 - Board Profile Configurator

Added:

- `bms_board_configurator.py`.
- GUI inputs for:
  - board/profile name
  - PlatformIO environment and upload port
  - voltage divider ratios
  - tap/ADC ratio calculation
  - analog INA240 current constants
  - INA226 profile values
  - NTC constants
  - ESP32 ADC pins
  - OLED pins and display constants
- Generated user profile output:
  - `bms_boards/generated/<profile_folder>/bms_board_common.h`
  - `bms_boards/generated/<profile_folder>/bms_board_profile.h`
  - `platformio.user.ini`
- GUI buttons for:
  - generate profile
  - build
  - upload
  - clean
- `platformio.user.example.ini` proving external board profile inclusion.
- `docs/board_configurator.md`.

Changed:

- `bms_boards/bms_board_config.h` now supports:
  - `BMS_BOARD_CONFIG_FILE`
- `.gitignore` now ignores:
  - `platformio.user.ini`
  - Python bytecode/cache files

Removed or avoided:

- The configurator does not edit `bms_core/`, `bms_hal/`, or platform source
  files.
- At Stage 10, the generated INA226 profile remained guarded until the firmware
  current-sensor backend existed.

### Stage 11 - Current Sensor Backend Abstraction

Added:

- `bms_current_sensor.h/.cpp`.
- Current sensor backend dispatch based on `BMS_CURRENT_SENSOR_TYPE`.
- Supported analog current backends:
  - `BMS_CURRENT_SENSOR_ANALOG_INA240`
  - `BMS_CURRENT_SENSOR_ANALOG_ACS772`
- ACS772 Hall current configuration:
  - `BMS_CURRENT_HALL_SENSITIVITY_MV_PER_A`
  - `BMS_CURRENT_SENSOR_POLARITY`
- Configurator option:
  - `analog_acs772`
- `docs/sensor_backends.md`.

Changed:

- `BMS_Measurement_UpdateCurrent()` now owns ADC acquisition only, then calls
  the current-sensor backend to convert ADC millivolts into milliamps.
- INA240 math moved out of `bms_measurement.cpp`.
- Shared analog-current filtering, no-load hysteresis, gain correction, and
  validity handling now live inside the current-sensor backend.
- `bms_boards/bms_board_config.h` now defines the ACS772 current sensor type.

Removed or avoided:

- No Arduino, ESP32, or platform APIs were added to the current-sensor backend.
- At Stage 11, INA226 was still guarded until the I2C backend could be added.

### Stage 12 - INA226 I2C Current Backend

Added:

- `bms_i2c_hal.h`.
- ESP32 Wire-backed I2C HAL adapter.
- INA226 current backend inside `bms_current_sensor.cpp`.
- INA226 calibration-register calculation from shunt resistance and expected
  current range.
- Digital current read path using the INA226 signed current register.
- Profile1 build environment:
  - `esp32dev_profile1`
- Configurator support for real `ina226` profiles.
- I2C pin and bus-speed configuration values in board profiles.

Changed:

- `BMS_BOARD_PROTOTYPE0_PROFILE1` now builds as the INA226 current-sensor
  variant instead of being a placeholder.
- `BMS_Measurement_UpdateCurrent()` now chooses analog ADC current acquisition
  or digital INA226 current acquisition through the current-sensor backend.
- Fault supervisor no longer expects the current ADC acquisition bit when the
  selected current backend is INA226.
- Missing INA226 hardware reports invalid current instead of stopping the whole
  firmware during initialization.

Removed or avoided:

- No INA226 or I2C platform calls were added to app logic or measurement math.
- No BMS core code includes Arduino, Wire, or ESP32 driver headers.
- No SoC, SoH, balancing, or production protection behavior was added.

### Stage 12.5 - Drag/Drop Configurator Workflow And Profile Cleanup

Added:

- Drag/drop hardware palette in `bms_board_configurator.py`.
- Visual board canvas with slots for:
  - MCU
  - voltage sense
  - current sense
  - temperature
  - display
- Selectable dropped blocks with `Configure Selected` navigation to the matching
  detail tab.
- Voltage divider sensing represented as an explicit voltage block:
  - `6S Divider Taps`
- Planning placeholder blocks:
  - `NXP S32K`
  - `STM32H Series`
  - `STM32F Series`
  - `TI MCU`
  - `LTC6811`
  - `BQ76952`
  - `PTC Sensor`
- Prototype-0 defaults button for quickly restoring the baseline board.
- Generated profile manifest:
  - `bms_profile_manifest.json`
- Generated profile manager panel.
- GUI actions for:
  - refreshing generated profiles
  - deleting selected generated profile files
  - removing selected PlatformIO build cache directories
- Documentation for cleaning built-in and generated PlatformIO environments.

Changed:

- Generated profiles now carry metadata such as profile folder, PlatformIO env,
  board name, dropped board components, selected blocks, and current sensor.
- The old drop-down block selector was replaced with an in-app drag/drop
  builder workflow without changing the firmware core or HAL contracts.
- Placeholder blocks can be dragged onto the board canvas, but generation is
  blocked until matching platform/sensor backends exist.

Removed or avoided:

- The cleanup actions only target `bms_boards/generated/` or `.pio/build/`.
- No generated-profile cleanup code edits core, HAL, platform, or app source.

### Stage 13 - Config/NVM Foundation

Added:

- `bms_nvm_hal.h`.
- ESP32 Preferences-backed NVM adapter:
  - `esp32_nvm_hal.cpp`
- Portable config service:
  - `bms_config.h/.cpp`
- Persistent config record with:
  - magic
  - record version
  - config version
  - config size
  - `CFG_REG` payload
  - CRC
- CRC calculation for `CFG_REG`.
- Diagnostic commands:
  - `GET,CFG`
  - `CFG,SAVE`
  - `CFG,LOAD`
  - `CFG,RESET`
- `docs/config_nvm.md`.

Changed:

- `CFG_REG` now owns voltage divider ratio, voltage gain/offset, and NTC ADC
  calibration arrays.
- Measurement conversion now reads voltage and NTC calibration from `CFG_REG`
  instead of only reading compile-time board-profile constants.
- Context config defaults are reusable so diagnostics can restore board-profile
  defaults without resetting the whole runtime context.
- App initialization attempts to load persisted config after context init and
  before first measurement.

Removed or avoided:

- No NVM or Preferences calls were added to `bms_core/`.
- No scheduler task writes flash.
- No automatic recurring config save was added.
- No production config authorization or lock/unlock policy was added yet.

### Stage 14 - Runtime Config Editing

Added:

- Diagnostic command family:
  - `CFG,SET,VOLT_RATIO,<index>,<ppm>`
  - `CFG,SET,VOLT_GAIN,<index>,<ppm>`
  - `CFG,SET,VOLT_OFFSET,<index>,<mV>`
  - `CFG,SET,NTC_GAIN,<index>,<ppm>`
  - `CFG,SET,NTC_OFFSET,<index>,<mV>`
  - `CFG,SET,CAPACITY,<mAh>`
  - `CFG,SET,THRESHOLD,<name>,<value>`
- One-based diagnostic indexes for cell/tap and temperature channels.
- Range checks inside the portable config service before edits enter `CFG_REG`.
- `CFG_REG.config_dirty` to show unsaved runtime config changes.
- Expanded `GET,CFG` output for voltage gain/offset, NTC calibration, capacity,
  thresholds, CRC, and dirty state.

Changed:

- `BMS_CONFIG_VERSION` moved to version 2 because the persisted config struct
  now includes dirty-state metadata.
- `CFG,SAVE` clears the dirty flag before writing to NVM.
- `CFG,LOAD` restores a saved config and reports it as clean.

Removed or avoided:

- No scheduler task writes flash.
- No measurement or fault code writes config directly.
- Runtime current-sensor calibration edits are still reserved for a later pass.
