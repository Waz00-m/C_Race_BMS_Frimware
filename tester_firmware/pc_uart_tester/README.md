# PC UART Tester

This is the immediate Stage 16 tester path. It runs on the PC and talks to the
BMS target over the same diagnostic serial port used by the dashboard.

Use this when you do not have a second tester MCU connected yet. The logic can
later be ported to ESP32 firmware.

## Browser GUI

Close the dashboard first so the tester can own the COM port.

```powershell
C:\Users\acer\AppData\Local\Python\bin\python.exe tester_firmware\pc_uart_tester\pc_bms_tester_gui.py
```

Then open:

```text
http://127.0.0.1:8765/
```

The GUI provides:

- COM port connect/disconnect.
- Baud and command timeout fields. The default `1.8` beside the baud field is
  the serial response timeout in seconds.
- Automated test button.
- Manual diagnostic command buttons.
- Saved test profiles.
- Expected-value sliders for validity masks.
- Known-fault exclusion toggle and fault-code field with a fault-table info
  button.
- ADC injection stimulus controls for cell tap ADC, current ADC, and temp ADC.
- Response meters for cells, taps, ADC, temperature, current, current ADC, and
  fault state.
- Automatic JSON log and PDF report generation after each automated test.

## Install Dependency

```powershell
python -m pip install pyserial
```

If Windows opens the Microsoft Store instead of Python, use your real Python
path or disable the Windows app execution alias. On this machine, one working
interpreter path is:

```powershell
C:\Users\acer\AppData\Local\Python\bin\python.exe
```

## List Ports

```powershell
python tester_firmware\pc_uart_tester\pc_bms_uart_tester.py --list-ports
```

## Strict CLI Test

Close the dashboard first so the tester can own the COM port.

```powershell
python tester_firmware\pc_uart_tester\pc_bms_uart_tester.py --port COM3
```

The tester runs once, then opens a shell:

```text
tester> run
tester> GET,TAPS
tester> GET,VOLT
tester> GET,CURRENT
tester> GET,TEMP
tester> GET,FAULT
tester> known code 0x3003,0x2003
tester> known on
tester> quit
```

## Known-Fault Exclusions

Known faults are off by default. With exclusions off, any active firmware fault
code fails the browser automated test.

In the GUI, turn on known-fault exclusions and enter fault codes such as:

```text
0x3003, 0x2003
```

The info button opens the local fault-code table. The tester uses
`GET,FAULT` `CODES=[...]`, so a known fault can be excluded even when it is not
the primary fault.

You can also run once from the command line:

```powershell
python tester_firmware\pc_uart_tester\pc_bms_uart_tester.py --port COM3 --once
```

Known fault codes from the command line:

```powershell
python tester_firmware\pc_uart_tester\pc_bms_uart_tester.py --port COM3 --once --known-on --known-fault-codes 0x3003,0x2003
```

Known-fault exclusions only change expected PASS/FAIL values. They do not
change firmware behavior or hide faults in raw responses.

## ADC Injection Stimulus

The GUI can drive the firmware's volatile diagnostic ADC injection mode. This
lets the PC tester simulate ADC millivolts without another MCU:

```text
GET,INJECT
DIAG,ADC,SET,CELL,1,2600
DIAG,ADC,SET,CURRENT,2129
DIAG,ADC,SET,TEMP,1,1400
DIAG,ADC,ON
DIAG,ADC,OFF
DIAG,ADC,CLEAR,ALL
```

Cell stimulus is still controlled through ADC mV. The GUI helper can estimate
ADC values for a target per-cell voltage from the latest `GET,TAPS` response,
but firmware conversion and validation remain the source of truth.

Use `Clear Injection` before returning to real hardware readings.

While injection is enabled, the target firmware reports diagnostic mode and the
GUI shows a `DIAG_MODE` badge at the bottom-right corner. `Clear Injection`
turns injection off and hides the badge. The OLED also shows `DIAG_MODE` in its
bottom-right corner while the target is in diagnostic injection mode.

## Test Profiles And Reports

The browser GUI can save and load test profiles. A profile stores:

- expected validity masks and reason fields
- known fault-code exclusions
- the current ADC injection slider setup

Built-in profiles are available for strict all-valid testing, known T1
temperature-sensor fault, and known current-sensor fault. User-saved profiles
are stored in:

```text
tester_firmware/pc_uart_tester/test_profiles.json
```

Every automated test writes:

```text
tester_firmware/pc_uart_tester/reports/*.json
tester_firmware/pc_uart_tester/reports/*.pdf
```

The PDF link appears in the GUI after the test completes. The PDF report is
tabulated and branded with a `C-RACE LABS` header. It includes summary cards,
run metadata, expected baselines, known fault-code exclusions, automated check
results, raw diagnostic responses, and a fault-code reference table. Reports
are ignored by git because they are generated bench evidence.

## Strict Baseline

```text
Cell valid    = 0x0000003F
Tap valid     = 0x0000003F
Current valid = 1
Temp valid    = 0x0000000F
```
