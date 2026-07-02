#include "bms_display_hal.h"

#include <Arduino.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Wire.h>

#include "bms_board_config.h"
#include "bms_i2c_hal.h"

static const int OLED_SDA_PIN = BMS_OLED_SDA_PIN;
static const int OLED_SCL_PIN = BMS_OLED_SCL_PIN;
static const int OLED_PAGE_BUTTON_PIN = BMS_OLED_PAGE_BUTTON_PIN;

static const int OLED_SCREEN_WIDTH = BMS_OLED_SCREEN_WIDTH;
static const int OLED_SCREEN_HEIGHT = BMS_OLED_SCREEN_HEIGHT;
static const int OLED_RESET_PIN = BMS_OLED_RESET_PIN;
static const uint8_t OLED_I2C_ADDRESS = BMS_OLED_I2C_ADDRESS;

static const uint16_t OLED_CELL_DISPLAY_MAX_MV =
    BMS_OLED_CELL_DISPLAY_MAX_MV;
static const uint16_t OLED_CELL_DISPLAY_MIN_MV =
    BMS_OLED_CELL_DISPLAY_MIN_MV;
static const uint32_t OLED_BUTTON_DEBOUNCE_MS =
    BMS_OLED_BUTTON_DEBOUNCE_MS;
static const uint32_t OLED_CURRENT_NO_LOAD_THRESHOLD_MA =
    BMS_OLED_CURRENT_NO_LOAD_THRESHOLD_MA;

static Adafruit_SSD1306 g_display(
    OLED_SCREEN_WIDTH,
    OLED_SCREEN_HEIGHT,
    &Wire,
    OLED_RESET_PIN);

static bool g_display_ready = false;
static uint8_t g_oled_page = 0U;
static bool g_last_button_reading = HIGH;
static bool g_stable_button_state = HIGH;
static uint32_t g_last_button_debounce_ms = 0UL;
static bms_register_snapshot_t g_last_snapshot;

static uint16_t BMS_ESP32_Display_ClampCellMilliVolts(uint16_t value)
{
    if (value < OLED_CELL_DISPLAY_MIN_MV) {
        return OLED_CELL_DISPLAY_MIN_MV;
    }

    if (value > OLED_CELL_DISPLAY_MAX_MV) {
        return OLED_CELL_DISPLAY_MAX_MV;
    }

    return value;
}

static void BMS_ESP32_Display_PrintHeader(const char *title)
{
    g_display.setTextSize(1);
    g_display.setTextColor(SSD1306_WHITE);
    g_display.setCursor(0, 0);
    g_display.print(title);
    g_display.drawLine(0, 10, 127, 10, SSD1306_WHITE);
}

static void BMS_ESP32_Display_PrintModeBadge(
    const bms_register_snapshot_t *snapshot)
{
    if ((snapshot == NULL) ||
        (snapshot->regs.sys.system_mode != BMS_SYSTEM_MODE_DIAGNOSTIC_MODE)) {
        return;
    }

    g_display.setTextSize(1);
    g_display.setTextColor(SSD1306_WHITE);
    g_display.fillRect(74, 56, 54, 8, SSD1306_BLACK);
    g_display.setCursor(74, 56);
    g_display.print("DIAG_MODE");
}

static void BMS_ESP32_Display_PrintVoltageV(uint32_t milli_volts, uint8_t digits)
{
    g_display.print((float)milli_volts / 1000.0f, digits);
    g_display.print("V");
}

static void BMS_ESP32_Display_PrintCurrentA(uint32_t milli_amps, uint8_t digits)
{
    g_display.print((float)milli_amps / 1000.0f, digits);
    g_display.print(" A");
}

static bool BMS_ESP32_Display_TemperatureIsValid(
    const bms_register_snapshot_t *snapshot,
    uint8_t index)
{
    return (index < BMS_NUM_TEMPERATURES) &&
           ((snapshot->regs.meas.temperature_valid_bitmap & (1UL << index)) !=
            0UL);
}

static void BMS_ESP32_Display_PrintTemperatureC(
    const bms_register_snapshot_t *snapshot,
    uint8_t index)
{
    if (!BMS_ESP32_Display_TemperatureIsValid(snapshot, index)) {
        g_display.print("FAULT");
        return;
    }

    const int16_t deci_c = snapshot->regs.meas.temperature_dC[index];
    g_display.print((float)deci_c / 10.0f, 1);
    g_display.print("C");
}

static void BMS_ESP32_Display_ShowVoltagePage(
    const bms_register_snapshot_t *snapshot)
{
    uint16_t oled_cell_mV[BMS_NUM_CELLS] = {0U};
    uint32_t oled_pack_mV = 0UL;

    for (uint8_t i = 0U; i < BMS_NUM_CELLS; ++i) {
        oled_cell_mV[i] = BMS_ESP32_Display_ClampCellMilliVolts(
            snapshot->regs.meas.cell_mV[i]);
        oled_pack_mV += oled_cell_mV[i];
    }

    g_display.clearDisplay();
    BMS_ESP32_Display_PrintHeader("VOLTAGE");

    g_display.setTextSize(1);
    g_display.setCursor(0, 13);
    g_display.print("PACK:");
    BMS_ESP32_Display_PrintVoltageV(oled_pack_mV, 2);

    g_display.setCursor(0, 25);
    g_display.print("C1:");
    BMS_ESP32_Display_PrintVoltageV(oled_cell_mV[0], 2);
    g_display.print(" C2:");
    BMS_ESP32_Display_PrintVoltageV(oled_cell_mV[1], 2);

    g_display.setCursor(0, 36);
    g_display.print("C3:");
    BMS_ESP32_Display_PrintVoltageV(oled_cell_mV[2], 2);
    g_display.print(" C4:");
    BMS_ESP32_Display_PrintVoltageV(oled_cell_mV[3], 2);

    g_display.setCursor(0, 47);
    g_display.print("C5:");
    BMS_ESP32_Display_PrintVoltageV(oled_cell_mV[4], 2);
    g_display.print(" C6:");
    BMS_ESP32_Display_PrintVoltageV(oled_cell_mV[5], 2);

    g_display.setCursor(0, 58);
    g_display.print("MAX:");
    BMS_ESP32_Display_PrintVoltageV(OLED_CELL_DISPLAY_MAX_MV, 2);

    BMS_ESP32_Display_PrintModeBadge(snapshot);
    g_display.display();
}

