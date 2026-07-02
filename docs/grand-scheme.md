# Drone BMS Firmware — Grand Scheme Roadmap

**Purpose:** Keep Codex and the development team aligned with the real project direction.  
**Current project state:** The firmware is no longer only a diagram/architecture structure. It now has a defined portable BMS spine with ESP32 implementation progress.  
**Tester firmware status:** Stage 16 PC UART tester and browser GUI started;
MicroPython embedded scaffold exists for later porting. PC tester can now use
volatile firmware-side ADC injection for bench stimulus before external tester
hardware exists. Browser profiles and JSON/PDF reports provide repeatable PC
bench evidence.
Tester firmware must not be mixed into the target BMS firmware.

---

## 1. One-Line Project Goal

Build a **portable, MCU-agnostic, sensor-agnostic Drone BMS firmware platform** that can start on ESP32, then migrate to NXP/STM32/TI/AFE-based hardware without rewriting the core BMS logic.

The firmware must support:

- Voltage monitoring
- Current monitoring
- Temperature monitoring
- Runtime register map
- Scheduler-driven execution
- Fault supervision
- Diagnostics
- Config/calibration workflow
- Sleep/wake policy
- Future SoC/SoH estimation
- Future protection output control
- Future diagnostic tester firmware
- Future AFE and CAN integration

---

## 2. Current Grand-Scheme Position

The project is not at the beginning anymore. The architecture phase is mostly complete, and the codebase now has a real firmware spine.

Estimated current position:

| Area | Estimated Completion |
|---|---:|
| Architecture/design thinking | 80–85% |
| Portable firmware spine | 65–70% |
| ESP32 target firmware for bench prototype | 50–60% |
| Hardware-calibrated reliable BMS firmware | 35–45% |
| Full system including tester firmware | 25–35% |
| Production/flight-ready Drone BMS | 20–30% |

Overall project position:

> The project is roughly **35% complete toward the ultimate BMS firmware system**, but the **core firmware foundation is around 65% complete**.

This means the current priority is not adding random features. The priority is making the existing measurement/config/fault spine trustworthy.

---

## 3. What Is Already Done

The current target firmware has moved beyond a simple `setup()` / `loop()` style prototype.

The firmware already includes a meaningful spine:

- Portable BMS core structure
- Runtime register map
- ESP32 PlatformIO project
- ESP32 platform adapter layer
- Timer-driven scheduler
- 1 ms base tick concept
- Foreground task dispatcher
- Register snapshot system
- ADC HAL
- UART HAL
- I2C HAL
- NVM HAL
- Display HAL
- Lock HAL
- Real ESP32 ADC measurement path
- Voltage tap measurement
- Current measurement path
- NTC temperature measurement
- Fault supervisor
- Fault code table
- Diagnostic UART commands
- Sleep policy register and decision reporting
- Board profile system
- Python board configurator
- INA240 / ACS772 / INA226 current backend support
- Config save/load/reset through NVM
- Runtime `CFG,SET,...` diagnostic editing
- First Stage 15 measurement validation truth layer
- Stage 16 diagnostic ADC injection for PC tester stimulus
- Dashboard/logging tooling

The firmware direction is now closer to:

```text
HAL → scheduler → measurement → registers → fault → diagnostic → config
```

It is no longer just:

```text
setup() → loop() → read ADC → print values
```

---

## 4. What Is Not Done Yet

The following are still not complete and should not be claimed as finished:

- Full embedded tester firmware automation and external hardware stimulus
- Hardware-proven validation thresholds
- Real sleep/wake implementation
- SoC algorithm
- SoH qualification
- Current-sensor runtime calibration editing
- Dashboard/configurator runtime config UI
- AFE backend for LTC6811/BQ76952
- Protection output layer
- CAN communication layer
- Unit tests / hardware-in-loop tests
- Final validation evidence
- Production/flight-ready behavior

The biggest immediate missing piece is:

> Measurement trust.

The firmware can read, convert, report, configure, and fault. But before fault logic, SoC, sleep, or protection can be trusted, the measurement system must decide whether a value is physically believable.

---

## 5. Core Development Rule

Do not add features just because the structure exists.

Every next stage must answer:

