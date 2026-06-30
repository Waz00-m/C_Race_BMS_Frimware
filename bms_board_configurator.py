"""
Board profile configurator for the Drone BMS firmware.

This tool generates user-owned board profile files and a PlatformIO user config
without modifying the portable BMS core.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import threading
from pathlib import Path
from tkinter import messagebox, ttk
import tkinter as tk


FIRMWARE_DIR = Path(__file__).resolve().parent
GENERATED_DIR = FIRMWARE_DIR / "bms_boards" / "generated"
USER_INI = FIRMWARE_DIR / "platformio.user.ini"

BMS_NUM_CELLS = 6
BMS_NUM_TEMPERATURES = 4

DEFAULT_RATIOS = [1132427, 2625637, 3959707, 5293902, 7340122, 7705690]
DEFAULT_CELL_PINS = [36, 39, 34, 35, 32, 33]
DEFAULT_TEMP_PINS = [26, 27, 14, 13]


def sanitize_identifier(value: str, fallback: str) -> str:
    text = value.strip().lower()
    text = re.sub(r"[^a-z0-9_]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    if not text:
        text = fallback
    if text[0].isdigit():
        text = f"bms_{text}"
    return text


def macro_name(value: str) -> str:
    return sanitize_identifier(value, "custom_board").upper()


def parse_int(value: str, default: int = 0) -> int:
    try:
        return int(str(value).strip(), 0)
    except (TypeError, ValueError):
        return default


def parse_float(value: str, default: float = 0.0) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def c_float(value: float) -> str:
    return f"{value:.6g}f"


class BoardConfigurator:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("BMS Board Profile Configurator")
        self.root.geometry("1120x780")

        self.vars: dict[str, tk.StringVar] = {}
        self.bool_vars: dict[str, tk.BooleanVar] = {}
        self.ratio_vars: list[tk.StringVar] = []
        self.gain_vars: list[tk.StringVar] = []
        self.offset_vars: list[tk.StringVar] = []
        self.tap_vars: list[tk.StringVar] = []
        self.adc_vars: list[tk.StringVar] = []
        self.cell_pin_vars: list[tk.StringVar] = []
        self.temp_pin_vars: list[tk.StringVar] = []

        self._init_vars()
        self._build_ui()

    def _init_vars(self) -> None:
        defaults = {
            "profile_slug": "my_6s_esp32_profile0",
            "board_name": "MY_6S_ESP32_PROFILE0",
            "env_name": "my_6s_esp32",
            "platformio_board": "esp32dev",
            "upload_port": "COM3",
            "voltage_mode": "cumulative_taps",
            "current_sensor": "analog_ina240",
            "current_zero_mv": "1650.0",
            "current_shunt_ohm": "0.00025",
            "current_ina_gain": "38.30",
            "current_adc_high_mv": "3200",
            "current_adc_gain": "1.0",
            "current_adc_offset_mv": "0.0",
            "current_reading_gain": "1.0",
            "current_smooth_alpha": "0.060",
            "current_noload_enter_ma": "2000",
            "current_noload_exit_ma": "1300",
            "current_offset_ma": "0.0",
            "ina226_address": "0x40",
            "ina226_shunt_ohm": "0.00025",
            "ina226_max_current_ma": "120000",
            "ntc_supply_mv": "3300.0",
            "ntc_fixed_ohm": "10000.0",
            "ntc_nominal_ohm": "10000.0",
            "ntc_beta": "3435.0",
            "ntc_nominal_temp_k": "298.15",
            "ntc_min_ohm": "500.0",
            "ntc_max_ohm": "200000.0",
            "temp_min_c": "-20.0",
            "temp_max_c": "100.0",
            "current_pin": "25",
            "oled_sda": "21",
            "oled_scl": "22",
            "oled_button": "18",
            "oled_width": "128",
            "oled_height": "64",
            "oled_reset": "-1",
            "oled_address": "0x3C",
            "oled_cell_max_mv": "4150",
            "oled_cell_min_mv": "0",
            "oled_debounce_ms": "50",
            "oled_noload_ma": "2000",
        }

        for key, value in defaults.items():
            self.vars[key] = tk.StringVar(value=value)

        self.bool_vars["ntc_to_ground"] = tk.BooleanVar(value=True)

        for i in range(BMS_NUM_CELLS):
            self.ratio_vars.append(tk.StringVar(value=str(DEFAULT_RATIOS[i])))
            self.gain_vars.append(tk.StringVar(value="1000000"))
            self.offset_vars.append(tk.StringVar(value="0"))
            self.tap_vars.append(tk.StringVar(value=""))
            self.adc_vars.append(tk.StringVar(value=""))
            self.cell_pin_vars.append(tk.StringVar(value=str(DEFAULT_CELL_PINS[i])))

        for i in range(BMS_NUM_TEMPERATURES):
            self.temp_pin_vars.append(tk.StringVar(value=str(DEFAULT_TEMP_PINS[i])))

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill="both", expand=True)

        notebook = ttk.Notebook(main)
        notebook.pack(fill="both", expand=True)

        self._build_board_tab(notebook)
        self._build_voltage_tab(notebook)
        self._build_current_tab(notebook)
        self._build_temperature_tab(notebook)
        self._build_pins_tab(notebook)
        self._build_generate_tab(notebook)

    def _entry(self, parent: ttk.Frame, row: int, label: str, key: str,
               width: int = 18, column: int = 0) -> ttk.Entry:
        ttk.Label(parent, text=label).grid(
            row=row,
            column=column,
            sticky="e",
            padx=4,
            pady=3,
        )
        entry = ttk.Entry(parent, textvariable=self.vars[key], width=width)
        entry.grid(row=row, column=column + 1, sticky="w", padx=4, pady=3)
        return entry

    def _build_board_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=12)
        notebook.add(frame, text="Board")

        self._entry(frame, 0, "Profile folder", "profile_slug", width=32)
        self._entry(frame, 1, "Board name", "board_name", width=32)
        self._entry(frame, 2, "PlatformIO env", "env_name", width=32)
        self._entry(frame, 3, "PIO board", "platformio_board", width=32)
        self._entry(frame, 4, "Upload port", "upload_port", width=32)

        ttk.Label(frame, text="Current sensor").grid(
            row=5,
            column=0,
            sticky="e",
            padx=4,
            pady=3,
        )
        sensor = ttk.Combobox(
            frame,
            textvariable=self.vars["current_sensor"],
            values=["analog_ina240", "ina226_placeholder"],
            state="readonly",
            width=29,
        )
        sensor.grid(row=5, column=1, sticky="w", padx=4, pady=3)

        ttk.Label(
            frame,
            text=(
                "Generated files go under bms_boards/generated/<profile folder>. "
                "The firmware core is not edited."
            ),
            wraplength=720,
        ).grid(row=6, column=0, columnspan=4, sticky="w", pady=(18, 3))

    def _build_voltage_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=12)
        notebook.add(frame, text="Voltage")

        ttk.Label(frame, text="Voltage mode").grid(
            row=0,
            column=0,
            sticky="e",
            padx=4,
            pady=3,
        )
        mode = ttk.Combobox(
            frame,
            textvariable=self.vars["voltage_mode"],
            values=["cumulative_taps", "direct_cell"],
            state="readonly",
            width=20,
        )
        mode.grid(row=0, column=1, sticky="w", padx=4, pady=3)

        headers = ["Cell", "Tap mV", "ADC mV", "Ratio ppm", "Gain ppm", "Offset mV"]
        for column, header in enumerate(headers):
            ttk.Label(frame, text=header).grid(
                row=2,
                column=column,
                sticky="w",
                padx=4,
                pady=(12, 4),
            )

        for i in range(BMS_NUM_CELLS):
            ttk.Label(frame, text=f"C{i + 1}").grid(
                row=i + 3,
                column=0,
                sticky="w",
                padx=4,
                pady=2,
            )
            ttk.Entry(frame, textvariable=self.tap_vars[i], width=12).grid(
                row=i + 3,
                column=1,
                padx=4,
                pady=2,
            )
            ttk.Entry(frame, textvariable=self.adc_vars[i], width=12).grid(
                row=i + 3,
                column=2,
                padx=4,
                pady=2,
            )
            ttk.Entry(frame, textvariable=self.ratio_vars[i], width=14).grid(
                row=i + 3,
                column=3,
                padx=4,
                pady=2,
            )
            ttk.Entry(frame, textvariable=self.gain_vars[i], width=12).grid(
                row=i + 3,
                column=4,
                padx=4,
                pady=2,
            )
            ttk.Entry(frame, textvariable=self.offset_vars[i], width=12).grid(
                row=i + 3,
                column=5,
                padx=4,
                pady=2,
            )

        ttk.Button(
            frame,
            text="Calculate ratios from Tap/ADC",
            command=self._calculate_voltage_ratios,
        ).grid(row=10, column=0, columnspan=3, sticky="w", padx=4, pady=14)

    def _build_current_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=12)
        notebook.add(frame, text="Current")

        self._entry(frame, 0, "Zero mV", "current_zero_mv")
        self._entry(frame, 1, "Shunt ohm", "current_shunt_ohm")
        self._entry(frame, 2, "INA gain", "current_ina_gain")
        self._entry(frame, 3, "ADC high valid mV", "current_adc_high_mv")
        self._entry(frame, 4, "ADC gain correction", "current_adc_gain")
        self._entry(frame, 5, "ADC offset mV", "current_adc_offset_mv")
        self._entry(frame, 6, "Reading gain", "current_reading_gain")
        self._entry(frame, 7, "Offset mA", "current_offset_ma")
        self._entry(frame, 8, "Smooth alpha", "current_smooth_alpha")
        self._entry(frame, 9, "No-load enter mA", "current_noload_enter_ma")
        self._entry(frame, 10, "No-load exit mA", "current_noload_exit_ma")

        self._entry(frame, 0, "INA226 address", "ina226_address", column=3)
        self._entry(frame, 1, "INA226 shunt ohm", "ina226_shunt_ohm", column=3)
        self._entry(
            frame,
            2,
            "INA226 max current mA",
            "ina226_max_current_ma",
            column=3,
        )

        ttk.Label(
            frame,
            text="INA226 is generated as a placeholder until the firmware backend exists.",
            wraplength=430,
        ).grid(row=4, column=3, columnspan=2, sticky="w", padx=4, pady=12)

    def _build_temperature_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=12)
        notebook.add(frame, text="Temperature")

        ttk.Checkbutton(
            frame,
            text="NTC to ground",
            variable=self.bool_vars["ntc_to_ground"],
        ).grid(row=0, column=1, sticky="w", padx=4, pady=3)

        self._entry(frame, 1, "NTC supply mV", "ntc_supply_mv")
        self._entry(frame, 2, "Fixed resistor ohm", "ntc_fixed_ohm")
        self._entry(frame, 3, "Nominal NTC ohm", "ntc_nominal_ohm")
        self._entry(frame, 4, "NTC beta", "ntc_beta")
        self._entry(frame, 5, "Nominal temp K", "ntc_nominal_temp_k")
        self._entry(frame, 6, "Min valid ohm", "ntc_min_ohm")
        self._entry(frame, 7, "Max valid ohm", "ntc_max_ohm")
        self._entry(frame, 8, "Min valid C", "temp_min_c")
        self._entry(frame, 9, "Max valid C", "temp_max_c")

    def _build_pins_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=12)
        notebook.add(frame, text="Pins/OLED")

        ttk.Label(frame, text="Cell ADC pins").grid(
            row=0,
            column=0,
            sticky="w",
            padx=4,
            pady=(0, 6),
        )
        for i in range(BMS_NUM_CELLS):
            ttk.Label(frame, text=f"C{i + 1}").grid(
                row=i + 1,
                column=0,
                sticky="e",
                padx=4,
                pady=2,
            )
            ttk.Entry(frame, textvariable=self.cell_pin_vars[i], width=8).grid(
                row=i + 1,
                column=1,
                sticky="w",
                padx=4,
                pady=2,
            )

        self._entry(frame, 8, "Current ADC pin", "current_pin", width=8)

        ttk.Label(frame, text="Temperature ADC pins").grid(
            row=0,
            column=3,
            sticky="w",
            padx=18,
            pady=(0, 6),
        )
        for i in range(BMS_NUM_TEMPERATURES):
            ttk.Label(frame, text=f"T{i + 1}").grid(
                row=i + 1,
                column=3,
                sticky="e",
                padx=4,
                pady=2,
            )
            ttk.Entry(frame, textvariable=self.temp_pin_vars[i], width=8).grid(
                row=i + 1,
                column=4,
                sticky="w",
                padx=4,
                pady=2,
            )

        oled_fields = [
            ("SDA", "oled_sda"),
            ("SCL", "oled_scl"),
            ("Button", "oled_button"),
            ("Width", "oled_width"),
            ("Height", "oled_height"),
            ("Reset", "oled_reset"),
            ("I2C address", "oled_address"),
            ("Cell max mV", "oled_cell_max_mv"),
            ("Cell min mV", "oled_cell_min_mv"),
            ("Debounce ms", "oled_debounce_ms"),
            ("No-load mA", "oled_noload_ma"),
        ]
        for row, (label, key) in enumerate(oled_fields):
            self._entry(frame, row, f"OLED {label}", key, width=12, column=6)

    def _build_generate_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=12)
        notebook.add(frame, text="Generate/Build")

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Generate Profile", command=self._generate_files).pack(
            side="left",
            padx=4,
        )
        ttk.Button(buttons, text="Build", command=self._build).pack(
            side="left",
            padx=4,
        )
        ttk.Button(buttons, text="Upload", command=self._upload).pack(
            side="left",
            padx=4,
        )
        ttk.Button(buttons, text="Clean", command=self._clean).pack(
            side="left",
            padx=4,
        )

        self.output = tk.Text(frame, height=28, wrap="none")
        self.output.pack(fill="both", expand=True, pady=(12, 0))
        self._log("Ready. Generate a board profile, then Build or Upload.")

    def _calculate_voltage_ratios(self) -> None:
        changed = 0
        for i in range(BMS_NUM_CELLS):
            tap_mV = parse_float(self.tap_vars[i].get(), 0.0)
            adc_mV = parse_float(self.adc_vars[i].get(), 0.0)
            if tap_mV > 0.0 and adc_mV > 0.0:
                ratio_ppm = int(round((tap_mV / adc_mV) * 1000000.0))
                self.ratio_vars[i].set(str(ratio_ppm))
                changed += 1

        self._log(f"Calculated {changed} voltage divider ratio(s).")

    def _profile_folder(self) -> str:
        return sanitize_identifier(self.vars["profile_slug"].get(), "custom_board")

    def _env_name(self) -> str:
        return sanitize_identifier(self.vars["env_name"].get(), self._profile_folder())

    def _board_name(self) -> str:
        text = self.vars["board_name"].get().strip()
        if not text:
            text = self._profile_folder().upper()
        return text

    def _voltage_mode_value(self) -> str:
        if self.vars["voltage_mode"].get() == "direct_cell":
            return "0U"
        return "1U"

    def _sensor_config_lines(self) -> list[str]:
        sensor = self.vars["current_sensor"].get()
        if sensor == "ina226_placeholder":
            return [
                "#define BMS_CURRENT_SENSOR_TYPE BMS_CURRENT_SENSOR_INA226",
                "#define BMS_BOARD_PROFILE_REQUIRES_INA226_BACKEND 1",
                f"#define BMS_INA226_I2C_ADDRESS ({self.vars['ina226_address'].get()}U)",
                f"#define BMS_INA226_SHUNT_OHM ({c_float(parse_float(self.vars['ina226_shunt_ohm'].get(), 0.00025))})",
                f"#define BMS_INA226_MAX_EXPECTED_CURRENT_MA ({parse_int(self.vars['ina226_max_current_ma'].get(), 120000)}L)",
            ]

        return ["#define BMS_CURRENT_SENSOR_TYPE BMS_CURRENT_SENSOR_ANALOG_INA240"]

    def _common_header_text(self, guard: str) -> str:
        ratios = [parse_int(v.get(), DEFAULT_RATIOS[i]) for i, v in enumerate(self.ratio_vars)]
        gains = [parse_int(v.get(), 1000000) for v in self.gain_vars]
        offsets = [parse_int(v.get(), 0) for v in self.offset_vars]
        cell_pins = [parse_int(v.get(), DEFAULT_CELL_PINS[i]) for i, v in enumerate(self.cell_pin_vars)]
        temp_pins = [parse_int(v.get(), DEFAULT_TEMP_PINS[i]) for i, v in enumerate(self.temp_pin_vars)]
        temp_min_dC = int(round(parse_float(self.vars["temp_min_c"].get(), -20.0) * 10.0))
        temp_max_dC = int(round(parse_float(self.vars["temp_max_c"].get(), 100.0) * 10.0))
        ntc_to_ground = "1" if self.bool_vars["ntc_to_ground"].get() else "0"

        return f"""#ifndef {guard}_COMMON_H
