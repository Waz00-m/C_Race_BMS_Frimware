"""
Board profile configurator for the Drone BMS firmware.

This tool generates user-owned board profile files and a PlatformIO user config
without modifying the portable BMS core.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import threading
from datetime import datetime
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
PROFILE_MANIFEST = "bms_profile_manifest.json"

MCU_BLOCKS = [
    "ESP32 DevKit / Arduino",
    "NXP S32K",
    "STM32 H series",
    "STM32 F series",
    "TI MCU",
]

VOLTAGE_BLOCKS = [
    "6S cumulative divider taps",
    "6S direct cell inputs",
    "LTC6811 AFE",
    "BQ76952 monitor/protector",
]

CURRENT_BLOCKS = [
    "INA240 analog shunt",
    "ACS772 analog Hall",
    "INA226 I2C shunt monitor",
]

TEMPERATURE_BLOCKS = [
    "10k NTC beta thermistors",
    "PTC temperature sensor",
]

DISPLAY_BLOCKS = [
    "SSD1306 OLED 128x64",
    "No display",
]

COMPONENT_LIBRARY = [
    {
        "id": "mcu_esp32",
        "category": "mcu",
        "label": "ESP32 DevKit",
        "detail": "Arduino PlatformIO target",
        "block_var": "mcu_block",
        "block_value": "ESP32 DevKit / Arduino",
        "config_tab": "Board",
        "color": "#cfe0ff",
        "implemented": True,
    },
    {
        "id": "mcu_nxp_s32k",
        "category": "mcu",
        "label": "NXP S32K",
        "detail": "Planned NXP automotive MCU",
        "block_var": "mcu_block",
        "block_value": "NXP S32K",
        "config_tab": "Board",
        "color": "#d8e4ff",
        "implemented": False,
        "note": "Needs NXP platform HAL and PlatformIO/CMake target.",
    },
    {
        "id": "mcu_stm32h",
        "category": "mcu",
        "label": "STM32H Series",
        "detail": "Planned STM32 high-performance MCU",
        "block_var": "mcu_block",
        "block_value": "STM32 H series",
        "config_tab": "Board",
        "color": "#d8e4ff",
        "implemented": False,
        "note": "Needs STM32H platform HAL and build target.",
    },
    {
        "id": "mcu_stm32f",
        "category": "mcu",
        "label": "STM32F Series",
        "detail": "Planned STM32 general MCU",
        "block_var": "mcu_block",
        "block_value": "STM32 F series",
        "config_tab": "Board",
        "color": "#d8e4ff",
        "implemented": False,
        "note": "Needs STM32F platform HAL and build target.",
    },
    {
        "id": "mcu_ti",
        "category": "mcu",
        "label": "TI MCU",
        "detail": "Planned TI controller target",
        "block_var": "mcu_block",
        "block_value": "TI MCU",
        "config_tab": "Board",
        "color": "#d8e4ff",
        "implemented": False,
        "note": "Needs TI platform HAL and build target.",
    },
    {
        "id": "voltage_divider_6s",
        "category": "voltage",
        "label": "6S Divider Taps",
        "detail": "Cumulative voltage divider",
        "block_var": "voltage_block",
        "block_value": "6S cumulative divider taps",
        "config_tab": "Voltage",
        "color": "#d7f2df",
        "implemented": True,
    },
    {
        "id": "voltage_direct_6s",
        "category": "voltage",
        "label": "6S Direct Cells",
        "detail": "Direct per-cell ADC mode",
        "block_var": "voltage_block",
        "block_value": "6S direct cell inputs",
        "config_tab": "Voltage",
        "color": "#d7f2df",
        "implemented": True,
    },
    {
        "id": "voltage_ltc6811",
        "category": "voltage",
        "label": "LTC6811",
        "detail": "Planned daisy-chain AFE",
        "block_var": "voltage_block",
        "block_value": "LTC6811 AFE",
        "config_tab": "Voltage",
        "color": "#e2f5e8",
        "implemented": False,
        "note": "Needs SPI/isoSPI HAL plus LTC6811 voltage backend.",
    },
    {
        "id": "voltage_bq76952",
        "category": "voltage",
        "label": "BQ76952",
        "detail": "Planned TI monitor/protector AFE",
        "block_var": "voltage_block",
        "block_value": "BQ76952 monitor/protector",
        "config_tab": "Voltage",
        "color": "#e2f5e8",
        "implemented": False,
        "note": "Needs BQ76952 register backend and transport HAL.",
    },
    {
        "id": "current_ina240",
        "category": "current",
        "label": "INA240",
        "detail": "Analog shunt amplifier",
        "block_var": "current_block",
        "block_value": "INA240 analog shunt",
        "config_tab": "Current",
        "color": "#ffe1c7",
        "implemented": True,
    },
    {
        "id": "current_acs772",
        "category": "current",
        "label": "ACS772",
        "detail": "Analog Hall current sensor",
        "block_var": "current_block",
        "block_value": "ACS772 analog Hall",
        "config_tab": "Current",
        "color": "#ffe1c7",
        "implemented": True,
    },
    {
        "id": "current_ina226",
        "category": "current",
        "label": "INA226",
        "detail": "I2C shunt monitor",
        "block_var": "current_block",
        "block_value": "INA226 I2C shunt monitor",
        "config_tab": "Current",
        "color": "#ffe1c7",
        "implemented": True,
    },
    {
        "id": "temp_ntc_10k",
        "category": "temperature",
        "label": "10k NTC",
        "detail": "Beta thermistor inputs",
        "block_var": "temperature_block",
        "block_value": "10k NTC beta thermistors",
        "config_tab": "Temperature",
        "color": "#f1dcff",
        "implemented": True,
    },
    {
        "id": "temp_ptc",
        "category": "temperature",
        "label": "PTC Sensor",
        "detail": "Planned PTC temperature input",
        "block_var": "temperature_block",
        "block_value": "PTC temperature sensor",
        "config_tab": "Temperature",
        "color": "#f6e8ff",
        "implemented": False,
        "note": "Needs PTC resistance conversion and validation backend.",
    },
    {
        "id": "display_ssd1306",
        "category": "display",
        "label": "SSD1306 OLED",
        "detail": "128x64 I2C display",
        "block_var": "display_block",
        "block_value": "SSD1306 OLED 128x64",
        "config_tab": "Pins/OLED",
        "color": "#d9eef2",
        "implemented": True,
    },
    {
        "id": "display_none",
        "category": "display",
        "label": "No Display",
        "detail": "Headless firmware build",
        "block_var": "display_block",
        "block_value": "No display",
        "config_tab": "Pins/OLED",
        "color": "#eeeeee",
        "implemented": True,
    },
]

COMPONENT_BY_ID = {component["id"]: component for component in COMPONENT_LIBRARY}

BOARD_SLOT_LAYOUT = {
    "mcu": {"title": "MCU", "x": 35, "y": 60},
    "voltage": {"title": "Voltage Sense", "x": 300, "y": 60},
    "current": {"title": "Current Sense", "x": 565, "y": 60},
    "temperature": {"title": "Temperature", "x": 300, "y": 225},
    "display": {"title": "Display", "x": 565, "y": 225},
}

BOARD_SLOT_WIDTH = 210
BOARD_SLOT_HEIGHT = 110


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
        self.profile_listbox: tk.Listbox | None = None
        self.notebook: ttk.Notebook | None = None
        self.tab_indices: dict[str, int] = {}
        self.palette_canvas: tk.Canvas | None = None
        self.board_canvas: tk.Canvas | None = None
        self.block_detail_var = tk.StringVar(value="Drag blocks onto the board.")
        self.selected_component_id: str | None = None
        self.drag_component_id: str | None = None
        self.drag_preview: tk.Toplevel | None = None
        self.board_components: dict[str, str] = {
            "mcu": "mcu_esp32",
            "voltage": "voltage_divider_6s",
            "current": "current_ina240",
            "temperature": "temp_ntc_10k",
            "display": "display_ssd1306",
        }

        self._init_vars()
        self._build_ui()

    def _init_vars(self) -> None:
        defaults = {
            "profile_slug": "my_6s_esp32_profile0",
            "board_name": "MY_6S_ESP32_PROFILE0",
            "env_name": "my_6s_esp32",
            "platformio_board": "esp32dev",
            "upload_port": "COM3",
            "mcu_block": MCU_BLOCKS[0],
            "voltage_block": VOLTAGE_BLOCKS[0],
            "current_block": CURRENT_BLOCKS[0],
            "temperature_block": TEMPERATURE_BLOCKS[0],
            "display_block": DISPLAY_BLOCKS[0],
            "voltage_mode": "cumulative_taps",
            "current_sensor": "analog_ina240",
            "current_zero_mv": "1650.0",
            "current_shunt_ohm": "0.00025",
            "current_ina_gain": "38.30",
            "hall_sensitivity_mv_per_a": "20.0",
            "current_polarity": "1.0",
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
            "ina226_config_register": "0x4127",
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
            "i2c_sda": "21",
            "i2c_scl": "22",
            "i2c_clock_hz": "400000",
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
        self.notebook = notebook

        self._build_board_tab(notebook)
        self._build_blocks_tab(notebook)
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
        self.tab_indices["Board"] = notebook.index(frame)

        self._entry(frame, 0, "Profile folder", "profile_slug", width=32)
        self._entry(frame, 1, "Board name", "board_name", width=32)
        self._entry(frame, 2, "PlatformIO env", "env_name", width=32)
        self._entry(frame, 3, "PIO board", "platformio_board", width=32)
        self._entry(frame, 4, "Upload port", "upload_port", width=32)

        ttk.Label(
            frame,
            text=(
                "Generated files go under bms_boards/generated/<profile folder>. "
                "Select hardware by dragging blocks on the Builder tab. "
                "The firmware core is not edited."
            ),
            wraplength=720,
        ).grid(row=6, column=0, columnspan=4, sticky="w", pady=(18, 3))

    def _build_blocks_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=12)
        notebook.add(frame, text="Builder")
        self.tab_indices["Builder"] = notebook.index(frame)

        palette_frame = ttk.LabelFrame(frame, text="Hardware Palette", padding=8)
        palette_frame.grid(row=0, column=0, sticky="ns", padx=(0, 10))

        board_frame = ttk.LabelFrame(frame, text="Board Canvas", padding=8)
        board_frame.grid(row=0, column=1, sticky="nsew")

        detail_frame = ttk.LabelFrame(frame, text="Selected Block", padding=8)
        detail_frame.grid(row=0, column=2, sticky="ns", padx=(10, 0))

        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(0, weight=1)

        self.palette_canvas = tk.Canvas(
            palette_frame,
            width=250,
            height=560,
            bg="#f6f7fb",
            highlightthickness=0,
        )
        palette_scroll = ttk.Scrollbar(
            palette_frame,
            orient="vertical",
            command=self.palette_canvas.yview,
        )
        self.palette_canvas.configure(yscrollcommand=palette_scroll.set)
        self.palette_canvas.pack(side="left", fill="both", expand=True)
        palette_scroll.pack(side="right", fill="y")

        self.board_canvas = tk.Canvas(
            board_frame,
            width=800,
            height=560,
            bg="#f9faf8",
            highlightthickness=0,
        )
        self.board_canvas.pack(fill="both", expand=True)

        ttk.Label(
            detail_frame,
            textvariable=self.block_detail_var,
            wraplength=230,
            justify="left",
        ).pack(fill="x", pady=(0, 8))

        ttk.Button(
            detail_frame,
            text="Configure Selected",
            command=self._configure_selected_component,
        ).pack(fill="x", pady=3)
        ttk.Button(
            detail_frame,
            text="Remove Selected",
            command=self._remove_selected_component,
        ).pack(fill="x", pady=3)
        ttk.Button(
            detail_frame,
            text="Use Prototype0 Defaults",
            command=self._load_prototype0_builder_defaults,
        ).pack(fill="x", pady=(18, 3))
        ttk.Button(
            detail_frame,
            text="Continue To Build",
            command=lambda: self._select_tab("Generate/Build"),
        ).pack(fill="x", pady=3)

        self._draw_palette()
        self._render_board_canvas()

    def _draw_palette(self) -> None:
        if self.palette_canvas is None:
            return

        self.palette_canvas.delete("all")
        self.palette_canvas.create_text(
            14,
            14,
            anchor="nw",
            text="Drag a block to the board",
            fill="#333333",
            font=("Segoe UI", 9, "bold"),
        )

        for index, component in enumerate(COMPONENT_LIBRARY):
            x0 = 14
            y0 = 42 + (index * 56)
            x1 = 232
            y1 = y0 + 44
            tag = f"palette:{component['id']}"

            self.palette_canvas.create_rectangle(
                x0,
                y0,
                x1,
                y1,
                fill=str(component["color"]),
                outline="#8a8f98",
                width=1,
                tags=(tag,),
            )
            self.palette_canvas.create_text(
                x0 + 10,
                y0 + 9,
                anchor="nw",
                text=str(component["label"]),
                fill="#1f2933",
                font=("Segoe UI", 9, "bold"),
                tags=(tag,),
            )
            self.palette_canvas.create_text(
                x0 + 10,
                y0 + 26,
                anchor="nw",
                text=str(component["detail"]),
                fill="#4b5563",
                font=("Segoe UI", 8),
                tags=(tag,),
            )
            if not bool(component.get("implemented", False)):
                self.palette_canvas.create_text(
                    x1 - 10,
                    y0 + 9,
                    anchor="ne",
                    text="PLANNED",
                    fill="#7c2d12",
                    font=("Segoe UI", 7, "bold"),
                    tags=(tag,),
                )

            self.palette_canvas.tag_bind(
                tag,
                "<ButtonPress-1>",
                lambda event, cid=component["id"]: self._start_component_drag(event, str(cid)),
            )
            self.palette_canvas.tag_bind(
                tag,
                "<B1-Motion>",
                self._move_component_drag,
            )
            self.palette_canvas.tag_bind(
                tag,
                "<ButtonRelease-1>",
                self._finish_component_drag,
            )

        self.palette_canvas.configure(scrollregion=self.palette_canvas.bbox("all"))

    def _render_board_canvas(self) -> None:
        if self.board_canvas is None:
            return

        self.board_canvas.delete("all")
        self.board_canvas.create_text(
            22,
            18,
            anchor="nw",
            text="Drop hardware blocks into their slots",
            fill="#222222",
            font=("Segoe UI", 12, "bold"),
        )

        for category, layout in BOARD_SLOT_LAYOUT.items():
            x0 = int(layout["x"])
            y0 = int(layout["y"])
            x1 = x0 + BOARD_SLOT_WIDTH
            y1 = y0 + BOARD_SLOT_HEIGHT

            self.board_canvas.create_rectangle(
                x0,
                y0,
                x1,
                y1,
                fill="#ffffff",
                outline="#b7bec8",
                width=2,
            )
            self.board_canvas.create_text(
                x0 + 10,
                y0 + 8,
                anchor="nw",
                text=str(layout["title"]),
                fill="#374151",
                font=("Segoe UI", 9, "bold"),
            )

            component_id = self.board_components.get(category)
            if component_id is None:
                self.board_canvas.create_text(
                    x0 + 14,
                    y0 + 50,
                    anchor="nw",
                    text="Drop block here",
                    fill="#9ca3af",
                    font=("Segoe UI", 9),
                )
                continue

            component = COMPONENT_BY_ID[component_id]
            self._draw_board_component(category, component, x0, y0)

    def _draw_board_component(
        self,
        category: str,
        component: dict[str, object],
        x0: int,
        y0: int,
    ) -> None:
        if self.board_canvas is None:
            return

        selected = component["id"] == self.selected_component_id
        outline = "#1d4ed8" if selected else "#6b7280"
        tag = f"board:{category}"
        card_x0 = x0 + 12
        card_y0 = y0 + 36
        card_x1 = x0 + BOARD_SLOT_WIDTH - 12
        card_y1 = y0 + BOARD_SLOT_HEIGHT - 12

        self.board_canvas.create_rectangle(
            card_x0,
            card_y0,
            card_x1,
            card_y1,
            fill=str(component["color"]),
            outline=outline,
            width=2,
            tags=(tag,),
        )
        self.board_canvas.create_text(
            card_x0 + 10,
            card_y0 + 10,
            anchor="nw",
            text=str(component["label"]),
            fill="#111827",
            font=("Segoe UI", 10, "bold"),
            tags=(tag,),
        )
        self.board_canvas.create_text(
            card_x0 + 10,
            card_y0 + 32,
            anchor="nw",
            text=str(component["detail"]),
            fill="#374151",
            font=("Segoe UI", 8),
            tags=(tag,),
        )
        if not bool(component.get("implemented", False)):
            self.board_canvas.create_text(
                card_x1 - 10,
                card_y0 + 10,
                anchor="ne",
                text="PLANNED",
                fill="#7c2d12",
                font=("Segoe UI", 7, "bold"),
                tags=(tag,),
            )

        self.board_canvas.tag_bind(
            tag,
            "<Button-1>",
            lambda event, cid=component["id"]: self._select_component(str(cid)),
        )

    def _start_component_drag(self, event: tk.Event, component_id: str) -> None:
        component = COMPONENT_BY_ID[component_id]
        self.drag_component_id = component_id
        self._destroy_drag_preview()

        self.drag_preview = tk.Toplevel(self.root)
        self.drag_preview.overrideredirect(True)
        label = tk.Label(
            self.drag_preview,
            text=str(component["label"]),
            bg=str(component["color"]),
            fg="#111827",
            relief="solid",
            borderwidth=1,
            padx=12,
            pady=7,
            font=("Segoe UI", 9, "bold"),
        )
        label.pack()
        self._move_component_drag(event)

    def _move_component_drag(self, event: tk.Event) -> None:
        if self.drag_preview is None:
            return

        self.drag_preview.geometry(f"+{event.x_root + 12}+{event.y_root + 12}")

    def _finish_component_drag(self, event: tk.Event) -> None:
        component_id = self.drag_component_id
        self.drag_component_id = None
        self._destroy_drag_preview()

        if (component_id is None) or (self.board_canvas is None):
            return

        x = event.x_root - self.board_canvas.winfo_rootx()
        y = event.y_root - self.board_canvas.winfo_rooty()
        if (x < 0) or (y < 0):
            return
        if (x > self.board_canvas.winfo_width()) or (y > self.board_canvas.winfo_height()):
            return

        self._place_component(component_id)

    def _destroy_drag_preview(self) -> None:
        if self.drag_preview is not None:
            self.drag_preview.destroy()
            self.drag_preview = None

    def _place_component(self, component_id: str) -> None:
        component = COMPONENT_BY_ID[component_id]
        category = str(component["category"])
        self.board_components[category] = component_id
        self.vars[str(component["block_var"])].set(str(component["block_value"]))
        self._apply_selected_blocks(log=False)
        self._select_component(component_id)
        self._log(f"Placed {component['label']} in {category} slot.")

    def _select_component(self, component_id: str) -> None:
        self.selected_component_id = component_id
        self._update_selected_component_detail()
        self._render_board_canvas()

    def _update_selected_component_detail(self) -> None:
        if self.selected_component_id is None:
            self.block_detail_var.set("Drag blocks onto the board.")
            return

        component = COMPONENT_BY_ID[self.selected_component_id]
        status = "Implemented" if bool(component.get("implemented", False)) else "Placeholder only"
        note = str(component.get("note", ""))
        note_text = f"\n\n{note}" if note else ""
        self.block_detail_var.set(
            f"{component['label']}\n"
            f"{component['detail']}\n\n"
            f"Slot: {component['category']}\n"
            f"Configure in: {component['config_tab']}\n"
            f"Status: {status}"
            f"{note_text}"
        )

    def _configure_selected_component(self) -> None:
        if self.selected_component_id is None:
            messagebox.showinfo("No block selected", "Select a block on the board first.")
            return

        component = COMPONENT_BY_ID[self.selected_component_id]
        self._select_tab(str(component["config_tab"]))

    def _remove_selected_component(self) -> None:
        if self.selected_component_id is None:
            messagebox.showinfo("No block selected", "Select a block on the board first.")
            return

        component = COMPONENT_BY_ID[self.selected_component_id]
        category = str(component["category"])
        self.board_components.pop(category, None)
        self.selected_component_id = None
        self._update_vars_from_board_components()
        self._render_board_canvas()
        self._update_selected_component_detail()
        self._log(f"Removed {component['label']} from {category} slot.")

    def _load_prototype0_builder_defaults(self) -> None:
        self.board_components = {
            "mcu": "mcu_esp32",
            "voltage": "voltage_divider_6s",
            "current": "current_ina240",
            "temperature": "temp_ntc_10k",
            "display": "display_ssd1306",
        }
        self._update_vars_from_board_components()
        self.selected_component_id = None
        self._render_board_canvas()
        self._update_selected_component_detail()
        self._log("Loaded Prototype0 builder defaults.")

    def _update_vars_from_board_components(self) -> None:
        for component_id in self.board_components.values():
            component = COMPONENT_BY_ID[component_id]
            self.vars[str(component["block_var"])].set(str(component["block_value"]))
        self._apply_selected_blocks(log=False)

    def _planned_components(self) -> list[dict[str, object]]:
        return [
            COMPONENT_BY_ID[component_id]
            for component_id in self.board_components.values()
            if not bool(COMPONENT_BY_ID[component_id].get("implemented", False))
        ]

    def _select_tab(self, tab_name: str) -> None:
        if self.notebook is None:
            return

        index = self.tab_indices.get(tab_name)
        if index is not None:
            self.notebook.select(index)

    def _build_voltage_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=12)
        notebook.add(frame, text="Voltage")
        self.tab_indices["Voltage"] = notebook.index(frame)

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
        self.tab_indices["Current"] = notebook.index(frame)

        self._entry(frame, 0, "Zero mV", "current_zero_mv")
        self._entry(frame, 1, "Shunt ohm", "current_shunt_ohm")
        self._entry(frame, 2, "INA gain", "current_ina_gain")
        self._entry(frame, 3, "Hall sensitivity mV/A", "hall_sensitivity_mv_per_a")
        self._entry(frame, 4, "Current polarity", "current_polarity")
        self._entry(frame, 5, "ADC high valid mV", "current_adc_high_mv")
        self._entry(frame, 6, "ADC gain correction", "current_adc_gain")
        self._entry(frame, 7, "ADC offset mV", "current_adc_offset_mv")
        self._entry(frame, 8, "Reading gain", "current_reading_gain")
        self._entry(frame, 9, "Offset mA", "current_offset_ma")
        self._entry(frame, 10, "Smooth alpha", "current_smooth_alpha")
        self._entry(frame, 11, "No-load enter mA", "current_noload_enter_ma")
        self._entry(frame, 12, "No-load exit mA", "current_noload_exit_ma")

        self._entry(frame, 0, "INA226 address", "ina226_address", column=3)
        self._entry(frame, 1, "INA226 shunt ohm", "ina226_shunt_ohm", column=3)
        self._entry(
            frame,
            2,
            "INA226 max current mA",
            "ina226_max_current_ma",
            column=3,
        )
        self._entry(
            frame,
            3,
            "INA226 config reg",
            "ina226_config_register",
            column=3,
        )

        ttk.Label(
            frame,
            text="INA226 uses the shared I2C bus and the firmware I2C backend.",
            wraplength=430,
        ).grid(row=5, column=3, columnspan=2, sticky="w", padx=4, pady=12)

    def _build_temperature_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=12)
        notebook.add(frame, text="Temperature")
        self.tab_indices["Temperature"] = notebook.index(frame)

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
        self.tab_indices["Pins/OLED"] = notebook.index(frame)

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

        i2c_fields = [
            ("SDA", "i2c_sda"),
            ("SCL", "i2c_scl"),
            ("Clock Hz", "i2c_clock_hz"),
        ]
        for row, (label, key) in enumerate(i2c_fields):
            self._entry(frame, row, f"I2C {label}", key, width=12, column=6)

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
            self._entry(frame, row + 4, f"OLED {label}", key, width=12, column=6)

    def _build_generate_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=12)
        notebook.add(frame, text="Generate/Build")
        self.tab_indices["Generate/Build"] = notebook.index(frame)

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

        manager = ttk.LabelFrame(frame, text="Generated Profiles", padding=8)
        manager.pack(fill="x", pady=(12, 0))

        self.profile_listbox = tk.Listbox(
            manager,
            height=5,
            exportselection=False,
        )
        self.profile_listbox.grid(row=0, column=0, rowspan=4, sticky="ew", padx=4)

        profile_buttons = ttk.Frame(manager)
        profile_buttons.grid(row=0, column=1, sticky="nw", padx=8)
        ttk.Button(
            profile_buttons,
            text="Refresh",
            command=self._refresh_generated_profiles,
        ).pack(fill="x", pady=2)
        ttk.Button(
            profile_buttons,
            text="Delete Profile Files",
            command=self._delete_selected_profile,
        ).pack(fill="x", pady=2)
        ttk.Button(
            profile_buttons,
            text="Remove Build Cache",
            command=self._remove_selected_profile_build_cache,
        ).pack(fill="x", pady=2)

        manager.columnconfigure(0, weight=1)

        self.output = tk.Text(frame, height=28, wrap="none")
        self.output.pack(fill="both", expand=True, pady=(12, 0))
        self._log("Ready. Generate a board profile, then Build or Upload.")
        self._refresh_generated_profiles()

    def _apply_selected_blocks(self, log: bool = True) -> None:
        if self.vars["mcu_block"].get() == "ESP32 DevKit / Arduino":
            self.vars["platformio_board"].set("esp32dev")

        if self.vars["voltage_block"].get() == "6S direct cell inputs":
            self.vars["voltage_mode"].set("direct_cell")
        else:
            self.vars["voltage_mode"].set("cumulative_taps")

        current_block = self.vars["current_block"].get()
        if current_block == "INA226 I2C shunt monitor":
            self.vars["current_sensor"].set("ina226")
            self.vars["ina226_address"].set("0x40")
            self.vars["ina226_shunt_ohm"].set("0.00025")
            self.vars["ina226_max_current_ma"].set("120000")
            self.vars["ina226_config_register"].set("0x4127")
        elif current_block == "ACS772 analog Hall":
            self.vars["current_sensor"].set("analog_acs772")
            self.vars["current_zero_mv"].set("1650.0")
            self.vars["hall_sensitivity_mv_per_a"].set("20.0")
            self.vars["current_polarity"].set("1.0")
        else:
            self.vars["current_sensor"].set("analog_ina240")
            self.vars["current_zero_mv"].set("1650.0")
            self.vars["current_shunt_ohm"].set("0.00025")
            self.vars["current_ina_gain"].set("38.30")

        if self.vars["temperature_block"].get() == "10k NTC beta thermistors":
            self.vars["ntc_fixed_ohm"].set("10000.0")
            self.vars["ntc_nominal_ohm"].set("10000.0")
            self.vars["ntc_beta"].set("3435.0")
            self.bool_vars["ntc_to_ground"].set(True)

        if self.vars["display_block"].get() == "SSD1306 OLED 128x64":
            self.vars["oled_width"].set("128")
            self.vars["oled_height"].set("64")
            self.vars["oled_address"].set("0x3C")
            self.vars["oled_reset"].set("-1")

        if log:
            self._log("Applied selected hardware blocks to profile fields.")

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
        if sensor == "ina226":
            address = parse_int(self.vars["ina226_address"].get(), 0x40)
            config = parse_int(self.vars["ina226_config_register"].get(), 0x4127)
            return [
                "#define BMS_CURRENT_SENSOR_TYPE BMS_CURRENT_SENSOR_INA226",
                f"#define BMS_INA226_I2C_ADDRESS (0x{address:02X}U)",
                f"#define BMS_INA226_SHUNT_OHM ({c_float(parse_float(self.vars['ina226_shunt_ohm'].get(), 0.00025))})",
                f"#define BMS_INA226_MAX_EXPECTED_CURRENT_MA ({parse_int(self.vars['ina226_max_current_ma'].get(), 120000)}L)",
                f"#define BMS_INA226_CONFIG_REGISTER (0x{config:04X}U)",
            ]

        if sensor == "analog_acs772":
            return ["#define BMS_CURRENT_SENSOR_TYPE BMS_CURRENT_SENSOR_ANALOG_ACS772"]

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
#define BMS_CURRENT_HALL_SENSITIVITY_MV_PER_A ({c_float(parse_float(self.vars["hall_sensitivity_mv_per_a"].get(), 20.0))})
#define BMS_CURRENT_SENSOR_POLARITY ({c_float(parse_float(self.vars["current_polarity"].get(), 1.0))})
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

#define BMS_I2C_SDA_PIN ({parse_int(self.vars["i2c_sda"].get(), 21)})
#define BMS_I2C_SCL_PIN ({parse_int(self.vars["i2c_scl"].get(), 22)})
#define BMS_I2C_CLOCK_HZ ({parse_int(self.vars["i2c_clock_hz"].get(), 400000)}UL)

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

    def _manifest_data(self, profile_folder: str, profile_include: str) -> dict[str, object]:
        return {
            "schema": 1,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "profile_folder": profile_folder,
            "profile_include": profile_include,
            "board_name": self._board_name(),
            "env_name": self._env_name(),
            "platformio_board": sanitize_identifier(
                self.vars["platformio_board"].get(),
                "esp32dev",
            ),
            "upload_port": self.vars["upload_port"].get().strip() or "COM3",
            "blocks": {
                "mcu": self.vars["mcu_block"].get(),
                "voltage": self.vars["voltage_block"].get(),
                "current": self.vars["current_block"].get(),
                "temperature": self.vars["temperature_block"].get(),
                "display": self.vars["display_block"].get(),
            },
            "board_components": dict(self.board_components),
            "current_sensor": self.vars["current_sensor"].get(),
        }

    def _validate_builder(self) -> bool:
        missing = [
            str(layout["title"])
            for category, layout in BOARD_SLOT_LAYOUT.items()
            if category not in self.board_components
        ]
        if missing:
            messagebox.showerror(
                "Board incomplete",
                "Drop blocks into these slots before generating: " + ", ".join(missing),
            )
            return False

        planned = self._planned_components()
        if planned:
            lines = [
                f"- {component['label']}: {component.get('note', 'backend not implemented')}"
                for component in planned
            ]
            messagebox.showerror(
                "Placeholder blocks selected",
                "These blocks are placeholders and cannot generate firmware yet:\n\n"
                + "\n".join(lines),
            )
            return False

        return True

    @staticmethod
    def _safe_child_path(root: Path, child_name: str) -> Path:
        resolved_root = root.resolve()
        target = (resolved_root / child_name).resolve()
        target.relative_to(resolved_root)
        return target

    def _read_profile_manifest(self, profile_folder: str) -> dict[str, object]:
        try:
            profile_dir = self._safe_child_path(GENERATED_DIR, profile_folder)
            manifest_file = profile_dir / PROFILE_MANIFEST
            if not manifest_file.exists():
                return {}
            with manifest_file.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                return data
        except (OSError, ValueError, json.JSONDecodeError):
            return {}
        return {}

    def _generate_files(self, quiet: bool = False) -> bool:
        if not self._validate_builder():
            return False

        self._update_vars_from_board_components()

        profile_folder = self._profile_folder()
        target_dir = GENERATED_DIR / profile_folder
        target_dir.mkdir(parents=True, exist_ok=True)

        guard = f"BMS_GENERATED_{macro_name(profile_folder)}"
        common_file = target_dir / "bms_board_common.h"
        profile_file = target_dir / "bms_board_profile.h"
        manifest_file = target_dir / PROFILE_MANIFEST
        profile_include = f"generated/{profile_folder}/bms_board_profile.h"

        common_file.write_text(self._common_header_text(guard), encoding="utf-8")
        profile_file.write_text(self._profile_header_text(guard), encoding="utf-8")
        manifest_file.write_text(
            json.dumps(self._manifest_data(profile_folder, profile_include), indent=2),
            encoding="utf-8",
        )
        USER_INI.write_text(self._platformio_text(profile_include), encoding="utf-8")

        self._log(f"Generated {common_file.relative_to(FIRMWARE_DIR)}")
        self._log(f"Generated {profile_file.relative_to(FIRMWARE_DIR)}")
        self._log(f"Generated {manifest_file.relative_to(FIRMWARE_DIR)}")
        self._log(f"Generated {USER_INI.relative_to(FIRMWARE_DIR)}")
        self._refresh_generated_profiles()

        if not quiet:
            messagebox.showinfo("Generated", "Board profile and platformio.user.ini generated.")
        return True

    def _refresh_generated_profiles(self) -> None:
        if self.profile_listbox is None:
            return

        self.profile_listbox.delete(0, "end")
        if not GENERATED_DIR.exists():
            return

        for profile_dir in sorted(GENERATED_DIR.iterdir()):
            if profile_dir.is_dir():
                self.profile_listbox.insert("end", profile_dir.name)

    def _selected_generated_profile(self) -> str | None:
        if self.profile_listbox is None:
            return None

        selected = self.profile_listbox.curselection()
        if not selected:
            return None

        return str(self.profile_listbox.get(selected[0]))

    def _delete_selected_profile(self) -> None:
        profile_folder = self._selected_generated_profile()
        if profile_folder is None:
            messagebox.showinfo("No profile selected", "Select a generated profile first.")
            return

        target_dir = self._safe_child_path(GENERATED_DIR, profile_folder)
        if not target_dir.exists():
            self._log(f"Generated profile is already missing: {profile_folder}")
            self._refresh_generated_profiles()
            return

        if not messagebox.askyesno(
            "Delete generated profile",
            f"Delete generated profile files for '{profile_folder}'?",
        ):
            return

        shutil.rmtree(target_dir)
        self._log(f"Deleted generated profile files: {profile_folder}")
        self._refresh_generated_profiles()

    def _remove_selected_profile_build_cache(self) -> None:
        profile_folder = self._selected_generated_profile()
        if profile_folder is None:
            messagebox.showinfo("No profile selected", "Select a generated profile first.")
            return

        manifest = self._read_profile_manifest(profile_folder)
        env_name = str(manifest.get("env_name") or sanitize_identifier(profile_folder, profile_folder))
        build_root = FIRMWARE_DIR / ".pio" / "build"
        target_dir = self._safe_child_path(build_root, env_name)

        if not target_dir.exists():
            self._log(f"No build cache found for env '{env_name}'.")
            return

        if not messagebox.askyesno(
            "Remove build cache",
            f"Remove PlatformIO build cache for env '{env_name}'?",
        ):
            return

        shutil.rmtree(target_dir)
        self._log(f"Removed build cache: .pio/build/{env_name}")

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
