"""PC UART tester for the Drone BMS diagnostic port."""

import argparse
import sys
import time

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    serial = None
    list_ports = None


DEFAULT_BAUD = 115200
DEFAULT_TIMEOUT_S = 1.8
LINE_TIMEOUT_S = 0.05

EXPECTED_CELL_VALID_MASK = 0x0000003F
EXPECTED_TAP_VALID_MASK = 0x0000003F
EXPECTED_VOLTAGE_REASON = 0x00000000
EXPECTED_CURRENT_VALID = 1
EXPECTED_CURRENT_REASON = 0x00000000
EXPECTED_TEMP_VALID_MASK = 0x0000000F
EXPECTED_TEMP_REASON = 0x00000000

KNOWN_FAULT_DOMAINS = {
    0x1001: {"voltage", "fault"},
    0x1002: {"voltage", "fault"},
    0x1003: {"voltage", "fault"},
    0x1004: {"voltage", "fault"},
    0x2002: {"current", "fault"},
    0x2003: {"current", "fault"},
    0x3001: {"temperature", "fault"},
    0x3003: {"temperature", "fault"},
    0x4001: {"voltage", "current", "temperature", "fault", "acq"},
    0x4002: {"voltage", "current", "temperature", "fault", "validation"},
}


def parse_int(value):
    text = str(value).strip()
    if text.lower().startswith("0x"):
        return int(text, 16)
    return int(text)


def as_hex(value, width=8):
    return "0x%0*X" % (width, int(value))


def parse_code_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        items = value
    else:
        items = []
        for part in str(value).replace(";", ",").split(","):
            items.extend(part.split())
    codes = []
    for item in items:
        text = str(item).strip()
        if text:
            codes.append(parse_int(text))
    return codes


def parse_response_list(value):
    if not value:
        return []
    text = str(value).strip()
    if text.startswith("["):
        text = text[1:]
    if text.endswith("]"):
        text = text[:-1]
    return [item.strip() for item in text.split(",") if item.strip()]


def fault_codes_from_data(data):
    codes = set(parse_int(item) for item in parse_response_list(data.get("CODES", "")))
    primary = parse_int(data.get("PRIMARY", 0))
    if primary != 0:
        codes.add(primary)
    return codes


def format_code_list(codes):
    if not codes:
        return "none"
    return ", ".join(as_hex(code, 4) for code in sorted(codes))


def split_csv_fields(text):
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
    fields = split_csv_fields(line.strip())
    if len(fields) < 2 or fields[0] != "RESP":
        return None, {}

    kind = fields[1].strip().upper()
    data = {}

    for field in fields[2:]:
        if "=" not in field:
            continue
        key, value = field.split("=", 1)
        data[key.strip().upper()] = value.strip()

    return kind, data


class KnownFaultPolicy:
    def __init__(self, enabled=False, fault_codes=None):
        self.enabled = enabled
        self.fault_codes = set(fault_codes or [])
        self.active_codes = set()
        self.matched_codes = set()

    def update_context(self, fault_data):
        self.active_codes = fault_codes_from_data(fault_data)
        self.matched_codes = (
            self.active_codes & self.fault_codes if self.enabled else set()
        )

    def allows_domain(self, domain):
        if not self.enabled or not self.matched_codes:
            return False
        for code in self.matched_codes:
            if domain in KNOWN_FAULT_DOMAINS.get(code, {"fault"}):
                return True
        return False

    def describe(self):
        state = "ON" if self.enabled else "OFF"
        return (
            "known exclusions %s, codes=%s, active=%s, matched=%s"
            % (
                state,
                format_code_list(self.fault_codes),
                format_code_list(self.active_codes),
                format_code_list(self.matched_codes),
            )
        )


class BmsSerialClient:
    def __init__(self, port, baud, command_timeout_s, show_raw=False):
        self.show_raw = show_raw
        self.command_timeout_s = command_timeout_s
        self.serial = serial.Serial(
            port=port,
            baudrate=baud,
            timeout=LINE_TIMEOUT_S,
            write_timeout=1.0,
        )

    def close(self):
        self.serial.close()

    def drain(self, duration_s=0.2):
        end = time.monotonic() + duration_s
        while time.monotonic() < end:
            self.serial.readline()

    def request(self, command, expected_kind=None, timeout_s=None):
        if timeout_s is None:
            timeout_s = self.command_timeout_s

        try:
            command = command.strip()
            expected = expected_kind.upper() if expected_kind else None
            self.serial.write((command + "\n").encode("utf-8"))
            self.serial.flush()

            end = time.monotonic() + timeout_s
            while time.monotonic() < end:
                raw = self.serial.readline()
                if not raw:
                    continue

                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                if self.show_raw:
                    print("RAW:", line)

                kind, data = parse_response(line)
                if kind is None:
                    continue
                if expected is None or kind == expected:
                    return line, kind, data
        except Exception as exc:
            print("UART request error:", exc)

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
            print("PASS -", label)
        elif self.policy is not None and self.policy.allows_domain(domain):
            self.passed += 1
            self.excluded += 1
            suffix = "; excluded by " + format_code_list(self.policy.matched_codes)
            if detail:
                print("EXCLUDED - %s (%s%s)" % (label, detail, suffix))
            else:
                print("EXCLUDED - %s (%s)" % (label, suffix.lstrip("; ")))
        else:
            self.failed += 1
            if detail:
                print("FAIL - %s (%s)" % (label, detail))
            else:
                print("FAIL -", label)