#define {guard}_COMMON_H

#include "bms_types.h"

#define BMS_BOARD_CELL_COUNT (6U)
#define BMS_BOARD_TEMPERATURE_COUNT (4U)

#define BMS_BOARD_VOLTAGE_INPUT_MODE ({self._voltage_mode_value()})

#define BMS_BOARD_HAS_VOLTAGE_CONFIG 1
static const uint32_t BMS_DEFAULT_VOLTAGE_DIVIDER_RATIO_PPM[BMS_NUM_CELLS] = {{
{self._format_ulong_array(ratios)}
}};

static const int32_t BMS_DEFAULT_VOLTAGE_GAIN_PPM[BMS_NUM_CELLS] = {{
{self._format_long_array(gains)}
}};

static const int32_t BMS_DEFAULT_VOLTAGE_OFFSET_MV[BMS_NUM_CELLS] = {{
{self._format_long_array(offsets)}
}};

#define BMS_ADC_LOW_VALID_MV (20U)
#define BMS_ADC_HIGH_VALID_MV (3250U)

#define BMS_CURRENT_ZERO_MV ({c_float(parse_float(self.vars["current_zero_mv"].get(), 1650.0))})
#define BMS_CURRENT_SHUNT_OHM ({c_float(parse_float(self.vars["current_shunt_ohm"].get(), 0.00025))})
#define BMS_CURRENT_INA_GAIN ({c_float(parse_float(self.vars["current_ina_gain"].get(), 38.30))})
#define BMS_CURRENT_ADC_HIGH_VALID_MV ({parse_int(self.vars["current_adc_high_mv"].get(), 3200)}U)
#define BMS_CURRENT_ADC_GAIN_CORRECTION ({c_float(parse_float(self.vars["current_adc_gain"].get(), 1.0))})
#define BMS_CURRENT_ADC_OFFSET_MV ({c_float(parse_float(self.vars["current_adc_offset_mv"].get(), 0.0))})
#define BMS_CURRENT_READING_GAIN ({c_float(parse_float(self.vars["current_reading_gain"].get(), 1.0))})
#define BMS_CURRENT_SMOOTH_ALPHA ({c_float(parse_float(self.vars["current_smooth_alpha"].get(), 0.060))})
#define BMS_CURRENT_NOLOAD_ENTER_MA ({parse_int(self.vars["current_noload_enter_ma"].get(), 2000)}L)
#define BMS_CURRENT_NOLOAD_EXIT_MA ({parse_int(self.vars["current_noload_exit_ma"].get(), 1300)}L)
#define BMS_CURRENT_OFFSET_MA ({c_float(parse_float(self.vars["current_offset_ma"].get(), 0.0))})

