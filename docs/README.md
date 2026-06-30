# Drone BMS Firmware

This folder contains the portable Drone BMS firmware library and the ESP32 first
platform adapter.

Current stage: Stage 8 sleep policy stub.

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
- Thin Arduino `setup()`/`loop()` wrapper.
- Minimal UART HAL interface.
- ESP32 UART HAL implementation that prints the boot banner.

Not implemented yet:

- Deep sleep.
- Wake-source policy.
- SoC algorithm.
- SoH algorithm.

Preferred build command when PlatformIO is installed:

```powershell
pio run -d Drone_BMS_Firmware
```
