"""
Portable Drone BMS firmware dashboard.

This dashboard is for the staged portable firmware, not the older Prototype-0
CSV firmware. It reads the current serial heartbeat and diagnostic responses.

Required:
    pip install pyserial

How to run:
    python bms_firmware_dashboard.py

Useful firmware commands:
    HELP
    GET,SNAPSHOT
    GET,VOLT
    GET,CURRENT
    GET,TEMP
    GET,FAULT
    GET,SLEEP
    GET,TAPS
    GET,CFG
"""

import csv
import datetime as dt
import queue
import re
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    raise SystemExit("pyserial is missing. Install it using: pip install pyserial")

BAUD_RATE = 115200
CSV_LOG_FILE = "bms_firmware_dashboard_log.csv"

WARNING_BITS = {
    0x00000001: "Cell low",
    0x00000002: "Cell high",
    0x00000004: "Cell imbalance",
    0x00000008: "Overcurrent",
    0x00000010: "Temperature high",
    0x00000020: "Sensor invalid",
}

FAULT_BITS = {
    0x00000001: "Cell undervoltage",
    0x00000002: "Cell overvoltage",
    0x00000004: "Pack undervoltage",
    0x00000008: "Pack overvoltage",
    0x00000010: "Overcurrent",
    0x00000020: "Temperature high",
    0x00000040: "Sensor invalid",
}

FAULT_CODES = {
    "0x0000": "No fault",
    "0x1001": "Cell overvoltage",
    "0x1002": "Cell undervoltage",
    "0x1003": "Pack overvoltage",
    "0x1004": "Pack undervoltage",
    "0x2002": "Discharge overcurrent",
    "0x2003": "Current sensor fault",
    "0x3001": "Cell temperature high",
    "0x3003": "Temperature sensor fault",
    "0x4001": "ADC read failure",
    "0x4002": "Measurement invalid",
}

VALIDATION_REASON_BITS = {
    0x00000001: "ADC missing",
    0x00000002: "ADC range",
    0x00000004: "Tap range",
    0x00000008: "Tap order",
    0x00000010: "Cell range",
    0x00000020: "Tap step",
    0x00000040: "Cell step",
    0x00000080: "ADC stuck",
    0x00000100: "Current sensor",
    0x00000200: "Current range",
    0x00000400: "Temperature sensor",
    0x00000800: "Temperature range",
}


def split_top_level(text, sep=","):
    parts = []
    depth = 0
    start = 0
    for i, char in enumerate(text):
        if char == "[":
            depth += 1
        elif char == "]" and depth > 0:
            depth -= 1
        elif char == sep and depth == 0:
            parts.append(text[start:i].strip())
            start = i + 1
    parts.append(text[start:].strip())
    return parts


def parse_kv_payload(payload):
    result = {}
    for part in split_top_level(payload):
        if "=" in part:
            key, value = part.split("=", 1)
            result[key.strip()] = value.strip()
    return result


def parse_int(value, default=0):
    try:
        return int(str(value).strip(), 0)
    except (TypeError, ValueError):
        return default


def parse_int_list(value, expected):
    text = str(value).strip()
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    values = []
    for item in split_top_level(text):
        if item:
            values.append(parse_int(item))
    while len(values) < expected:
        values.append(None)
    return values[:expected]


def parse_temp_list(value, expected):
    text = str(value).strip()
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    values = []
    for item in split_top_level(text):
        item = item.strip()
        if not item:
            continue
        if item.upper() in {"FAULT", "NAN", "INVALID"}:
            values.append("FAULT")
        else:
            values.append(parse_int(item))
    while len(values) < expected:
        values.append(None)
    return values[:expected]


def fmt_mv(value):
    if value is None:
        return "--"
    return f"{value / 1000.0:.3f} V"


def fmt_ma(value):
    if value is None:
        return "--"
    return f"{value / 1000.0:.3f} A"


def fmt_dc(value):
    if value is None:
        return "--"
    if value == "FAULT":
        return "FAULT"
    return f"{value / 10.0:.1f} C"


def decode_bits(value, bit_names):
    names = [name for bit, name in bit_names.items() if value & bit]
    return ", ".join(names) if names else "None"