#define BMS_NTC_TO_GROUND {ntc_to_ground}
#define BMS_NTC_SUPPLY_MV ({c_float(parse_float(self.vars["ntc_supply_mv"].get(), 3300.0))})
#define BMS_NTC_FIXED_RESISTOR_OHM ({c_float(parse_float(self.vars["ntc_fixed_ohm"].get(), 10000.0))})
#define BMS_NTC_NOMINAL_RESISTANCE_OHM ({c_float(parse_float(self.vars["ntc_nominal_ohm"].get(), 10000.0))})
#define BMS_NTC_BETA ({c_float(parse_float(self.vars["ntc_beta"].get(), 3435.0))})
#define BMS_NTC_NOMINAL_TEMP_K ({c_float(parse_float(self.vars["ntc_nominal_temp_k"].get(), 298.15))})
#define BMS_NTC_MIN_VALID_OHM ({c_float(parse_float(self.vars["ntc_min_ohm"].get(), 500.0))})
#define BMS_NTC_MAX_VALID_OHM ({c_float(parse_float(self.vars["ntc_max_ohm"].get(), 200000.0))})
#define BMS_TEMP_SENSOR_MIN_VALID_DC ({temp_min_dC})
#define BMS_TEMP_SENSOR_MAX_VALID_DC ({temp_max_dC})

