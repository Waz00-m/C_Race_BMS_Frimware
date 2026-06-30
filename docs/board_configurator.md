# Board Profile Configurator

Stage 10 adds a Python/Tkinter configurator for builder-owned board profiles.

Run it from the firmware folder:

```powershell
py bms_board_configurator.py
```

The configurator creates:

```text
bms_boards/generated/<profile_folder>/bms_board_common.h
bms_boards/generated/<profile_folder>/bms_board_profile.h
platformio.user.ini
```

`platformio.user.ini` is intentionally ignored by Git because it contains local
builder choices such as upload port and environment name.

Generated board profile files may be committed if they describe a board that
should be shared with another builder.

## Builder Workflow

1. Enter a profile folder and board name.
2. Enter voltage divider ratios directly, or enter measured tap mV and ADC mV
   and press `Calculate ratios from Tap/ADC`.
3. Enter current sensor values.
4. Enter NTC values.
5. Enter ESP32 ADC and OLED pins.
6. Press `Generate Profile`.
7. Press `Build`.
8. Press `Upload`.

The GUI runs PlatformIO with the generated config:

```powershell
pio run -c platformio.user.ini -e <generated_env>
pio run -c platformio.user.ini -e <generated_env> -t upload
```

## External Profile Include

The firmware supports generated board profiles through:

```ini
-D BMS_BOARD_CONFIG_FILE=\"generated/<profile_folder>/bms_board_profile.h\"
```

`bms_boards/bms_board_config.h` includes that file directly when the macro is
provided. This lets users create profiles without editing the library selector.

## Current Limitation

The GUI can generate an INA226 placeholder profile, but the INA226 firmware
backend is not implemented yet. That generated profile is intentionally guarded
so it fails safely at build time until the backend exists.