1. Can the firmware measure correctly?
2. Can the firmware prove whether a measurement is valid?
3. Can the firmware report why a measurement is invalid?
4. Can fault logic trust the measurement?
5. Can diagnostics expose the truth clearly?
6. Can the calibration workflow be repeated safely?

---

# 6. Major Phases

---

## Phase 1 — Architecture Foundation

**Status:** Mostly done.

### Major objective

Create the reusable firmware platform structure.

### Already done

- Folder structure
- Core / HAL / platform separation
- Register map
- Scheduler
- Diagnostic commands
- Board profile system
- Config service
- Fault code structure
- ESP32 PlatformIO build structure

### Remaining minor objectives

- Make naming consistent.
- Remove unused placeholders.
- Confirm all modules compile cleanly.
- Confirm no platform calls exist inside `bms_core/`.
- Update documentation from architecture-only to implementation-aware.
- Keep generated build folders out of source control where possible.

### Codex rule

Codex must not collapse the architecture into one monolithic `main.cpp`.

---

## Phase 2 — Target Firmware Functional Foundation

**Status:** Partially done.

### Major objective

Make the ESP32 BMS target firmware run as a real bench prototype.

### Already done

- ADC measurement path
- Voltage/current/temp conversion
- Diagnostic UART
- Fault supervisor
- OLED/dashboard support
- Config/NVM
- Board profiles
- Runtime calibration commands

### Remaining minor objectives

- Production-tuned measurement validation thresholds
- SoC calculation
- Better current calibration workflow
- Clean fault-clear/latch policy
- State-machine hardening
- Profile switching: active → idle → sleep-ready
- Clear diagnostic reporting for validity and fault state

### Codex rule

Codex can improve services, but must not introduce direct ESP32/Arduino APIs into portable core modules.

---

## Phase 3 — Measurement Truth and Calibration

**Status:** First implementation done; hardware confirmation is next.

### Major objective

Make measured values trustworthy before faults, SoC, sleep, or protection depend on them.

This remains the most important active phase until hardware validation confirms
the thresholds and invalid-reason behavior.

### Why this matters

Pack voltage may be close, but individual cell values still require validation. The firmware must know when a reading is valid, invalid, stuck, floating, out of order, or physically impossible.

### Minor objectives

The first measurement validation service now exists:

```text
bms_core/bms_measurement_validation.h
bms_core/bms_measurement_validation.cpp
```

Current register additions:

```text
MEAS_REG.cell_valid_bitmap
MEAS_REG.tap_valid_bitmap
MEAS_REG.current_valid
MEAS_REG.temperature_valid_bitmap
ACQ_REG.stuck_bitmap
```

Future validation fields may include:

```text
ACQ_REG.timeout_bitmap
```

Do not add fields blindly; add only what is required by the actual validation
logic.

### Voltage validation objectives

- Validate cumulative tap order.
- Detect non-monotonic taps.
- Validate tap physical range.
- Validate reconstructed cell physical range.
- Detect impossible cell voltage.
- Detect sudden jump between samples.
- Detect stuck/floating ADC channel.
- Add `tap_valid_bitmap`.
- Add `cell_valid_bitmap`.
- Make `GET,TAPS` and `GET,VOLT` show validity clearly.

### Current validation objectives

- Add current sensor valid flag.
- Validate plausible current range.
- Detect ADC saturation.
- Detect no-load instability.
- Add no-load hysteresis.
- Add current calibration status.
- Ensure current faults only depend on valid current readings.

### Temperature validation objectives

- Detect NTC open circuit.
- Detect NTC short circuit.
- Validate plausible temperature range.
- Add `temperature_valid_bitmap`.
- Ensure temperature faults only depend on validated temperature readings.

### Fault integration objectives

- Fault supervisor must not trust raw conversions directly.
- Fault supervisor should consume validated measurement status.
- Invalid measurement should create acquisition/sensor fault, not fake a safe value.
- Do not hide invalid readings by forcing them to normal-looking values.

### Expected diagnostic output examples

```text
RESP,TAPS,ADC_MV=[...],TAP_MV=[...],TAP_VALID=0x3F,CELL_VALID=0x3F
RESP,VOLT,CELL_MV=[...],VALID=0x3F,PACK_MV=...
RESP,FAULT,PRIMARY=0x4002,...
```

### Hard rules