#define BMS_BOARD_HAS_NTC_ADC_CALIBRATION 1
static const int32_t BMS_NTC_ADC_GAIN_PPM[BMS_NUM_TEMPERATURES] = {{
    1000000L,
    1000000L,
    1000000L,
    1000000L,
}};

static const int16_t BMS_NTC_ADC_OFFSET_MV[BMS_NUM_TEMPERATURES] = {{
    0,
    0,
    0,
    0,
}};

#define BMS_ESP32_ADC_PIN_CELL_1 ({cell_pins[0]})
#define BMS_ESP32_ADC_PIN_CELL_2 ({cell_pins[1]})
#define BMS_ESP32_ADC_PIN_CELL_3 ({cell_pins[2]})
#define BMS_ESP32_ADC_PIN_CELL_4 ({cell_pins[3]})
#define BMS_ESP32_ADC_PIN_CELL_5 ({cell_pins[4]})
#define BMS_ESP32_ADC_PIN_CELL_6 ({cell_pins[5]})
#define BMS_ESP32_ADC_PIN_CURRENT ({parse_int(self.vars["current_pin"].get(), 25)})
#define BMS_ESP32_ADC_PIN_TEMP_1 ({temp_pins[0]})
#define BMS_ESP32_ADC_PIN_TEMP_2 ({temp_pins[1]})
#define BMS_ESP32_ADC_PIN_TEMP_3 ({temp_pins[2]})
#define BMS_ESP32_ADC_PIN_TEMP_4 ({temp_pins[3]})

