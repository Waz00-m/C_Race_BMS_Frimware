# Tester Firmware

Stage 16 starts with a PC UART tester first, because the PC is available as the
immediate diagnostic host. The embedded tester path remains separate for later
porting to ESP32 or another MCU.

Immediate tester:

```text
tester_firmware/pc_uart_tester/
```

Future embedded tester scaffold:

```text
tester_firmware/micropython_uart_tester/
```

It is intentionally not part of the target BMS PlatformIO firmware. The target
firmware remains in:

```text
app/
bms_core/
bms_hal/
bms_platform/
bms_boards/
```

## First Tester Scope

The first tester is a PC UART PASS/FAIL harness. It sends existing diagnostic
commands and validates the response fields that Stage 15 made trustworthy:

```text
GET,INJECT
GET,TAPS
GET,VOLT
GET,CURRENT
GET,TEMP
GET,FAULT
```

The strict baseline expectation is:

```text
Cell valid    = 0x0000003F
Tap valid     = 0x0000003F
Current valid = 1
Temp valid    = 0x0000000F
```

Known faults are not treated as expected behavior by default. The browser tester
has an explicit exclusion toggle and a fault-code field:

```text
Known fault codes: 0x3003, 0x2003
```

With exclusions off, the same active fault is reported as a failure.

Known-fault exclusions only change tester expectations. They do not hide or
modify firmware faults.

The GUI info button in the known-fault section opens the local fault-code table.
`GET,FAULT` also reports `CODES=[...]` so non-primary active faults can be
matched by code.

## PC Tester Usage

Install the serial dependency:

```powershell
python -m pip install pyserial
```

If Windows opens the Microsoft Store instead of Python, use the real Python
interpreter path or disable the Windows app execution alias.

List ports:

```powershell
python tester_firmware\pc_uart_tester\pc_bms_uart_tester.py --list-ports
```

Run strict mode on the BMS diagnostic port:

```powershell
python tester_firmware\pc_uart_tester\pc_bms_uart_tester.py --port COM3
```

Run once and exit:

```powershell
python tester_firmware\pc_uart_tester\pc_bms_uart_tester.py --port COM3 --once
```

The dashboard must be disconnected first because only one PC program can own
the COM port at a time.

## Browser GUI

The PC tester also has a browser GUI:

```powershell
python tester_firmware\pc_uart_tester\pc_bms_tester_gui.py
```

It serves a local page at:

```text
http://127.0.0.1:8765/
```

The GUI is the preferred manual tester surface. It provides COM-port control,
an automated test button, raw command buttons, expected-value sliders,
known-fault exclusion controls, response meters for the latest diagnostic
responses, ADC injection stimulus controls, saved test profiles, and automatic
JSON/PDF test reports. It also shows a run-history table for the latest
generated reports.

The timeout field beside baud rate is the command response timeout in seconds.
The default `1.8` means the tester waits up to 1.8 seconds for the expected
`RESP,...` line after sending a command.

## Firmware ADC Injection Stimulus

The PC GUI can now drive a volatile firmware diagnostic injection mode. This is
not external hardware stimulus. It overrides acquisition-layer ADC millivolts
inside the BMS firmware so conversion, validation, fault supervision, and
diagnostic reporting react as if the ADC pins had changed.

Diagnostic commands:

```text
GET,INJECT
DIAG,ADC,SET,CELL,1,2600
DIAG,ADC,SET,CURRENT,2129
DIAG,ADC,SET,TEMP,1,1400
DIAG,ADC,ON
DIAG,ADC,OFF
DIAG,ADC,CLEAR,ALL
```

The controllable voltage stimulus is ADC mV, not final cell mV. The GUI's
"all cells target" helper estimates ADC slider values from the latest
`GET,TAPS` tap/ADC ratio, then the firmware still does the real conversion.

Current stimulus uses the current ADC mV path. On Prototype-0 profile0 this
exercises the analog INA240 conversion path. INA226 profile hardware is digital
and should be validated separately when available.

When injection is enabled, injected ADC channels are excluded from stuck-ADC
detection so a deliberate constant simulated value does not immediately become
a stuck-sensor fault.

While injection is enabled, the target reports `DIAGNOSTIC_MODE` and the GUI
shows a small `DIAG_MODE` badge in the bottom-right corner. `Clear Injection`
turns injection off, clears injected ADC values, and the badge returns to
normal. The ESP32 OLED display also overlays `DIAG_MODE` at the bottom-right
corner while diagnostic injection is active.

## Saved Profiles And Reports

Saved browser test profiles store:

- expected masks and reason fields
- known fault-code exclusions
- ADC stimulus slider settings

Default profiles include strict all-valid, known T1 temperature sensor, and
known current sensor cases. User profiles are written to:

```text
tester_firmware/pc_uart_tester/test_profiles.json
```

Each automated test writes a machine-readable JSON log and a human-readable PDF
report:

```text
tester_firmware/pc_uart_tester/reports/
```

The GUI shows the latest PDF link after `Run Automated Test`. The PDF is a
tabulated `C-RACE LABS` report with summary cards, run metadata, expected
baselines, known fault-code exclusions, automated check results, raw diagnostic
responses, and a fault-code reference table.

The GUI run-history table reads the latest JSON reports from the report folder
and links to the matching PDFs. It is a quick trend view for repeated bench
runs: result, timestamp, profile, pass/fail counts, port, and report link.

The PC CLI and MicroPython tester scaffold use the same fault-code exclusion
model:

```text
known code 0x3003,0x2003
known on
run
```

The PC CLI can also start with known codes:

```powershell
python tester_firmware\pc_uart_tester\pc_bms_uart_tester.py --port COM3 --once --known-on --known-fault-codes 0x3003,0x2003
```

The BMS diagnostic service is scheduler-polled and command-driven. `GET,...`
commands return register snapshots; `CFG,...` commands can change runtime
configuration, and `CFG,SAVE` writes NVM. Keep automated tester traffic focused
on read-only commands unless a config test is intentional.

## Why MicroPython

MicroPython remains acceptable for a later embedded tester stage because the
first embedded goal is quick diagnostic orchestration, not hard real-time signal
generation. It is useful for:

- sending UART commands
- parsing `RESP,...` lines
- checking masks and flags
- printing PASS/FAIL summaries
- iterating test scripts quickly

Hardware signal injection can still be added later through DACs, digital pots,
relays, or a more timing-controlled tester firmware if needed.

## Available Board Choices

The current MicroPython tester scaffold needs a MicroPython-capable MCU. An
ESP8266 can run it, but the UART arrangement is constrained because the primary
UART is often also the console/REPL UART.

Arduino Uno and Mega do not run this MicroPython tester directly. They remain
valid tester hardware candidates with a separate Arduino/C++ tester firmware.
Mega is preferred over Uno because it has multiple hardware UARTs.

You do not specifically need another ESP32. The choices from the currently
available boards are:

| Board | Can run this MicroPython tester? | Tester suitability |
|---|---|---|
| ESP8266 | Yes, with UART caveats | Good for MicroPython proof, but REPL/UART sharing can be awkward. |
| Arduino Mega | No | Best available UART tester if using Arduino/C++ firmware because it has multiple hardware UARTs. |
| Arduino Uno | No | Possible with `SoftwareSerial`, but least reliable for a tester bridge. |

For current validation, the PC is the selected tester. For standalone tester
firmware later, use a second MCU.

## Boundary Rule

Tester firmware must not be mixed into the target firmware. It may live in the
same repository for coordination, but it must remain in a separate top-level
folder and communicate through the target's public diagnostic interface.
