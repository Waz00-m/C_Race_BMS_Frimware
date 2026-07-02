"""MicroPython UART tester for the Drone BMS diagnostic port."""

import time

try:
    from machine import Pin, UART
except ImportError:
    Pin = None
    UART = None

import tester_config as cfg


KNOWN_FAULT_DOMAINS = {
    0x1001: ("voltage", "fault"),
    0x1002: ("voltage", "fault"),
    0x1003: ("voltage", "fault"),
    0x1004: ("voltage", "fault"),
    0x2002: ("current", "fault"),
    0x2003: ("current", "fault"),
    0x3001: ("temperature", "fault"),
    0x3003: ("temperature", "fault"),
    0x4001: ("voltage", "current", "temperature", "fault", "acq"),
    0x4002: ("voltage", "current", "temperature", "fault", "validation"),
}


class KnownFaultPolicy:
    def __init__(self):
        self.enabled = bool(cfg.KNOWN_FAULTS_ENABLED)
        self.fault_codes = set(_code_list(cfg.KNOWN_FAULT_CODES))
        self.active_codes = set()
        self.matched_codes = set()

    def update_context(self, fault_data):
        self.active_codes = _fault_codes_from_data(fault_data)
        if self.enabled:
            self.matched_codes = self.active_codes & self.fault_codes
        else:
            self.matched_codes = set()

    def allows_domain(self, domain):
        if (not self.enabled) or (not self.matched_codes):
            return False
        for code in self.matched_codes:
            domains = KNOWN_FAULT_DOMAINS.get(code, ("fault",))
            if domain in domains:
                return True
        return False

    def describe(self):
        state = "ON" if self.enabled else "OFF"
        return (
            "known exclusions %s, codes=%s, active=%s, matched=%s"
        ) % (
            state,
            _format_code_list(self.fault_codes),
            _format_code_list(self.active_codes),
            _format_code_list(self.matched_codes),
        )


def _ticks_ms():
    if hasattr(time, "ticks_ms"):
        return time.ticks_ms()
    return int(time.time() * 1000)


def _ticks_diff(end, start):
    if hasattr(time, "ticks_diff"):
        return time.ticks_diff(end, start)
    return end - start


def _sleep_ms(ms):
    if hasattr(time, "sleep_ms"):
        time.sleep_ms(ms)
    else:
        time.sleep(ms / 1000.0)


def _int_value(value):
    text = str(value).strip()
    if text.lower().startswith("0x"):
        return int(text, 16)
    return int(text)


def _as_hex(value, width=8):
    return "0x%0*X" % (width, int(value))


def _code_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        items = value
    else:
        items = []
        for part in str(value).replace(";", ",").split(","):
            items.extend(part.split())

    codes = []
    for item in items:
        text = str(item).strip()
        if text:
            codes.append(_int_value(text))
    return codes


def _response_list(value):
    if not value:
        return []
    text = str(value).strip()
    if text.startswith("["):
        text = text[1:]
    if text.endswith("]"):
        text = text[:-1]
    items = []
    for item in text.split(","):
        item = item.strip()
        if item:
            items.append(item)
    return items


def _fault_codes_from_data(data):
    codes = set()
    for item in _response_list(data.get("CODES", "")):
        codes.add(_int_value(item))
    primary = _int_value(data.get("PRIMARY", 0))
    if primary != 0:
        codes.add(primary)
    return codes


def _format_code_list(codes):
    if not codes:
        return "none"
    values = sorted(list(codes))
    return ", ".join(_as_hex(code, 4) for code in values)


def _split_csv_fields(text):
    fields = []
    part = ""
    depth = 0

    for ch in text:
        if ch == "[":
            depth += 1
        elif ch == "]" and depth > 0:
            depth -= 1

        if ch == "," and depth == 0:
            fields.append(part)
            part = ""
        else:
            part += ch

    fields.append(part)
    return fields


def parse_response(line):
    fields = _split_csv_fields(line.strip())
    if len(fields) < 2 or fields[0] != "RESP":
        return None, {}

    kind = fields[1]
    data = {}

    for field in fields[2:]:
        if "=" not in field:
            continue
        key, value = field.split("=", 1)
        data[key.strip().upper()] = value.strip()

    return kind, data


def create_uart():
    if UART is None:
        raise RuntimeError("machine.UART is available only on MicroPython.")

    kwargs = {
        "baudrate": cfg.UART_BAUD,
        "timeout": cfg.LINE_POLL_DELAY_MS,
    }

    if cfg.UART_TX_PIN is not None:
        kwargs["tx"] = Pin(cfg.UART_TX_PIN)
    if cfg.UART_RX_PIN is not None:
        kwargs["rx"] = Pin(cfg.UART_RX_PIN)

    return UART(cfg.UART_ID, **kwargs)