class SerialReader(threading.Thread):
    def __init__(self, port, baud, out_queue, stop_event):
        super().__init__(daemon=True)
        self.port = port
        self.baud = baud
        self.out_queue = out_queue
        self.stop_event = stop_event
        self.ser = None

    def run(self):
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=0.2)
            time.sleep(1.5)
            self.out_queue.put(("info", f"Connected to {self.port} @ {self.baud}"))
        except Exception as exc:
            self.out_queue.put(("error", f"Could not open serial port: {exc}"))
            return

        while not self.stop_event.is_set():
            try:
                line = self.ser.readline().decode("utf-8", errors="replace").strip()
                if line:
                    self.out_queue.put(("line", line))
            except Exception as exc:
                self.out_queue.put(("error", f"Serial read error: {exc}"))
                break

        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        except Exception:
            pass

    def send_command(self, command):
        if self.ser and self.ser.is_open:
            self.ser.write((command.strip() + "\n").encode("utf-8"))


class FirmwareDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("Drone BMS Firmware Dashboard")
        self.root.geometry("1220x820")

        self.q = queue.Queue()
        self.stop_event = threading.Event()
        self.reader = None
        self.raw_paused = tk.BooleanVar(value=False)

        self.vars = {}
        self.cell_vars = [tk.StringVar(value="--") for _ in range(6)]
        self.temp_vars = [tk.StringVar(value="--") for _ in range(4)]
        self.cell_adc_vars = [tk.StringVar(value="--") for _ in range(6)]
        self.temp_adc_vars = [tk.StringVar(value="--") for _ in range(4)]

        for key in [
            "connection", "mode", "uptime", "tick", "pack_v", "current_a",
            "fault_primary", "fault_name", "severity", "warn_hex",
            "fault_hex", "latched_hex", "events", "warnings", "faults",
            "current_adc", "acq_valid", "acq_stuck", "cell_valid",
            "tap_valid", "temp_valid", "current_valid",
            "validation_reasons", "sleep_decision", "sleep_reason",
            "sleep_allowed", "sleep_threshold", "last_command",
            "last_response", "latest_line",
        ]:
            self.vars[key] = tk.StringVar(value="--")
        self.vars["connection"].set("Disconnected")
        self.vars["latest_line"].set("Waiting for serial data...")

        self._build_ui()
        self._refresh_ports()
        self._open_log()
        self._poll_queue()

    def _build_ui(self):
        root = self.root
        top = ttk.Frame(root, padding=10)
        top.pack(fill="x")

        ttk.Label(top, text="Serial Port").pack(side="left")
        self.port_combo = ttk.Combobox(top, width=38, state="readonly")
        self.port_combo.pack(side="left", padx=8)
        ttk.Button(top, text="Refresh", command=self._refresh_ports).pack(side="left", padx=3)
        ttk.Button(top, text="Connect", command=self._connect).pack(side="left", padx=3)
        ttk.Button(top, text="Disconnect", command=self._disconnect).pack(side="left", padx=3)
        ttk.Checkbutton(top, text="Pause raw", variable=self.raw_paused).pack(side="left", padx=14)
        ttk.Label(top, textvariable=self.vars["connection"]).pack(side="right")

        commands = ttk.Frame(root, padding=(10, 0, 10, 8))
        commands.pack(fill="x")
        for label, command in [
            ("Help", "HELP"),
            ("Snapshot", "GET,SNAPSHOT"),
            ("Voltage", "GET,VOLT"),
            ("Current", "GET,CURRENT"),
            ("Temp", "GET,TEMP"),
            ("Fault", "GET,FAULT"),
            ("Sleep", "GET,SLEEP"),
            ("Taps", "GET,TAPS"),
        ]:
            ttk.Button(commands, text=label, command=lambda c=command: self._send_command(c)).pack(side="left", padx=3)

        ttk.Label(commands, text="Command").pack(side="left", padx=(18, 4))
        self.command_entry = ttk.Entry(commands, width=28)
        self.command_entry.pack(side="left")
        self.command_entry.bind("<Return>", lambda _event: self._send_custom_command())
        ttk.Button(commands, text="Send", command=self._send_custom_command).pack(side="left", padx=4)

        main = ttk.Frame(root, padding=10)
        main.pack(fill="both", expand=True)

        summary = ttk.LabelFrame(main, text="System Summary", padding=10)
        summary.pack(fill="x")
        summary_items = [
            ("Mode", "mode"), ("Uptime", "uptime"), ("Tick", "tick"),
            ("Pack", "pack_v"), ("Current", "current_a"), ("Severity", "severity"),
            ("Primary", "fault_primary"), ("Primary name", "fault_name"),
            ("Events", "events"), ("Sleep", "sleep_decision"),
            ("Sleep reason", "sleep_reason"), ("Sleep allowed", "sleep_allowed"),
        ]
        for i, (label, key) in enumerate(summary_items):
            ttk.Label(summary, text=f"{label}:").grid(row=i // 3, column=(i % 3) * 2, sticky="e", padx=5, pady=4)
            ttk.Label(summary, textvariable=self.vars[key], width=24).grid(row=i // 3, column=(i % 3) * 2 + 1, sticky="w", padx=5, pady=4)

        panels = ttk.Frame(main)
        panels.pack(fill="x", pady=8)

        cells = ttk.LabelFrame(panels, text="Cell Voltages", padding=10)
        cells.pack(side="left", fill="both", expand=True, padx=(0, 5))
        for i in range(6):
            ttk.Label(cells, text=f"C{i + 1}:").grid(row=i, column=0, sticky="e", padx=4, pady=2)
            ttk.Label(cells, textvariable=self.cell_vars[i], width=14).grid(row=i, column=1, sticky="w", padx=4, pady=2)
            ttk.Label(cells, text="ADC:").grid(row=i, column=2, sticky="e", padx=4, pady=2)
            ttk.Label(cells, textvariable=self.cell_adc_vars[i], width=10).grid(row=i, column=3, sticky="w", padx=4, pady=2)

        temps = ttk.LabelFrame(panels, text="Temperatures", padding=10)
        temps.pack(side="left", fill="both", expand=True, padx=5)
        for i in range(4):
            ttk.Label(temps, text=f"T{i + 1}:").grid(row=i, column=0, sticky="e", padx=4, pady=2)
            ttk.Label(temps, textvariable=self.temp_vars[i], width=14).grid(row=i, column=1, sticky="w", padx=4, pady=2)
            ttk.Label(temps, text="ADC:").grid(row=i, column=2, sticky="e", padx=4, pady=2)
            ttk.Label(temps, textvariable=self.temp_adc_vars[i], width=10).grid(row=i, column=3, sticky="w", padx=4, pady=2)
        ttk.Label(temps, text="Current ADC:").grid(row=5, column=0, sticky="e", padx=4, pady=(10, 2))
        ttk.Label(temps, textvariable=self.vars["current_adc"], width=14).grid(row=5, column=1, sticky="w", padx=4, pady=(10, 2))

        faults = ttk.LabelFrame(panels, text="Warnings and Faults", padding=10)
        faults.pack(side="left", fill="both", expand=True, padx=(5, 0))
        fault_items = [
            ("Warn hex", "warn_hex"), ("Active hex", "fault_hex"),
            ("Latched hex", "latched_hex"), ("ACQ valid", "acq_valid"),
            ("ACQ stuck", "acq_stuck"), ("Cell valid", "cell_valid"),
            ("Tap valid", "tap_valid"), ("Temp valid", "temp_valid"),
            ("Current valid", "current_valid"),
            ("Validation", "validation_reasons"),
            ("Sleep threshold", "sleep_threshold"),
            ("Warnings", "warnings"), ("Active faults", "faults"),
        ]
        for i, (label, key) in enumerate(fault_items):
            ttk.Label(faults, text=f"{label}:").grid(row=i, column=0, sticky="ne", padx=4, pady=2)
            ttk.Label(faults, textvariable=self.vars[key], wraplength=260, width=34).grid(row=i, column=1, sticky="w", padx=4, pady=2)

        latest = ttk.LabelFrame(main, text="Latest Parsed Activity", padding=10)
        latest.pack(fill="x", pady=(0, 8))
        latest.columnconfigure(1, weight=1)
        for row, (label, key) in enumerate([
            ("Last command", "last_command"),
            ("Last response", "last_response"),
            ("Latest line", "latest_line"),
        ]):
            ttk.Label(latest, text=f"{label}:").grid(row=row, column=0, sticky="e", padx=4, pady=2)
            ttk.Label(latest, textvariable=self.vars[key], wraplength=1040).grid(row=row, column=1, sticky="w", padx=4, pady=2)

        raw = ttk.LabelFrame(main, text="Raw Serial Monitor", padding=10)
        raw.pack(fill="both", expand=True)
        self.raw_text = tk.Text(raw, height=12, wrap="none")
        self.raw_text.pack(fill="both", expand=True)

    def _refresh_ports(self):
        ports = list(serial.tools.list_ports.comports())
        display = [f"{p.device} - {p.description}" for p in ports]
        self.port_combo["values"] = display
        if display and not self.port_combo.get():
            self.port_combo.current(0)

    def _selected_port(self):
        selected = self.port_combo.get()
        if not selected:
            return None
        return selected.split(" - ")[0].strip()

    def _connect(self):
        port = self._selected_port()
        if not port:
            messagebox.showwarning("No port", "Select a serial port first.")
            return
        self._disconnect()
        self.stop_event.clear()
        self.reader = SerialReader(port, BAUD_RATE, self.q, self.stop_event)
        self.reader.start()
        self.vars["connection"].set("Connecting...")

    def _disconnect(self):
        self.stop_event.set()
        self.vars["connection"].set("Disconnected")

    def _send_custom_command(self):
        command = self.command_entry.get().strip()
        if command:
            self._send_command(command)
            self.command_entry.delete(0, "end")

    def _send_command(self, command):
        if self.reader:
            self.reader.send_command(command)
            self.vars["last_command"].set(command)
            self._append_raw(f">>> {command}")
        else:
            messagebox.showinfo("Not connected", "Connect to the ESP32 first.")

    def _open_log(self):
        self.log_file = open(CSV_LOG_FILE, "a", newline="", encoding="utf-8")
        self.log_writer = csv.writer(self.log_file)
        if self.log_file.tell() == 0:
            self.log_writer.writerow(["PC_TIME", "LINE"])
            self.log_file.flush()

    def _append_raw(self, line):
        if self.raw_paused.get():
            return
        self.raw_text.insert("end", line + "\n")
        self.raw_text.see("end")

    def _set_hex_faults(self, warn_hex=None, active_hex=None, latched_hex=None):
        if warn_hex is not None:
            warn_value = parse_int(warn_hex)
            self.vars["warn_hex"].set(f"0x{warn_value:08X}")
            self.vars["warnings"].set(decode_bits(warn_value, WARNING_BITS))
        if active_hex is not None:
            fault_value = parse_int(active_hex)
            self.vars["fault_hex"].set(f"0x{fault_value:08X}")
            self.vars["faults"].set(decode_bits(fault_value, FAULT_BITS))
        if latched_hex is not None:
            latched_value = parse_int(latched_hex)
            self.vars["latched_hex"].set(f"0x{latched_value:08X}")

    def _set_primary_fault(self, value):
        fault_int = parse_int(value)
        fault_hex = f"0x{fault_int:04X}"
        self.vars["fault_primary"].set(fault_hex)
        self.vars["fault_name"].set(FAULT_CODES.get(fault_hex, "Unknown"))

    def _set_validation_reason(self, *values):
        combined = 0
        for value in values:
            if value is not None:
                combined |= parse_int(value)
        self.vars["validation_reasons"].set(
            decode_bits(combined, VALIDATION_REASON_BITS)
        )

    def _handle_line(self, line):
        self.vars["latest_line"].set(line)
        self.log_writer.writerow([dt.datetime.now().isoformat(timespec="seconds"), line])
        self.log_file.flush()

        if line.startswith("BMS INIT OK"):
            payload = line.split(",", 1)[1] if "," in line else ""
            data = parse_kv_payload(payload)
            if "MODE" in data:
                self.vars["mode"].set(data["MODE"])
            return

        if line.startswith("SYS:"):
            data = parse_kv_payload(line[4:].replace(" ", ","))
            if "mode" in data:
                self.vars["mode"].set(data["mode"])
            if "uptime_ms" in data:
                self.vars["uptime"].set(f"{parse_int(data['uptime_ms'])} ms")
            return

        if line.startswith("SCHED:"):
            match = re.search(r"tick_ms=(\d+)", line)
            if match:
                self.vars["tick"].set(f"{parse_int(match.group(1))} ms")
            return

        if line.startswith("MEAS:"):
            self._parse_meas_line(line)
            return

        if line.startswith("ACQ:"):
            self._parse_acq_line(line)
            return

        if line.startswith("FAULT:"):
            data = parse_kv_payload(line[6:].replace(" ", ","))
            self._apply_fault_data(data)
            return

        if line.startswith("SLEEP:"):
            data = parse_kv_payload(line[6:].replace(" ", ","))
            self._apply_sleep_data(data)
            return

        if line.startswith("RESP,"):
            self.vars["last_response"].set(line)
            self._parse_response_line(line)

    def _parse_meas_line(self, line):
        data = parse_kv_payload(line[5:].strip().replace(" ", ","))
        if "pack_mV" in data:
            self.vars["pack_v"].set(fmt_mv(parse_int(data["pack_mV"])))
        if "current_mA" in data:
            self.vars["current_a"].set(fmt_ma(parse_int(data["current_mA"])))
        if "cell_mV" in data:
            for index, value in enumerate(parse_int_list(data["cell_mV"], 6)):
                self.cell_vars[index].set(fmt_mv(value))
        if "cell_valid" in data:
            self.vars["cell_valid"].set(f"0x{parse_int(data['cell_valid']):08X}")
        if "tap_valid" in data:
            self.vars["tap_valid"].set(f"0x{parse_int(data['tap_valid']):08X}")
        if "temp_valid" in data:
            self.vars["temp_valid"].set(f"0x{parse_int(data['temp_valid']):08X}")
        if "current_valid" in data:
            self.vars["current_valid"].set("Yes" if parse_int(data["current_valid"]) else "No")
        self._set_validation_reason(
            data.get("voltage_reason"),
            data.get("current_reason"),
            data.get("temp_reason"),
        )
        if "temp_dC" in data:
            for index, value in enumerate(parse_temp_list(data["temp_dC"], 4)):
                self.temp_vars[index].set(fmt_dc(value))

    def _parse_acq_line(self, line):
        data = parse_kv_payload(line[4:].strip().replace(" ", ","))
        if "cell" in data:
            for index, value in enumerate(parse_int_list(data["cell"], 6)):
                self.cell_adc_vars[index].set("--" if value is None else f"{value} mV")
        if "current" in data:
            self.vars["current_adc"].set(f"{parse_int(data['current'])} mV")
        if "temp" in data:
            for index, value in enumerate(parse_int_list(data["temp"], 4)):
                self.temp_adc_vars[index].set("--" if value is None else f"{value} mV")
        if "valid" in data:
            self.vars["acq_valid"].set(f"0x{parse_int(data['valid']):08X}")
        if "stuck" in data:
            self.vars["acq_stuck"].set(f"0x{parse_int(data['stuck']):08X}")

    def _apply_fault_data(self, data):
        self._set_hex_faults(
            warn_hex=data.get("warn") or data.get("WARN"),
            active_hex=data.get("active") or data.get("ACTIVE") or data.get("FAULT"),
            latched_hex=data.get("latched") or data.get("LATCHED"),
        )
        primary = data.get("primary") or data.get("PRIMARY")
        if primary is not None:
            self._set_primary_fault(primary)
        severity = data.get("severity") or data.get("SEVERITY")
        if severity is not None:
            self.vars["severity"].set(severity)
        events = data.get("events") or data.get("EVENTS")
        if events is not None:
            self.vars["events"].set(str(parse_int(events)))

    def _apply_sleep_data(self, data):
        decision = data.get("decision") or data.get("DECISION")
        if decision is not None:
            self.vars["sleep_decision"].set(decision)

        reason = data.get("reason") or data.get("REASON")
        if reason is not None:
            self.vars["sleep_reason"].set(reason)

        allowed = data.get("allowed") or data.get("ALLOWED")
        if allowed is not None:
            self.vars["sleep_allowed"].set("Yes" if parse_int(allowed) else "No")

        threshold = data.get("threshold_mA") or data.get("THRESHOLD_MA")
        if threshold is not None:
            self.vars["sleep_threshold"].set(fmt_ma(parse_int(threshold)))

    def _parse_response_line(self, line):
        parts = split_top_level(line)
        if len(parts) < 2:
            return
        kind = parts[1]
        payload = ",".join(parts[2:])
        data = parse_kv_payload(payload)

        if kind == "SNAPSHOT":
            if "MODE" in data:
                self.vars["mode"].set(data["MODE"])
            if "UPTIME_MS" in data:
                self.vars["uptime"].set(f"{parse_int(data['UPTIME_MS'])} ms")
            if "PACK_MV" in data:
                self.vars["pack_v"].set(fmt_mv(parse_int(data["PACK_MV"])))
            if "CURRENT_MA" in data:
                self.vars["current_a"].set(fmt_ma(parse_int(data["CURRENT_MA"])))
            self._apply_fault_data(data)
        elif kind == "VOLT":
            if "PACK_MV" in data:
                self.vars["pack_v"].set(fmt_mv(parse_int(data["PACK_MV"])))
            if "CELL_MV" in data:
                for index, value in enumerate(parse_int_list(data["CELL_MV"], 6)):
                    self.cell_vars[index].set(fmt_mv(value))
            if "VALID" in data:
                self.vars["cell_valid"].set(f"0x{parse_int(data['VALID']):08X}")
            if "TAP_VALID" in data:
                self.vars["tap_valid"].set(f"0x{parse_int(data['TAP_VALID']):08X}")
            self._set_validation_reason(data.get("REASON"))
        elif kind == "CURRENT":
            if "CURRENT_MA" in data:
                self.vars["current_a"].set(fmt_ma(parse_int(data["CURRENT_MA"])))
            if "ADC_MV" in data:
                self.vars["current_adc"].set(f"{parse_int(data['ADC_MV'])} mV")
            if "VALID" in data:
                self.vars["current_valid"].set("Yes" if parse_int(data["VALID"]) else "No")
            self._set_validation_reason(data.get("REASON"))
        elif kind == "TEMP":
            if "TEMP_DC" in data:
                for index, value in enumerate(parse_temp_list(data["TEMP_DC"], 4)):
                    self.temp_vars[index].set(fmt_dc(value))
            if "ADC_MV" in data:
                for index, value in enumerate(parse_int_list(data["ADC_MV"], 4)):
                    self.temp_adc_vars[index].set("--" if value is None else f"{value} mV")
            if "VALID" in data:
                self.vars["temp_valid"].set(f"0x{parse_int(data['VALID']):08X}")
            self._set_validation_reason(data.get("REASON"))
        elif kind == "FAULT":
            self._apply_fault_data(data)
            if "CELL_VALID" in data:
                self.vars["cell_valid"].set(f"0x{parse_int(data['CELL_VALID']):08X}")
            if "TAP_VALID" in data:
                self.vars["tap_valid"].set(f"0x{parse_int(data['TAP_VALID']):08X}")
            if "CURRENT_VALID" in data:
                self.vars["current_valid"].set("Yes" if parse_int(data["CURRENT_VALID"]) else "No")
            if "TEMP_VALID" in data:
                self.vars["temp_valid"].set(f"0x{parse_int(data['TEMP_VALID']):08X}")
        elif kind == "SLEEP":
            self._apply_sleep_data(data)
        elif kind == "TAPS":
            if "ADC_MV" in data:
                for index, value in enumerate(parse_int_list(data["ADC_MV"], 6)):
                    self.cell_adc_vars[index].set("--" if value is None else f"{value} mV")
            if "CELL_MV" in data:
                for index, value in enumerate(parse_int_list(data["CELL_MV"], 6)):
                    self.cell_vars[index].set(fmt_mv(value))
            if "TAP_VALID" in data:
                self.vars["tap_valid"].set(f"0x{parse_int(data['TAP_VALID']):08X}")
            if "CELL_VALID" in data:
                self.vars["cell_valid"].set(f"0x{parse_int(data['CELL_VALID']):08X}")
            self._set_validation_reason(data.get("REASON"))

    def _poll_queue(self):
        while True:
            try:
                kind, payload = self.q.get_nowait()
            except queue.Empty:
                break

            if kind == "line":
                self._append_raw(payload)
                self._handle_line(payload)
            elif kind == "info":
                self.vars["connection"].set(payload)
                self._append_raw(payload)
            elif kind == "error":
                self.vars["connection"].set("Error")
                self._append_raw(payload)

        self.root.after(100, self._poll_queue)

    def close(self):
        self._disconnect()
        try:
            self.log_file.close()
        except Exception:
            pass


if __name__ == "__main__":
    root = tk.Tk()
    app = FirmwareDashboard(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (app.close(), root.destroy()))
    root.mainloop()