- Do not add MOSFET/protection output behavior yet.
- Do not add balancing yet.
- Do not fake SoH.
- Do not let fault supervisor trust invalid measurements.
- Do not silently clamp bad values to safe-looking values.

---

## Phase 4 — Diagnostic Tester Firmware

**Status:** Started with a separate PC UART tester and a MicroPython embedded
scaffold.

### Major objective

Build a separate tester MCU firmware that can stimulate, command, and verify the BMS target.

Tester firmware is not the same as target firmware.

### Tester firmware role

```text
Inject known signal
→ send UART command
→ read BMS response
→ compare expected result
→ print PASS/FAIL
```

### Minor objectives

- Create separate tester project.
- Implement UART master command sender. First PC tester exists.
- Implement command menu or scripted tests. First PASS/FAIL suite exists.
- Use the browser GUI as the current manual tester surface.
- Read BMS responses. First `RESP,...` parser exists.
- Parse:
  - `GET,VOLT`
  - `GET,TAPS`
  - `GET,CURRENT`
  - `GET,TEMP`
  - `GET,FAULT`
  - `GET,CFG`
- Compare expected vs actual.
- Print PASS/FAIL.
- Add report logging.
- Add current mV injection support later.
- Add voltage/temp simulation later.
- Add automated test sequences.

### Recommended timing

Do not expand tester firmware beyond UART PASS/FAIL until Stage 15 measurement
validation remains stable on the bench. Otherwise, the tester will only test
untrusted values.

### Codex rule

Tester firmware must live in its own project/folder. Do not mix tester firmware into the BMS target firmware core.

---

## Phase 5 — SoC / Estimation

**Status:** Not implemented.

### Major objective

Calculate battery state from validated measurements.

SoC must come after measurement validation, because bad voltage/current data will produce bad SoC.

### Minor objectives

- Add voltage-based SoC lookup table.
- Add coulomb-counting accumulator.
- Track `used_mAh`.
- Track `used_mWh`.
- Calculate pack power.
- Calculate C-rate.
- Handle initial SoC assumption.
- Add reset/recalibration command.
- Mark `soc_valid` only when inputs are valid.
- Do not claim production SoC until validated.

### Suggested implementation path

Initial:

```text
Voltage-based SoC estimate
```

Next:

```text
Coulomb counting using current integration
```

Later:

```text
Hybrid correction using voltage rest condition
```

### SoH rule

SoH must remain unqualified until there is enough long-term data:

- cycle history
- capacity trend
- internal resistance trend
- temperature aging history
- validated capacity test

Do not print fake `SoH = 100%`.

Use:

```text
SOH=N/A
SOH_VALID=0
SOH_METHOD=NOT_AVAILABLE
```

---

## Phase 6 — Sleep/Wake Implementation

**Status:** Sleep decision/reporting exists; real sleep/wake is not done.

### Major objective

Move from sleep decision reporting to actual controlled sleep/wake behavior.

### Minor objectives

- Implement active → idle profile switching.
- Implement idle → sleep-ready transition.
- Stop fast scheduler before sleep.
- Save runtime snapshot before sleep.
- Arm wake sources.
- Enter ESP32 sleep mode.
- Restore after wake.
- Record wake cause.
- Reinitialize required peripherals.
- Requalify sensors after wake.
- Deny sleep during:
  - critical fault
  - diagnostic command
  - active load
  - communication session
  - untrusted measurement state

### Hard rule

Sleep is not a function call after measurement.

Sleep is allowed only after state-machine and sleep-policy approval.

### Codex rule

Do not implement deep sleep before validation and state handling are stable.

---

## Phase 7 — Protection and Output Control

**Status:** Not implemented.

### Major objective

Convert fault decisions into safe output actions.

This is high-risk and must not be rushed.

### Minor objectives

- Define protection request interface.
- Define CHG/DSG output states.
- Define MOSFET/gate-driver control abstraction.
- Define no-cutoff modes for drone/flight safety.
- Define fault severity behavior.
- Define latch/clear/requalification rules.
- Add hardware output HAL.
- Test with dummy GPIO first.
- Only then connect real protection hardware.

### Drone-specific safety note

For drone use, blindly cutting output can be dangerous during flight. Protection behavior must be defined carefully and may need warning/telemetry/fail-safe strategy instead of immediate cutoff in every case.

