# Board Profile Configurator

Stage 10 added a Python/Tkinter configurator for builder-owned board profiles.
Stage 12.5 adds the first drag/drop component workflow and generated-profile
cleanup controls.

Run it from the firmware folder:

```powershell
py bms_board_configurator.py
```

The configurator creates:

```text
bms_boards/generated/<profile_folder>/bms_board_common.h
bms_boards/generated/<profile_folder>/bms_board_profile.h
bms_boards/generated/<profile_folder>/bms_profile_manifest.json
platformio.user.ini
```

`platformio.user.ini` is intentionally ignored by Git because it contains local
builder choices such as upload port and environment name.

Generated board profile files may be committed if they describe a board that
should be shared with another builder.

## Builder Workflow

1. Enter a profile folder and board name.
2. Open the `Builder` tab.
3. Drag hardware blocks from the palette onto the board canvas.
4. Select a dropped block and press `Configure Selected` to jump to the matching
   detail tab.
5. Enter voltage divider ratios directly, or enter measured tap mV and ADC mV
   and press `Calculate ratios from Tap/ADC`.
6. Enter current sensor values.
   Supported current sensor choices now include analog INA240, analog ACS772,
   and digital INA226.
7. Enter NTC values.
8. Enter ESP32 ADC, I2C, and OLED pins.
9. Press `Generate Profile`.
10. Press `Build`.
11. Press `Upload`.

The voltage divider is now represented explicitly as the `6S Divider Taps`
voltage-sense block. Future voltage front ends, such as an AFE, should be added
as additional voltage blocks instead of hiding them inside generic voltage
settings.

## Placeholder Blocks

Some blocks are present as planning placeholders. They can be dragged onto the
board canvas to describe a future design, but they intentionally stop
generation until the matching platform or sensor backend exists.

Current placeholder blocks:

- `NXP S32K`
- `STM32H Series`
- `STM32F Series`
- `TI MCU`
- `LTC6811`
- `BQ76952`
- `PTC Sensor`

Example future NXP flow:

1. Drag `NXP S32K` into the MCU slot.
2. Drag `LTC6811` or `BQ76952` into the voltage-sense slot.
3. Drag a current-sensor block.
4. Drag `PTC Sensor` or another temperature block.
5. Implement the required platform HAL and sensor backend.
6. Turn the placeholder block into an implemented block.
7. Generate/build the profile.

This keeps the configurator honest: it can sketch tomorrow's board today, but it
will not silently generate fake ESP32 firmware for an unsupported MCU or AFE.

The GUI runs PlatformIO with the generated config:

```powershell
pio run -c platformio.user.ini -e <generated_env>
pio run -c platformio.user.ini -e <generated_env> -t upload
```

## Cleaning Profiles

From inside `Drone_BMS_Firmware`, clean a built-in profile build with:

```powershell
pio run -e esp32dev -t clean
pio run -e esp32dev_profile1 -t clean
```

From the parent folder, add `-d Drone_BMS_Firmware`:

```powershell
pio run -d Drone_BMS_Firmware -e esp32dev_profile1 -t clean
```

For a generated profile, use the generated user config:

```powershell
pio run -c platformio.user.ini -e <generated_env> -t clean
```

The configurator's `Generated Profiles` panel can also:

- refresh the generated profile list
- delete selected generated profile files
- remove the selected profile's `.pio/build/<env>` cache

Deleting generated profile files removes only files under
`bms_boards/generated/<profile_folder>/`. It does not edit the BMS core.

## External Profile Include

The firmware supports generated board profiles through:

```ini
-D BMS_BOARD_CONFIG_FILE=\"generated/<profile_folder>/bms_board_profile.h\"
```

`bms_boards/bms_board_config.h` includes that file directly when the macro is
provided. This lets users create profiles without editing the library selector.

## INA226 Notes

The GUI can generate an INA226 profile. The generated profile selects:

```cpp
BMS_CURRENT_SENSOR_INA226
```

and writes INA226 address, shunt, expected current range, and config-register
values. INA226 current is read through the firmware I2C HAL, not through the
ESP32 ADC current pin.

If the chip is not present or the I2C wiring is wrong, the firmware should
continue running and report invalid current so the normal current-sensor fault
path can catch it.