class BmsUartClient:
    def __init__(self, uart):
        self.uart = uart

    def _read_line(self, timeout_ms):
        start = _ticks_ms()
        while _ticks_diff(_ticks_ms(), start) < timeout_ms:
            raw = self.uart.readline()
            if raw:
                try:
                    return raw.decode("utf-8").strip()
                except Exception:
                    return str(raw).strip()
            _sleep_ms(cfg.LINE_POLL_DELAY_MS)
        return None

    def request(self, command, expected_kind=None, timeout_ms=None):
        if timeout_ms is None:
            timeout_ms = cfg.COMMAND_TIMEOUT_MS

        try:
            command = command.strip()
            self.uart.write((command + "\n").encode("utf-8"))

            start = _ticks_ms()
            while _ticks_diff(_ticks_ms(), start) < timeout_ms:
                remaining = timeout_ms - _ticks_diff(_ticks_ms(), start)
                line = self._read_line(max(remaining, cfg.LINE_POLL_DELAY_MS))
                if line is None:
                    break
                kind, data = parse_response(line)
                if kind is None:
                    continue
                if expected_kind is None or kind == expected_kind:
                    return line, kind, data
        except Exception as exc:
            print("UART request error: %s" % exc)

        return None, None, {}


class TestSummary:
    def __init__(self, policy=None):
        self.passed = 0
        self.failed = 0
        self.excluded = 0
        self.policy = policy

    def check(self, condition, label, detail="", domain="general"):
        if condition:
            self.passed += 1
            print("PASS - " + label)
        elif self.policy is not None and self.policy.allows_domain(domain):
            self.passed += 1
            self.excluded += 1
            suffix = "excluded by " + _format_code_list(
                self.policy.matched_codes)
            if detail:
                print("EXCLUDED - " + label + " (" + detail + "; " +
                      suffix + ")")
            else:
                print("EXCLUDED - " + label + " (" + suffix + ")")
        else:
            self.failed += 1
            if detail:
                print("FAIL - " + label + " (" + detail + ")")
            else:
                print("FAIL - " + label)


def _expect_response(summary, line, label):
    summary.check(line is not None, label, "no matching RESP line")
    return line is not None


def _check_hex(summary, data, key, expected, label, domain="general"):
    if key not in data:
        summary.check(False, label, "missing " + key, domain)
        return
    try:
        actual = _int_value(data[key])
        detail = "expected 0x%08X got 0x%08X" % (expected, actual)
        summary.check(actual == expected, label, detail, domain)
    except Exception as exc:
        summary.check(False, label, "parse error: %s" % exc, domain)


def _check_int(summary, data, key, expected, label, domain="general"):
    if key not in data:
        summary.check(False, label, "missing " + key, domain)
        return
    try:
        actual = _int_value(data[key])
        detail = "expected %d got %d" % (expected, actual)
        summary.check(actual == expected, label, detail, domain)
    except Exception as exc:
        summary.check(False, label, "parse error: %s" % exc, domain)


def _check_fault_codes(summary, data, policy):
    policy.update_context(data)
    allowed = policy.fault_codes if policy.enabled else set()
    unexpected = policy.active_codes - allowed
    expected = "none"
    if policy.enabled and allowed:
        expected = "none except " + _format_code_list(allowed)
    detail = "expected %s got %s" % (
        expected,
        _format_code_list(policy.active_codes),
    )
    summary.check(len(unexpected) == 0, "active fault codes", detail,
                  "fault_codes")


def test_taps(client, summary):
    print("\nGET,TAPS")
    line, _, data = client.request("GET,TAPS", "TAPS")
    if not _expect_response(summary, line, "TAPS response"):
        return
    _check_hex(summary, data, "TAP_VALID", cfg.EXPECTED_TAP_VALID_MASK,
               "tap valid bitmap", "voltage")
    _check_hex(summary, data, "CELL_VALID", cfg.EXPECTED_CELL_VALID_MASK,
               "cell valid bitmap", "voltage")
    _check_hex(summary, data, "REASON", cfg.EXPECTED_VOLTAGE_REASON,
               "voltage validation reason", "voltage")


def test_voltage(client, summary):
    print("\nGET,VOLT")
    line, _, data = client.request("GET,VOLT", "VOLT")
    if not _expect_response(summary, line, "VOLT response"):
        return
    _check_hex(summary, data, "VALID", cfg.EXPECTED_CELL_VALID_MASK,
               "voltage cell valid bitmap", "voltage")
    _check_hex(summary, data, "TAP_VALID", cfg.EXPECTED_TAP_VALID_MASK,
               "voltage tap valid bitmap", "voltage")
    _check_hex(summary, data, "REASON", cfg.EXPECTED_VOLTAGE_REASON,
               "voltage reason", "voltage")


def test_current(client, summary):
    print("\nGET,CURRENT")
    line, _, data = client.request("GET,CURRENT", "CURRENT")
    if not _expect_response(summary, line, "CURRENT response"):
        return
    _check_int(summary, data, "VALID", cfg.EXPECTED_CURRENT_VALID,
               "current valid flag", "current")
    _check_hex(summary, data, "REASON", cfg.EXPECTED_CURRENT_REASON,
               "current reason", "current")