---

## Phase 8 — AFE / Future Sensor Migration

**Status:** Architecture-ready; not implemented.

### Major objective

Allow future LTC6811 / BQ76952 / other AFE backend without rewriting core logic.

### Minor objectives

- Create AFE voltage source interface.
- Create AFE temperature source interface.
- Create AFE current/fault/status mapping if required.
- Create SPI/I2C backend as needed.
- Map AFE cell readings to `MEAS_REG`.
- Map AFE faults to `FAULT_REG`.
- Keep measurement/fault/scheduler logic unchanged.
- Ensure AFE backend is selected by board profile or build environment.

### Codex rule

Do not hard-code AFE behavior into measurement service. It must enter through a sensor backend interface.

---

## Phase 9 — CAN / Host Communication

**Status:** Not implemented.

### Major objective

Add future host/drone-controller communication without breaking UART diagnostic flow.

### Minor objectives

- Add CAN HAL.
- Define CAN frame map.
- Define pack status frame.
- Define cell summary frame.
- Define fault frame.
- Define configuration/diagnostic frame if needed.
- Add timeout and bus-off handling.
- Keep UART diagnostic path available for internal debug.

### Rule

CAN is a transport layer. It should not rewrite BMS core logic.

---

## Phase 10 — Production Validation

**Status:** Not started.

### Major objective

Prove the firmware behaves correctly under real and simulated failure conditions.

### Minor objectives

- Unit tests for conversion functions.
- Unit tests for fault supervisor.
- Unit tests for config range checks.
- Unit tests for validation layer.
- Hardware-in-loop tests.
- Current injection tests.
- Voltage tap fault tests.
- NTC open/short tests.
- UART diagnostic timeout tests.
- NVM save/load/reset tests.
- Watchdog/overrun tests.
- Sleep/wake tests.
- Long-duration logging.
- Thermal validation.
- EMI validation.
- Protection output validation.
- Regression test checklist.

---

# 7. Immediate Priority Order

The next work should be executed in this order.

## Priority 1 — Freeze Current Code State

### Objective

Create a known baseline after the first Stage 15 validation implementation.

### Tasks

- Tag current code as Stage 15 / Rev 1.3 baseline.
- Confirm it builds.
- Clean generated junk from repo if needed.
- Confirm `.pio/` is not tracked.
- Confirm `.gitignore` excludes build/cache outputs.
- Document actual modules.

### Suggested tag

```text
stage-15-measurement-validation-baseline
```

---

## Priority 2 — Hardware Calibration Closure

### Objective

Close the truth gap between firmware and multimeter on top of Stage 15
validation.

### Tasks

- Confirm voltage tap ADC mV against measured tap inputs.
- Confirm reconstructed cell mV against multimeter readings.
- Confirm pack voltage against multimeter.
- Confirm current zero point and known-current readings.
- Confirm NTC readings against known temperature or known resistance.
- Record valid bitmaps and invalid-reason bitmaps for each test.

This is the most important next engineering step.

---

## Priority 3 — Validation Threshold Tuning

### Objective

Tune validation thresholds using real bench data without weakening fault truth.

### Tasks

- Review false positives and false negatives from Stage 15 bench tests.
- Adjust broad physical limits only when evidence supports the change.
- Confirm disconnected/floating channels report invalid.
- Confirm sudden jumps are detected without breaking normal startup behavior.
- Keep all threshold changes documented.

---

## Priority 4 — Documentation Update

### Objective

Update the document from architecture-only to implementation-aware.

### Tasks

Create or refresh Rev 1.3 document sections:

- Current Firmware Implementation Status
- Actual Codebase Folder Structure
- Implemented Core Spine
- PlatformIO Build Environment
- ESP32 Platform Adapter Status
- Scheduler Implementation Status
- Register Map Implementation Status
- HAL Implementation Status
- Sensor Source Implementation Status
- Telemetry / Diagnostic Status
- Implemented vs Planned Feature Matrix
- Known Gaps and Next Implementation Steps
- Code-to-Architecture Traceability

---

## Priority 5 — Tester Firmware

### Objective

Extend the separate tester firmware after measurement validation is stable.

### Tasks

- Run the PC UART tester on the BMS diagnostic COM port.
- Confirm command/response timing without the dashboard connected.
- Add manual commands.
- Add automated tests.
- Add PASS/FAIL reporting.