#define BMS_OLED_SDA_PIN ({parse_int(self.vars["oled_sda"].get(), 21)})
#define BMS_OLED_SCL_PIN ({parse_int(self.vars["oled_scl"].get(), 22)})
#define BMS_OLED_PAGE_BUTTON_PIN ({parse_int(self.vars["oled_button"].get(), 18)})
#define BMS_OLED_SCREEN_WIDTH ({parse_int(self.vars["oled_width"].get(), 128)})
#define BMS_OLED_SCREEN_HEIGHT ({parse_int(self.vars["oled_height"].get(), 64)})
#define BMS_OLED_RESET_PIN ({parse_int(self.vars["oled_reset"].get(), -1)})
#define BMS_OLED_I2C_ADDRESS ({self.vars["oled_address"].get()})
#define BMS_OLED_CELL_DISPLAY_MAX_MV ({parse_int(self.vars["oled_cell_max_mv"].get(), 4150)}U)
#define BMS_OLED_CELL_DISPLAY_MIN_MV ({parse_int(self.vars["oled_cell_min_mv"].get(), 0)}U)
#define BMS_OLED_BUTTON_DEBOUNCE_MS ({parse_int(self.vars["oled_debounce_ms"].get(), 50)}UL)
#define BMS_OLED_CURRENT_NO_LOAD_THRESHOLD_MA ({parse_int(self.vars["oled_noload_ma"].get(), 2000)}UL)

