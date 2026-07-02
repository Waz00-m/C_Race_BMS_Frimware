# Next Objectives

This file tracks the next work after the Stage 1 to Stage 8 firmware foundation.
The current priority is hardware truth, not more architecture.

## Current Position

- Stage 1 to Stage 8 firmware foundation is complete.
- ESP32 runs the portable BMS firmware on the Prototype-0 PCB.
- Prototype-0 firmware and the new portable firmware show similar measured cell
  patterns.
- Pack voltage is close to the expected total pack voltage.
- Per-cell values are still wrong compared with manual multimeter readings.

## Observed Hardware Snapshot

Manual multimeter cell readings:

| Cell | Multimeter |
| --- | ---: |
| C1 | 3.61 V |
| C2 | 3.59 V |
| C3 | 3.16 V |
| C4 | 3.61 V |
| C5 | 3.60 V |
| C6 | 3.61 V |

New portable firmware dashboard snapshot:

| Cell | Firmware |
| --- | ---: |
| C1 | 3.582 V |
| C2 | 3.453 V |
| C3 | 3.703 V |
| C4 | 3.633 V |
| C5 | 2.706 V |
| C6 | 4.232 V |

Prototype-0 dashboard snapshot:

| Cell | Prototype-0 |
| --- | ---: |
| C1 | 3.5794 V |
| C2 | 3.4960 V |
| C3 | 3.6729 V |
| C4 | 3.6482 V |
| C5 | 2.9206 V |
| C6 | 4.0674 V |

## Most Likely Issue

The pack voltage is approximately correct, while individual cells are wrong.
Both firmware versions show a similar pattern. That points away from the new
firmware architecture and toward the voltage tap conversion path.

Most likely causes:

- Per-channel divider ratios are not calibrated to the actual PCB resistor
  values.
- The cumulative tap math is amplifying small tap-voltage errors into large
  per-cell errors.
- One or more tap channels may be mapped to the wrong ESP32 ADC pin.
- The PCB tap network may have loading, leakage, solder, connector, or resistor
  tolerance issues.
- ESP32 ADC nonlinearity and attenuation error are affecting high divider
  readings.

## Objective 1 - Capture Raw Tap Truth Table

For each voltage tap channel, record these values at the same time:

| Tap | Battery-side tap voltage from pack negative | ESP32 ADC pin | ADC mV reported by firmware |
| --- | ---: | --- | ---: |
| Tap 1 | 3.164 V | GPIO36 | TBD |
| Tap 2 | 7.210 V | GPIO39 | TBD |
| Tap 3 | 10.810 V | GPIO34 | TBD |
| Tap 4 | 14.410 V | GPIO35 | TBD |
| Tap 5 | 18.020 V | GPIO32 | TBD |
| Tap 6 | 21.260 V | GPIO33 | TBD |

Expected battery-side cumulative taps from the current multimeter cell readings:

| Tap | Expected cumulative voltage |
| --- | ---: |
| Tap 1 | 3.61 V |
| Tap 2 | 7.20 V |
| Tap 3 | 10.36 V |
| Tap 4 | 13.97 V |
| Tap 5 | 17.57 V |
| Tap 6 | 21.18 V |

## Calibration Session Notes

### 2026-06-30 - ADC Pin Measurements

ESP32 installed on Prototype-0 PCB. User measured ESP32 ADC pin voltages using a
new multimeter after the previous meter was damaged during a short/arc event.

| Channel | ESP32 pin | DMM voltage at ADC pin |
| --- | --- | ---: |
| ADC1 / VC1 | GPIO36 | 2.579 V |
| ADC2 / VC2 | GPIO39 | 2.545 V |
| ADC3 / VC3 | GPIO34 | 2.530 V |
| ADC4 / VC4 | GPIO35 | 2.524 V |
| ADC5 / VC5 | GPIO32 | 2.330 V |
| ADC6 / VC6 | GPIO33 | 2.549 V |

Notes:

- These are ADC pin voltages only.
- Battery-side cumulative tap voltages are still required before divider ratios
  can be finalized.
- Do not measure resistance on the live battery board.
- Use insulated probes or clip leads where possible; one probe slip can short
  adjacent balance taps.

### 2026-06-30 - Battery-Side Tap Measurements

Measured from pack negative / B- using the new multimeter:

| Tap | Battery-side tap voltage |
| --- | ---: |
| VC1 | 3.164 V |
| VC2 | 7.210 V |
| VC3 | 10.810 V |
| VC4 | 14.410 V |
| VC5 | 18.020 V |
| VC6 | 21.260 V |

Cells reconstructed from these cumulative taps:

| Cell | Voltage from tap subtraction |
| --- | ---: |
| C1 | 3.164 V |
| C2 | 4.046 V |
| C3 | 3.600 V |
| C4 | 3.600 V |
| C5 | 3.610 V |
| C6 | 3.240 V |

First-pass effective divider ratios from battery-side tap voltage divided by
DMM-measured ADC pin voltage:

| Channel | Ratio | Ratio ppm |
| --- | ---: | ---: |
| VC1 / GPIO36 | 1.226832 | 1226832 |
| VC2 / GPIO39 | 2.833006 | 2833006 |
| VC3 / GPIO34 | 4.272727 | 4272727 |
| VC4 / GPIO35 | 5.709192 | 5709192 |
| VC5 / GPIO32 | 7.733906 | 7733906 |
| VC6 / GPIO33 | 8.340526 | 8340526 |

Important:

- These ratios are based on DMM ADC-pin voltages, not yet on
  `analogReadMilliVolts()` values reported by the ESP32.
- Firmware constants should be finalized after collecting `GET,TAPS` output.
- VC1 is very different from the original assumed ratio and should be
  double-checked for resistor value, net mapping, or probe/reference error.

### 2026-06-30 - Firmware `GET,TAPS` Calibration Capture

Firmware response before ratio update:

```text
RESP,TAPS,ADC_MV=[2875,2822,2805,2784,2507,2829],TAP_MV=[3872,7600,11567,15401,18150,22930],CELL_MV=[3872,3728,3967,3834,2749,4780]
```

Ratios calculated from battery-side tap voltage divided by firmware-reported
ADC mV:

| Channel | Tap mV | Firmware ADC mV | Applied ratio ppm |
| --- | ---: | ---: | ---: |
| VC1 / GPIO36 | 3164 | 2875 | 1100522 |
| VC2 / GPIO39 | 7210 | 2822 | 2554926 |
| VC3 / GPIO34 | 10810 | 2805 | 3853832 |
| VC4 / GPIO35 | 14410 | 2784 | 5176006 |
| VC5 / GPIO32 | 18020 | 2507 | 7187874 |
| VC6 / GPIO33 | 21260 | 2829 | 7515023 |

Firmware change:

- Updated `BMS_DEFAULT_VOLTAGE_DIVIDER_RATIO_PPM` to the applied ratio ppm
  values above.
- Reset `BMS_DEFAULT_VOLTAGE_GAIN_PPM` to `1000000` for all voltage channels.

Expected next `GET,TAPS` result if ADC readings remain similar:

```text
TAP_MV=[3164,7210,10810,14410,18020,21260]
CELL_MV=[3164,4046,3600,3600,3610,3240]
```

Remaining concern:

- The cumulative tap-derived cells still differ from the earlier individual
  cell list. After the firmware matches the measured taps, re-check individual
  cell voltage directly across each adjacent cell pair.

### 2026-06-30 - Second `GET,TAPS` Calibration Capture

Firmware response after the first ratio update:

```text
RESP,TAPS,ADC_MV=[2790,2748,2732,2703,2457,2721],TAP_MV=[3070,7020,10528,13990,17660,20448],CELL_MV=[3070,3950,3508,3462,3670,2788]
```

The computed taps were still low versus the measured battery-side target taps.
Applied second-pass ratios using the same target tap voltages:

| Channel | Target tap mV | Firmware ADC mV | Applied ratio ppm |
| --- | ---: | ---: | ---: |
| VC1 / GPIO36 | 3164 | 2790 | 1134050 |
| VC2 / GPIO39 | 7210 | 2748 | 2623726 |
| VC3 / GPIO34 | 10810 | 2732 | 3956808 |
| VC4 / GPIO35 | 14410 | 2703 | 5331114 |
| VC5 / GPIO32 | 18020 | 2457 | 7334147 |
| VC6 / GPIO33 | 21260 | 2721 | 7813304 |

Expected next `GET,TAPS` result if ADC readings remain similar:

```text
TAP_MV=[3164,7210,10810,14410,18020,21260]
CELL_MV=[3164,4046,3600,3600,3610,3240]
```

### 2026-06-30 - Third `GET,TAPS` Calibration Capture

Firmware response after the second ratio update:

```text
RESP,TAPS,ADC_MV=[2794,2746,2730,2722,2455,2759],TAP_MV=[3168,7204,10802,14511,18005,21556],CELL_MV=[3168,4036,3598,3709,3494,3551]
```

VC1, VC2, VC3, and VC5 were close to target. VC4 and VC6 were still high.
Applied third-pass ratios:

| Channel | Target tap mV | Firmware ADC mV | Applied ratio ppm |
| --- | ---: | ---: | ---: |
| VC1 / GPIO36 | 3164 | 2794 | 1132427 |
| VC2 / GPIO39 | 7210 | 2746 | 2625637 |
| VC3 / GPIO34 | 10810 | 2730 | 3959707 |
| VC4 / GPIO35 | 14410 | 2722 | 5293902 |
| VC5 / GPIO32 | 18020 | 2455 | 7340122 |
| VC6 / GPIO33 | 21260 | 2759 | 7705690 |

Expected next `GET,TAPS` result if ADC readings remain similar:

```text
TAP_MV=[3164,7210,10810,14410,18020,21260]
CELL_MV=[3164,4046,3600,3600,3610,3240]
```

## Objective 2 - Verify Pin And Channel Mapping

Confirm that the PCB voltage tap outputs really connect to the configured pins:

- Cell/tap 1: GPIO36
- Cell/tap 2: GPIO39
- Cell/tap 3: GPIO34
- Cell/tap 4: GPIO35
- Cell/tap 5: GPIO32
- Cell/tap 6: GPIO33

If any PCB net does not match this order, update the active board profile in
`bms_boards/prototype0_common/bms_prototype0_common.h`.

## Objective 3 - Calibrate Voltage Divider Ratios

After the raw truth table is captured, compute each effective divider ratio:

```text
effective_ratio = battery_side_tap_mV / adc_pin_mV
```

Then update `BMS_DEFAULT_VOLTAGE_DIVIDER_RATIO_PPM` in the active board
profile and remove the temporary global gain correction if it is no longer
needed.

## Objective 4 - Add A Diagnostic Tap Command

Add a temporary firmware diagnostic command for calibration:

```text
GET,TAPS
```

The response should show:

```text
RESP,TAPS,ADC_MV=[...],TAP_MV=[...],CELL_MV=[...]
```

This will make calibration easier than reading mixed heartbeat lines.

Status: implemented in firmware after this calibration session.

## Objective 5 - Add Validation Before Fault Decisions

Status: first Stage 15 validation layer implemented and confirmed on
Prototype-0 profile0 bench hardware. Threshold tuning remains only if real
hardware creates false positives.

The fault supervisor no longer trusts converted voltage values unless tap and
cell validity bitmaps show all voltage channels are valid. Validation now covers:

- Tap order monotonicity.
- Cell voltage physical range.
- Sudden step changes.
- Missing or stuck ADC channels.
- Current and temperature validity/reason reporting.

Remaining work before production protection truth:

- Confirm validation behavior on floating/disconnected ESP32 inputs.
- Tune thresholds if real hardware creates false positives.
- Add richer calibration-complete status later if needed.

## Objective 6 - Current And Temperature Calibration

After voltage taps are corrected:

- Calibrate current sensor zero point with no load.
- Calibrate current gain with a known load.
- Verify NTC topology and beta constants.
- Handle open/short temperature sensor faults cleanly.

## Objective 7 - Prototype-0 Feature Parity

Only after measurement truth is acceptable:

- Decide whether to port OLED display behavior.
- Decide whether to preserve Prototype-0 CSV output as a compatibility mode.
- Decide the next production-facing telemetry packet format.

## Objective 8 - Post Stage 15 Board Profile Work

After Stage 9 through Stage 15, the next architecture work is:

- Keep `BMS_BOARD_PROTOTYPE0_PROFILE0` as the calibrated analog INA240
  Prototype-0 baseline.
- Continue the sensor backend selection layer beyond current sensing.
- Validate the INA226 backend on `BMS_BOARD_PROTOTYPE0_PROFILE1` hardware once
  that PCB/profile exists.
- Add future AFE voltage/current backend support, such as LTC6811.
- Continue improving the GUI configurator from the Stage 12.5 drag/drop board
  builder toward richer hardware modules, compatibility checks, and generated
  backend scaffolding.
- Use the Stage 14/15 diagnostic workflow for hardware calibration closure.
- Add dashboard/configurator forms on top of runtime config commands.
- Extend the Stage 16 PC UART tester from PASS/FAIL smoke tests toward richer
  scripted bench tests.

## Objective 9 - Stage 16 Tester Firmware Foundation

Status: PC UART tester and browser GUI are active in
`tester_firmware/pc_uart_tester/`. An embedded MicroPython scaffold also exists
for later porting.

The first tester scope is:

- Send `GET,TAPS`, `GET,VOLT`, `GET,CURRENT`, `GET,TEMP`, and `GET,FAULT`.
- Send `GET,INJECT` and `DIAG,ADC,...` for volatile firmware-side ADC
  stimulus.
- Parse `RESP,...` diagnostic lines.
- Check strict Stage 15 profile0 validity outputs.
- Allow known faults only through an explicit tester-side exclusion toggle and
  entered fault codes from `GET,FAULT CODES=[...]`.
- Print PASS/FAIL summary.
- Simulate cell/tap ADC, current ADC, and temperature ADC values inside the
  target firmware so validation and fault reactions can be exercised without a
  second tester MCU.
- Show `DIAG_MODE` in the GUI while firmware-side ADC injection is enabled.
- Show `DIAG_MODE` on the ESP32 OLED while firmware-side ADC injection is
  enabled.
- Save/load PC tester profiles for strict and known-fault test cases.
- Generate JSON logs and PDF reports for automated PC tester runs.
- Show a PC tester run-history/trend table from generated reports.
- Use fault-code exclusions in the PC CLI and MicroPython tester scaffold.

Next tester work:

- Run the PC UART tester against the BMS COM port.
- Confirm command/response timing without the dashboard connected.
- Use the browser GUI as the preferred manual tester surface.
- Review real bench PDF reports and add any missing fields needed for evidence.
- Port the richer report/history model to embedded tester storage later if the
  hardware tester needs standalone evidence.
- Port the tester logic to ESP32 or another MCU later.
- Add external hardware stimulus later with DACs, digital pots, relays, or a
  dedicated tester MCU. The current ADC stimulus is firmware-side injection,
  not physical pin driving.
