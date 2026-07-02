# Drone BMS Firmware

This folder contains the portable Drone BMS firmware library and the ESP32 first
platform adapter.

Current stage: Stage 16 tester firmware foundation.

Implemented now:

- Portable BMS type definitions.
- Portable status codes.
- Runtime register map structs.
- BMS context initialization and default register values.
- Register snapshot capture API.
- Register enum-to-string helpers.
- Boot-time default register snapshot printout.
- Timer HAL interface.
- ESP32 hardware timer adapter for a 1 ms base tick.
- Lock HAL interface and ESP32 critical-section adapter.
- Core scheduler profiles and ISR-driven due flags.
- Foreground scheduler flag consumption in `BMS_App_Run()`.
- Low-rate scheduler heartbeat output.
- Fake measurement service that writes safe default values into `MEAS_REG`.
- Scheduler-driven fake current, voltage, and temperature updates.
- Measurement heartbeat output from register snapshots.
- ADC HAL interface.
- ESP32 ADC adapter with pin mapping in `esp32_pin_config.h`.
- Real ADC-backed voltage, current, and NTC temperature conversion paths.
- Acquisition register updates for raw ADC, ADC millivolts, valid bitmap, and
  sample counters.
- Stable fault-code definitions and warning/fault bit masks.
- Fault supervisor service for voltage, current, temperature, and sensor-valid
  checks.
- Fault heartbeat output with warning bitmap, active bitmap, latched bitmap,
  primary fault code, severity, and event counter.
- Non-blocking UART receive HAL.
- Diagnostic UART parser with fixed command buffer.
- Diagnostic responses for snapshot, voltage, current, temperature, and fault
  state.
- Fault-code table documentation.
- Sleep policy service.
- `SLEEP_REG` sleep decision and reason reporting.
- Scheduler-driven sleep policy evaluation.
- Diagnostic sleep response through `GET,SLEEP`.
- Prototype-0 board profile selection through `bms_boards/`.
- Active board profile: `BMS_BOARD_PROTOTYPE0_PROFILE0`.
- INA226 board profile: `BMS_BOARD_PROTOTYPE0_PROFILE1`.
- External generated board profile support through `BMS_BOARD_CONFIG_FILE`.
- Python board profile configurator: `bms_board_configurator.py`.
- Configurator drag/drop hardware builder and generated-profile cleanup tools.
- Current sensor backend abstraction.
- Analog current backends:
  - INA240 shunt amplifier
  - ACS772 Hall sensor
- I2C HAL interface.
- ESP32 Wire-backed I2C HAL adapter.
- Digital INA226 current-sensor backend.
- NVM HAL interface.
- ESP32 Preferences-backed NVM adapter.
- Portable config service with CRC, load, save, and reset behavior.
- Diagnostic config commands:
  - `GET,CFG`
  - `CFG,SET,...`
  - `CFG,SAVE`
  - `CFG,LOAD`
  - `CFG,RESET`
- Runtime config edits for voltage calibration, NTC ADC calibration, capacity,
  and fault thresholds with range checks and dirty-state reporting.
- Measurement validation service for tap, cell, current, and temperature
  validity.
- Validation bitmaps and invalid-reason bitmaps in the runtime register map.
- Fault supervisor gating so voltage faults do not trust invalid tap/cell data.
- Diagnostic and dashboard visibility for validation state.
- PC UART tester in `tester_firmware/pc_uart_tester/`.
- Browser GUI for the PC UART tester.
- MicroPython UART tester scaffold in
  `tester_firmware/micropython_uart_tester/`.
- First tester PASS/FAIL checks for Stage 15 validity outputs.
- Volatile firmware-side ADC injection for PC tester stimulus.
- Saved PC tester profiles and automated JSON/PDF test reports.
- PC tester run history and fault-code exclusions in GUI, CLI, and
  MicroPython scaffold.
- Thin Arduino `setup()`/`loop()` wrapper.
- Minimal UART HAL interface.
- ESP32 UART HAL implementation that prints the boot banner.

Not implemented yet:

- Deep sleep.
- Wake-source policy.
- SoC algorithm.
- SoH algorithm.
- Dashboard/configurator forms for runtime config edits.
- Production-qualified validation thresholds and hardware-in-loop evidence.
- External analog stimulus hardware in tester firmware.
- Embedded ESP32 tester firmware port.
- Embedded/CI automated regression test reporting.

Preferred build command when PlatformIO is installed:

```powershell
pio run -d Drone_BMS_Firmware
```