def expect_response(summary, line, label):
    summary.check(line is not None, label, "no matching RESP line")
    return line is not None


def check_hex(summary, data, key, expected, label, domain="general"):
    if key not in data:
        summary.check(False, label, "missing " + key, domain)
        return
    try:
        actual = parse_int(data[key])
        detail = "expected 0x%08X got 0x%08X" % (expected, actual)
        summary.check(actual == expected, label, detail, domain)
    except Exception as exc:
        summary.check(False, label, "parse error: " + str(exc), domain)


def check_int(summary, data, key, expected, label, domain="general"):
    if key not in data:
        summary.check(False, label, "missing " + key, domain)
        return
    try:
        actual = parse_int(data[key])
        detail = "expected %d got %d" % (expected, actual)
        summary.check(actual == expected, label, detail, domain)
    except Exception as exc:
        summary.check(False, label, "parse error: " + str(exc), domain)


def check_fault_codes(summary, data, policy):
    policy.update_context(data)
    allowed = policy.fault_codes if policy.enabled else set()
    unexpected = policy.active_codes - allowed
    expected = "none"
    if policy.enabled and allowed:
        expected = "none except " + format_code_list(allowed)
    detail = "expected %s got %s" % (expected, format_code_list(policy.active_codes))
    summary.check(len(unexpected) == 0, "active fault codes", detail, "fault_codes")


def test_taps(client, summary):
    print("\nGET,TAPS")
    line, _, data = client.request("GET,TAPS", "TAPS")
    if not expect_response(summary, line, "TAPS response"):
        return
    check_hex(summary, data, "TAP_VALID", EXPECTED_TAP_VALID_MASK,
              "tap valid bitmap", "voltage")
    check_hex(summary, data, "CELL_VALID", EXPECTED_CELL_VALID_MASK,
              "cell valid bitmap", "voltage")
    check_hex(summary, data, "REASON", EXPECTED_VOLTAGE_REASON,
              "voltage validation reason", "voltage")


def test_voltage(client, summary):
    print("\nGET,VOLT")
    line, _, data = client.request("GET,VOLT", "VOLT")
    if not expect_response(summary, line, "VOLT response"):
        return
    check_hex(summary, data, "VALID", EXPECTED_CELL_VALID_MASK,
              "voltage cell valid bitmap", "voltage")
    check_hex(summary, data, "TAP_VALID", EXPECTED_TAP_VALID_MASK,
              "voltage tap valid bitmap", "voltage")
    check_hex(summary, data, "REASON", EXPECTED_VOLTAGE_REASON,
              "voltage reason", "voltage")


def test_current(client, summary):
    print("\nGET,CURRENT")
    line, _, data = client.request("GET,CURRENT", "CURRENT")
    if not expect_response(summary, line, "CURRENT response"):
        return
    check_int(summary, data, "VALID", EXPECTED_CURRENT_VALID,
              "current valid flag", "current")
    check_hex(summary, data, "REASON", EXPECTED_CURRENT_REASON,
              "current reason", "current")


def test_temperature(client, summary):
    print("\nGET,TEMP")
    line, _, data = client.request("GET,TEMP", "TEMP")
    if not expect_response(summary, line, "TEMP response"):
        return
    check_hex(summary, data, "VALID", EXPECTED_TEMP_VALID_MASK,
              "temperature valid bitmap", "temperature")
    check_hex(summary, data, "REASON", EXPECTED_TEMP_REASON,
              "temperature reason", "temperature")


def test_fault(client, summary, policy):
    print("\nGET,FAULT")
    line, _, data = client.request("GET,FAULT", "FAULT")
    if not expect_response(summary, line, "FAULT response"):
        return
    check_fault_codes(summary, data, policy)
    check_hex(summary, data, "CELL_VALID", EXPECTED_CELL_VALID_MASK,
              "fault cell valid mirror", "voltage")
    check_hex(summary, data, "TAP_VALID", EXPECTED_TAP_VALID_MASK,
              "fault tap valid mirror", "voltage")
    check_int(summary, data, "CURRENT_VALID", EXPECTED_CURRENT_VALID,
              "fault current valid mirror", "current")
    check_hex(summary, data, "TEMP_VALID", EXPECTED_TEMP_VALID_MASK,
              "fault temperature valid mirror", "temperature")


