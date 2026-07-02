"""Boot entry for the Drone BMS MicroPython UART tester."""

import time

import tester_config as cfg
from bms_uart_tester import BmsUartClient, create_uart, interactive_shell, run_suite


def _sleep_ms(ms):
    if hasattr(time, "sleep_ms"):
        time.sleep_ms(ms)
    else:
        time.sleep(ms / 1000.0)


def main():
    print("Drone BMS MicroPython UART tester starting")
    print("UART%d @ %d baud" % (cfg.UART_ID, cfg.UART_BAUD))
    _sleep_ms(cfg.BOOT_SETTLE_MS)

    uart = create_uart()
    client = BmsUartClient(uart)

    run_suite(client)
    interactive_shell(client)


main()