#endif
"""

    @staticmethod
    def _format_ulong_array(values: list[int]) -> str:
        return "".join(f"    {value}UL,\n" for value in values).rstrip()

    @staticmethod
    def _format_long_array(values: list[int]) -> str:
        return "".join(f"    {value}L,\n" for value in values).rstrip()

    def _profile_header_text(self, guard: str) -> str:
        sensor_lines = "\n".join(self._sensor_config_lines())
        return f"""#ifndef {guard}_PROFILE_H
#define {guard}_PROFILE_H

#define BMS_BOARD_NAME "{self._board_name()}"
#define BMS_BOARD_PROFILE_ID (100U)
{sensor_lines}

#include "bms_board_common.h"

#endif
"""

    def _platformio_text(self, profile_include: str) -> str:
        env_name = self._env_name()
        board = sanitize_identifier(self.vars["platformio_board"].get(), "esp32dev")
        upload_port = self.vars["upload_port"].get().strip() or "COM3"
        return f"""[platformio]
src_dir = .

[env:{env_name}]
platform = espressif32
board = {board}
framework = arduino
upload_port = {upload_port}
monitor_speed = 115200
lib_deps =
    adafruit/Adafruit SSD1306 @ ^2.5.13
build_flags =
    -Iapp
    -Ibms_boards
    -Ibms_core
    -Ibms_hal
    -Ibms_platform/esp32
    -D BMS_BOARD_CONFIG_FILE=\\\"{profile_include}\\\"