def test_temperature(client, summary):
    print("\nGET,TEMP")
    line, _, data = client.request("GET,TEMP", "TEMP")
    if not _expect_response(summary, line, "TEMP response"):
        return
    _check_hex(summary, data, "VALID", cfg.EXPECTED_TEMP_VALID_MASK,
               "temperature valid bitmap", "temperature")
    _check_hex(summary, data, "REASON", cfg.EXPECTED_TEMP_REASON,
               "temperature reason", "temperature")


def test_fault_snapshot(client, summary, policy):
    print("\nGET,FAULT")
    line, _, data = client.request("GET,FAULT", "FAULT")
    if not _expect_response(summary, line, "FAULT response"):
        return
    _check_fault_codes(summary, data, policy)
    _check_hex(summary, data, "CELL_VALID", cfg.EXPECTED_CELL_VALID_MASK,
               "fault cell valid mirror", "voltage")
    _check_hex(summary, data, "TAP_VALID", cfg.EXPECTED_TAP_VALID_MASK,
               "fault tap valid mirror", "voltage")
    _check_int(summary, data, "CURRENT_VALID", cfg.EXPECTED_CURRENT_VALID,
               "fault current valid mirror", "current")
    _check_hex(summary, data, "TEMP_VALID", cfg.EXPECTED_TEMP_VALID_MASK,
               "fault temperature valid mirror", "temperature")


def run_suite(client, policy=None):
    if policy is None:
        policy = KnownFaultPolicy()

    print("\nDrone BMS UART tester")
    print("Expected: cells=0x%08X taps=0x%08X temp=0x%08X current=%d" % (
        cfg.EXPECTED_CELL_VALID_MASK,
        cfg.EXPECTED_TAP_VALID_MASK,
        cfg.EXPECTED_TEMP_VALID_MASK,
        cfg.EXPECTED_CURRENT_VALID,
    ))

    _, _, fault_data = client.request("GET,FAULT", "FAULT")
    policy.update_context(fault_data)
    print(policy.describe())

    summary = TestSummary(policy)
    for test in (
        test_taps,
        test_voltage,
        test_current,
    ):
        try:
            test(client, summary)
        except Exception as exc:
            summary.check(False, test.__name__, "exception: %s" % exc)

    try:
        test_temperature(client, summary)
    except Exception as exc:
        summary.check(False, test_temperature.__name__,
                      "exception: %s" % exc)

    try:
        test_fault_snapshot(client, summary, policy)
    except Exception as exc:
        summary.check(False, test_fault_snapshot.__name__,
                      "exception: %s" % exc)

    print("\nSUMMARY: %d passed, %d failed, %d excluded" % (
        summary.passed,
        summary.failed,
        summary.excluded,
    ))
    if summary.failed == 0:
        print("RESULT: PASS")
    else:
        print("RESULT: FAIL")
    return summary.failed == 0


def interactive_shell(client):
    policy = KnownFaultPolicy()
    print("\nCommands: run, known, help, or raw BMS command like GET,VOLT")
    while True:
        try:
            command = input("tester> ").strip()
        except KeyboardInterrupt:
            print("\nExiting tester shell.")
            return

        if command == "":
            continue
        if command in ("help", "h", "?"):
            print("run - execute PASS/FAIL suite")
            print("known - show known-fault exclusion state")
            print("known on/off - toggle known-fault exclusions")
            print("known code <fault_code>[,<fault_code>...]")
            print("known add <fault_code>[,<fault_code>...]")
            print("known clear - clear known-fault codes")
            print("example: known code 0x3003,0x2003")
            print("GET,TAPS / GET,VOLT / GET,CURRENT / GET,TEMP / GET,FAULT")
            continue
        if command in ("run", "r"):
            run_suite(client, policy)
            continue

        try:
            fields = command.split()
            if fields and fields[0].lower() == "known":
                handle_known_command(policy, fields[1:])
                continue

            expected = None
            upper = command.upper()
            if upper.startswith("GET,"):
                expected = upper.split(",", 1)[1]
            line, _, _ = client.request(command, expected)
            if line is None:
                print("No response")
            else:
                print(line)
        except Exception as exc:
            print("Command error: %s" % exc)


def handle_known_command(policy, args):
    if len(args) == 0:
        print(policy.describe())
        return

    action = args[0].lower()

    if action == "on":
        policy.enabled = True
        print(policy.describe())
        return

    if action == "off":
        policy.enabled = False
        print(policy.describe())
        return

    if action == "clear":
        policy.fault_codes = set()
        policy.matched_codes = set()
        print(policy.describe())
        return

    if action in ("code", "codes", "set"):
        if len(args) < 2:
            print("Usage: known code <fault_code>[,<fault_code>...]")
            return
        policy.fault_codes = set(_code_list(" ".join(args[1:])))
        print(policy.describe())
        return

    if action == "add":
        if len(args) < 2:
            print("Usage: known add <fault_code>[,<fault_code>...]")
            return
        policy.fault_codes.update(_code_list(" ".join(args[1:])))
        print(policy.describe())
        return

    print("Unknown known-fault command")
