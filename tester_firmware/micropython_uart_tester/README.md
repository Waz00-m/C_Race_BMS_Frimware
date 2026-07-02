# MicroPython UART Tester

This is the Stage 16 tester firmware foundation. It is intentionally separate
from the target BMS firmware.

The first tester does not inject analog signals yet. It proves the UART test
loop:

```text
send diagnostic command
read RESP line
parse fields
compare expected validity state
print PASS/FAIL
```

## Strict Baseline

The default config expects a fully valid Prototype-0 profile0 diagnostic state:

```text
Cell valid    = 0x0000003F
Tap valid     = 0x0000003F
Current valid = 1
Temp valid    = 0x0000000F
```

Known-fault exclusions are off by default. If exclusions are off, any active
firmware fault code is reported as a failed test.

## Known-Fault Exclusion Mode

The tester shell has a software toggle and fault-code values for known faults:

```text
known
known on
known off
known clear
known code <fault_code>[,<fault_code>...]
known add <fault_code>[,<fault_code>...]
```

For the current bench case where T1 is intentionally faulty:

```text
known code 0x3003
known on
run
```

To return to strict mode:

```text
known off
run
```

## Wiring

Use one MicroPython-capable tester MCU and the BMS target diagnostic UART.

```text
tester TX -> BMS RX
tester RX -> BMS TX
tester GND -> BMS GND
```

Default tester pins are in `tester_config.py`:

```text
UART_ID = 2
UART_TX_PIN = 17
UART_RX_PIN = 16
UART_BAUD = 115200
```

The BMS target currently uses its diagnostic UART at 115200 baud. Avoid running
the dashboard and tester against the same BMS UART at the same time.

## Copy To MicroPython Board

With `mpremote`, from this folder:

```powershell
mpremote connect COMx fs cp tester_config.py :tester_config.py
mpremote connect COMx fs cp bms_uart_tester.py :bms_uart_tester.py
mpremote connect COMx fs cp main.py :main.py
mpremote connect COMx reset
```

You can also copy the three `.py` files using Thonny.

## Console Commands

After boot, the tester runs the suite once and then opens a small shell:

```text
run
known
known code 0x3003
known on
known off
GET,TAPS
GET,VOLT
GET,CURRENT
GET,TEMP
GET,FAULT
```

## First PASS/FAIL Coverage

- `GET,TAPS`: tap/cell valid bitmaps and voltage reason.
- `GET,VOLT`: voltage valid mirrors.
- `GET,CURRENT`: INA240 current validity.
- `GET,TEMP`: strict temperature validity, with known fault-code exclusions
  reported as `EXCLUDED` when explicitly enabled.
- `GET,FAULT`: validity mirrors exposed by fault response.

Future tester stages can add report logging, scripted test cases, current
injection, voltage simulation, and NTC open/short fixtures.

## Tester Board Options

MicroPython requires a MicroPython-capable board. From the boards currently on
hand:

- ESP8266 can run MicroPython, but UART use is awkward because the main UART is
  also commonly used for the USB REPL.
- Arduino Uno and Arduino Mega do not run MicroPython in the usual workflow.
  They can be used as tester hardware with separate Arduino/C++ tester
  firmware instead.
- Arduino Mega is the best Arduino option because it has extra hardware UARTs.
  Uno can work only with `SoftwareSerial` or a USB/serial bridge and is less
  reliable for this role.

You do not need another ESP32 specifically. If you want to keep using this
MicroPython tester, use the ESP8266. If you want the most robust tester from the
boards on hand, use the Arduino Mega with a separate Arduino/C++ tester sketch.
For quick manual checks, the PC can still send the same UART commands over USB.