def run_suite(client, policy):
    print("\nDrone BMS PC UART tester")
    print(
        "Expected: cells=0x%08X taps=0x%08X temp=0x%08X current=%d"
        % (
            EXPECTED_CELL_VALID_MASK,
            EXPECTED_TAP_VALID_MASK,
            EXPECTED_TEMP_VALID_MASK,
            EXPECTED_CURRENT_VALID,
        )
    )

    _, _, fault_data = client.request("GET,FAULT", "FAULT")
    policy.update_context(fault_data)
    print(policy.describe())

    summary = TestSummary(policy)
    for test in (test_taps, test_voltage, test_current):
        try:
            test(client, summary)
        except Exception as exc:
            summary.check(False, test.__name__, "exception: " + str(exc))

    try:
        test_temperature(client, summary)
    except Exception as exc:
        summary.check(False, test_temperature.__name__, "exception: " + str(exc))

    for test in (test_fault,):
        try:
            test(client, summary, policy)
        except Exception as exc:
            summary.check(False, test.__name__, "exception: " + str(exc))

    print(
        "\nSUMMARY: %d passed, %d failed, %d excluded" %
        (summary.passed, summary.failed, summary.excluded)
    )
    print("RESULT:", "PASS" if summary.failed == 0 else "FAIL")
    return summary.failed == 0


def handle_known_command(policy, args):
    if len(args) == 0:
        print(policy.describe())
        return

    action = args[0].lower()
    if action == "on":
        policy.enabled = True
    elif action == "off":
        policy.enabled = False
    elif action == "clear":
        policy.fault_codes = set()
        policy.matched_codes = set()
    elif action in ("code", "codes", "set"):
        if len(args) < 2:
            print("Usage: known code <fault_code>[,<fault_code>...]")
            return
        policy.fault_codes = set(parse_code_list(" ".join(args[1:])))
    elif action == "add":
        if len(args) < 2:
            print("Usage: known add <fault_code>[,<fault_code>...]")
            return
        policy.fault_codes.update(parse_code_list(" ".join(args[1:])))
    else:
        print("Unknown known-fault command")
        return

    print(policy.describe())


def interactive_shell(client, policy):
    print("\nCommands: run, known, help, quit, or raw BMS command like GET,VOLT")
    while True:
        try:
            command = input("tester> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting tester shell.")
            return

        if command == "":
            continue
        if command.lower() in ("quit", "exit", "q"):
            return
        if command.lower() in ("help", "h", "?"):
            print("run - execute PASS/FAIL suite")
            print("known - show known-fault exclusion state")
            print("known on/off - toggle known-fault exclusions")
            print("known clear - clear known-fault codes")
            print("known code <fault_code>[,<fault_code>...]")
            print("known add <fault_code>[,<fault_code>...]")
            print("example: known code 0x3003,0x2003")
            print("GET,TAPS / GET,VOLT / GET,CURRENT / GET,TEMP / GET,FAULT")
            print("GET,INJECT / DIAG,ADC,SET,CELL,1,2600 / DIAG,ADC,ON")
            continue
        if command.lower() in ("run", "r"):
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
            print("Command error:", exc)


def print_ports():
    if list_ports is None:
        return
    ports = list(list_ports.comports())
    if not ports:
        print("No serial ports found.")
        return
    print("Available serial ports:")
    for item in ports:
        print("  %s - %s" % (item.device, item.description))


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="PC UART PASS/FAIL tester for Drone BMS diagnostics."
    )
    parser.add_argument("--port", help="Serial port, for example COM3.")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S)
    parser.add_argument("--once", action="store_true",
                        help="Run once and exit instead of opening shell.")
    parser.add_argument("--show-raw", action="store_true",
                        help="Print all received serial lines.")
    parser.add_argument("--known-on", action="store_true",
                        help="Enable known-fault exclusions at startup.")
    parser.add_argument("--known-fault-codes", default="",
                        help="Comma-separated known fault codes, e.g. 0x3003,0x2003.")
    parser.add_argument("--list-ports", action="store_true")
    return parser


def main(argv=None):
    if serial is None:
        print("Missing dependency: pyserial")
        print("Install with: python -m pip install pyserial")
        return 2

    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.list_ports:
        print_ports()
        return 0

    if not args.port:
        print("No --port provided.")
        print_ports()
        return 2

    policy = KnownFaultPolicy(
        enabled=args.known_on,
        fault_codes=parse_code_list(args.known_fault_codes),
    )

    client = None
    try:
        client = BmsSerialClient(
            args.port,
            args.baud,
            args.timeout,
            args.show_raw,
        )
        client.drain()
        if args.once:
            return 0 if run_suite(client, policy) else 1
        run_suite(client, policy)
        interactive_shell(client, policy)
        return 0
    except serial.SerialException as exc:
        print("Serial error:", exc)
        return 2
    except Exception as exc:
        print("Tester error:", exc)
        return 2
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    sys.exit(main())