build_src_filter =
    +<app/*.cpp>
    +<bms_core/*.cpp>
    +<bms_platform/esp32/*.cpp>
"""

    def _generate_files(self, quiet: bool = False) -> bool:
        profile_folder = self._profile_folder()
        target_dir = GENERATED_DIR / profile_folder
        target_dir.mkdir(parents=True, exist_ok=True)

        guard = f"BMS_GENERATED_{macro_name(profile_folder)}"
        common_file = target_dir / "bms_board_common.h"
        profile_file = target_dir / "bms_board_profile.h"
        profile_include = f"generated/{profile_folder}/bms_board_profile.h"

        common_file.write_text(self._common_header_text(guard), encoding="utf-8")
        profile_file.write_text(self._profile_header_text(guard), encoding="utf-8")
        USER_INI.write_text(self._platformio_text(profile_include), encoding="utf-8")

        self._log(f"Generated {common_file.relative_to(FIRMWARE_DIR)}")
        self._log(f"Generated {profile_file.relative_to(FIRMWARE_DIR)}")
        self._log(f"Generated {USER_INI.relative_to(FIRMWARE_DIR)}")

        if self.vars["current_sensor"].get() == "ina226_placeholder":
            self._log(
                "Warning: INA226 profile generated as a placeholder. "
                "Build will fail until the INA226 backend exists."
            )

        if not quiet:
            messagebox.showinfo("Generated", "Board profile and platformio.user.ini generated.")
        return True

    def _build(self) -> None:
        if self._generate_files(quiet=True):
            self._run_pio(["run"])

    def _upload(self) -> None:
        if self._generate_files(quiet=True):
            self._run_pio(["run", "-t", "upload"])

    def _clean(self) -> None:
        if self._generate_files(quiet=True):
            self._run_pio(["run", "-t", "clean"])

    def _find_pio(self) -> str | None:
        found = shutil.which("pio")
        if found:
            return found

        home = Path.home()
        candidates = [
            home / ".platformio" / "penv" / "Scripts" / "pio.exe",
            home / ".platformio" / "penv" / "Scripts" / "pio",
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        return None

    def _run_pio(self, action: list[str]) -> None:
        pio = self._find_pio()
        if pio is None:
            messagebox.showerror(
                "PlatformIO not found",
                "Could not find pio. Install PlatformIO or add it to PATH.",
            )
            return

        env_name = self._env_name()
        command = [pio, *action, "-c", str(USER_INI), "-e", env_name]
        self._log("")
        self._log("Running: " + " ".join(command))

        thread = threading.Thread(
            target=self._run_process,
            args=(command,),
            daemon=True,
        )
        thread.start()

    def _run_process(self, command: list[str]) -> None:
        try:
            process = subprocess.Popen(
                command,
                cwd=FIRMWARE_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            self._log_threadsafe(f"Could not start PlatformIO: {exc}")
            return

        assert process.stdout is not None
        for line in process.stdout:
            self._log_threadsafe(line.rstrip())

        return_code = process.wait()
        self._log_threadsafe(f"PlatformIO exited with code {return_code}")

    def _log(self, message: str) -> None:
        self.output.insert("end", message + "\n")
        self.output.see("end")

    def _log_threadsafe(self, message: str) -> None:
        self.root.after(0, lambda: self._log(message))


def main() -> None:
    root = tk.Tk()
    BoardConfigurator(root)
    root.mainloop()


if __name__ == "__main__":
    main()