---

# 8. Codex Development Rules

Codex must obey these rules while editing the codebase.

## Hard architecture rules

- Do not put ESP32/Arduino calls inside `bms_core/`.
- Do not use `Serial` inside `bms_core/`.
- Do not use `analogRead` inside `bms_core/`.
- Do not use `millis()` inside `bms_core/`.
- Do not use `delay()` inside `bms_core/`.
- Do not write flash automatically from scheduler tasks.
- Do not allocate heap memory in ISR or fast periodic tasks.
- ISR must only update tick/task flags.
- Heavy work must run in foreground scheduler dispatch.
- Fault supervisor must not trust raw/unvalidated values.
- Do not fake SoH.
- Do not add protection output until validation and fault policy are stable.
- Do not mix tester firmware into target firmware.

## Boundary rule

Platform-specific code belongs in:

```text
bms_platform/esp32/
```

Portable code belongs in:

```text
bms_core/
bms_hal/
bms_boards/
```

Sensor-specific backend code must remain behind sensor abstraction.

---

# 9. Codex Task Prompts

Use these prompts one stage at a time.

## Task A — Baseline Audit

```text
Review the current Drone_BMS_Firmware codebase. Do not change functionality. Produce a short audit of implemented modules, build environments, and any platform-specific calls that appear outside bms_platform/esp32. Confirm whether bms_core contains Arduino, Serial, analogRead, millis, delay, Preferences, or Wire usage.
```

## Task B — Stage 15 Validation Design

```text
Design Stage 15 measurement validation for the current codebase. Add only the minimal new types and fields needed to represent tap validity, cell validity, current validity, and temperature validity. Do not implement protection output, balancing, SoC, or SoH. Keep all platform-specific code out of bms_core.
```

## Task C — Stage 15 Implementation

```text
Implement bms_measurement_validation.h/.cpp in bms_core. Validate voltage taps, reconstructed cells, current, and temperature using the existing register/config structures. Update diagnostic output to expose validity status. Ensure the fault supervisor uses validated values instead of trusting raw conversions.
```

## Task D — Calibration Closure

```text
Improve the voltage calibration workflow without changing hardware. Use existing GET,TAPS and CFG,SET workflows. Make output clear enough to compare firmware ADC mV, calculated tap mV, reconstructed cell mV, and validity bitmaps against multimeter readings.
```

## Task E — Documentation Sync

```text
Update docs to reflect the current implementation status. Do not overclaim production readiness. Mark tester firmware, SoC, SoH, real sleep/wake, CAN, AFE, and protection output as future stages.
```

---

# 10. Definition of Done for Stage 15 Baseline

The first Stage 15 implementation is done only when:

- `pio run` succeeds for the active environments.
- `bms_core/` has no direct platform calls.
- Voltage tap validity is visible.
- Cell validity is visible.
- Current validity is visible.
- Temperature validity is visible.
- Fault supervisor does not trust invalid measurements.
- Diagnostics expose invalid reasons clearly.
- No bad reading is hidden by clamping it into a safe-looking value.
- The firmware can explain why a value is invalid.
- Calibration workflow can be repeated using `GET,TAPS`, `GET,CFG`, `CFG,SET`, and `CFG,SAVE`.

---

# 11. Current Honest Status Statement

Use this statement in review or documentation:

> The firmware has progressed beyond architecture diagrams into an implementation-aware portable BMS spine. The ESP32 target now includes scheduler-driven measurement, runtime registers, diagnostics, configuration/NVM workflow, board profiles, current sensor backend support, preliminary fault supervision, and a first Stage 15 measurement validation truth layer. The next critical step is not adding more features, but closing hardware calibration and threshold evidence so fault logic, future SoC, sleep policy, and protection behavior only depend on trusted values.

---

# 12. Ultimate Goal

The ultimate goal is not only to make values print.

The final goal is:

```text
Trusted measurement
→ validated state estimation
→ reliable fault classification
→ controlled diagnostics
→ safe sleep/wake behavior
→ configurable hardware abstraction
→ repeatable tester validation
→ future AFE/CAN/protection integration
→ production-ready evidence
```

The next step toward that goal is:

```text
Hardware calibration closure on top of Stage 15 validation
```