static void BMS_ESP32_Display_ShowCurrentPage(
    const bms_register_snapshot_t *snapshot)
{
    g_display.clearDisplay();
    BMS_ESP32_Display_PrintHeader("CURRENT");

    if (snapshot->regs.meas.current_abs_mA <=
        OLED_CURRENT_NO_LOAD_THRESHOLD_MA) {
        g_display.setTextSize(2);
        g_display.setCursor(10, 24);
        g_display.print("NO LOAD");

        g_display.setTextSize(1);
        g_display.setCursor(38, 50);
        g_display.print("0.0 A");
    } else {
        g_display.setTextSize(2);
        g_display.setCursor(8, 26);
        BMS_ESP32_Display_PrintCurrentA(
            snapshot->regs.meas.current_abs_mA,
            1);
    }

    BMS_ESP32_Display_PrintModeBadge(snapshot);
    g_display.display();
}

static void BMS_ESP32_Display_ShowTemperaturePage(
    const bms_register_snapshot_t *snapshot)
{
    g_display.clearDisplay();
    BMS_ESP32_Display_PrintHeader("TEMPERATURE");

    g_display.setTextSize(1);
    g_display.setCursor(0, 18);
    g_display.print("T1:");
    BMS_ESP32_Display_PrintTemperatureC(snapshot, 0U);

    g_display.setCursor(68, 18);
    g_display.print("T2:");
    BMS_ESP32_Display_PrintTemperatureC(snapshot, 1U);

    g_display.setCursor(0, 38);
    g_display.print("T3:");
    BMS_ESP32_Display_PrintTemperatureC(snapshot, 2U);

    g_display.setCursor(68, 38);
    g_display.print("T4:");
    BMS_ESP32_Display_PrintTemperatureC(snapshot, 3U);

    BMS_ESP32_Display_PrintModeBadge(snapshot);
    g_display.display();
}

static void BMS_ESP32_Display_Render(const bms_register_snapshot_t *snapshot)
{
    if (!g_display_ready || (snapshot == NULL)) {
        return;
    }

    switch (g_oled_page) {
    case 0U:
        BMS_ESP32_Display_ShowVoltagePage(snapshot);
        break;
    case 1U:
        BMS_ESP32_Display_ShowCurrentPage(snapshot);
        break;
    case 2U:
        BMS_ESP32_Display_ShowTemperaturePage(snapshot);
        break;
    default:
        g_oled_page = 0U;
        BMS_ESP32_Display_ShowVoltagePage(snapshot);
        break;
    }
}

bms_status_t BMS_HAL_Display_Init(void)
{
    const bms_status_t i2c_status = BMS_HAL_I2C_Init();
    if (i2c_status != BMS_STATUS_OK) {
        return i2c_status;
    }

    pinMode(OLED_PAGE_BUTTON_PIN, INPUT_PULLUP);

    g_display_ready = g_display.begin(
        SSD1306_SWITCHCAPVCC,
        OLED_I2C_ADDRESS);

    if (!g_display_ready) {
        return BMS_STATUS_HAL_ERROR;
    }

    g_display.clearDisplay();
    g_display.setTextSize(1);
    g_display.setTextColor(SSD1306_WHITE);
    g_display.setCursor(0, 0);
    g_display.println("P0 BMS READY");
    g_display.println("HW Timer Mode");
    g_display.println("Portable Core");
    g_display.println("OLED Adapter");
    g_display.display();

    return BMS_STATUS_OK;
}

bms_status_t BMS_HAL_Display_PollInput(void)
{
    if (!g_display_ready) {
        return BMS_STATUS_OK;
    }

    const bool reading = digitalRead(OLED_PAGE_BUTTON_PIN);
    const uint32_t now_ms = millis();

    if (reading != g_last_button_reading) {
        g_last_button_debounce_ms = now_ms;
        g_last_button_reading = reading;
    }

    if ((now_ms - g_last_button_debounce_ms) > OLED_BUTTON_DEBOUNCE_MS) {
        if (reading != g_stable_button_state) {
            g_stable_button_state = reading;

            if (g_stable_button_state == LOW) {
                g_oled_page++;
                if (g_oled_page > 2U) {
                    g_oled_page = 0U;
                }

                BMS_ESP32_Display_Render(&g_last_snapshot);
            }
        }
    }

    return BMS_STATUS_OK;
}

bms_status_t BMS_HAL_Display_Update(const bms_register_snapshot_t *snapshot)
{
    if (snapshot == NULL) {
        return BMS_STATUS_INVALID_ARGUMENT;
    }

    if (!g_display_ready) {
        return BMS_STATUS_OK;
    }

    g_last_snapshot = *snapshot;
    BMS_ESP32_Display_Render(snapshot);

    return BMS_STATUS_OK;
}
