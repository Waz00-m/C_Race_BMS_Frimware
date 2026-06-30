#include "bms_diagnostic.h"

#include <stdio.h>
#include <string.h>

#include "bms_adc_hal.h"
#include "bms_register_snapshot.h"
#include "bms_register_strings.h"
#include "bms_uart_hal.h"

static void BMS_Diagnostic_SendLine(const char *line)
{
    BMS_HAL_UART_Send(line);
    BMS_HAL_UART_Send("\r\n");
}

static bool BMS_Diagnostic_TemperatureIsValid(
    const bms_meas_reg_t *meas,
    uint8_t index)
{
    return (index < BMS_NUM_TEMPERATURES) &&
           ((meas->temperature_valid_bitmap & (1UL << index)) != 0UL);
}

static void BMS_Diagnostic_FormatTemperature(
    const bms_meas_reg_t *meas,
    uint8_t index,
    char *text,
    size_t text_size)
{
    if ((text == NULL) || (text_size == 0U)) {
        return;
    }

    if (!BMS_Diagnostic_TemperatureIsValid(meas, index)) {
        (void)snprintf(text, text_size, "FAULT");
        return;
    }

    (void)snprintf(
        text,
        text_size,
        "%d",
        (int)meas->temperature_dC[index]);
}

static void BMS_Diagnostic_UppercaseInPlace(char *text)
{
    for (uint8_t i = 0U; text[i] != '\0'; ++i) {
        if ((text[i] >= 'a') && (text[i] <= 'z')) {
            text[i] = (char)(text[i] - 'a' + 'A');
        }
    }
}

static void BMS_Diagnostic_Normalize(char *command)
{
    if (command == NULL) {
        return;
    }

    char *read = command;
    char *write = command;

    while ((*read == ' ') || (*read == '\t') || (*read == '$')) {
        read++;
    }

    while (*read != '\0') {
        char c = *read++;
        if (c == ',') {
            c = ' ';
        }

        if ((c == ' ') || (c == '\t')) {
            if ((write != command) && (write[-1] != ' ')) {
                *write++ = ' ';
            }
        } else {
            *write++ = c;
        }
    }

    if ((write != command) && (write[-1] == ' ')) {
        write--;
    }

    *write = '\0';
    BMS_Diagnostic_UppercaseInPlace(command);
}

static const char *BMS_Diagnostic_PayloadAfterBmsPrefix(const char *command)
{
    if (strncmp(command, "BMS ", 4U) == 0) {
        return &command[4U];
    }

    return command;
}

static void BMS_Diagnostic_SendHelp(void)
{
    BMS_Diagnostic_SendLine(
        "RESP,HELP,CMDS=HELP|GET,SNAPSHOT|GET,VOLT|GET,CURRENT|GET,TEMP|GET,FAULT|GET,SLEEP|GET,TAPS");
}

static void BMS_Diagnostic_SendSnapshot(const bms_register_snapshot_t *snapshot)
{
    char line[224];
    const bms_register_map_t *regs = &snapshot->regs;

    (void)snprintf(
        line,
        sizeof(line),
        "RESP,SNAPSHOT,MODE=%s,UPTIME_MS=%lu,PACK_MV=%lu,CURRENT_MA=%ld,WARN=0x%08lX,FAULT=0x%08lX,PRIMARY=0x%04X,SEVERITY=%s",
        BMS_SystemMode_ToString(regs->sys.system_mode),
        (unsigned long)regs->sys.uptime_ms,
        (unsigned long)regs->meas.pack_mV,
        (long)regs->meas.current_mA,
        (unsigned long)regs->fault.warning_bitmap,
        (unsigned long)regs->fault.active_fault_bitmap,
        (unsigned)regs->fault.primary_fault_code,
        BMS_FaultSeverity_ToString(regs->fault.fault_severity));
    BMS_Diagnostic_SendLine(line);
}

static void BMS_Diagnostic_SendVoltage(const bms_register_snapshot_t *snapshot)
{
    char line[192];
    const bms_meas_reg_t *meas = &snapshot->regs.meas;

    (void)snprintf(
        line,
        sizeof(line),
        "RESP,VOLT,PACK_MV=%lu,CELL_MV=[%u,%u,%u,%u,%u,%u],MIN=%u,MAX=%u,DELTA_MV=%u",
        (unsigned long)meas->pack_mV,
        (unsigned)meas->cell_mV[0],
        (unsigned)meas->cell_mV[1],
        (unsigned)meas->cell_mV[2],
        (unsigned)meas->cell_mV[3],
        (unsigned)meas->cell_mV[4],
        (unsigned)meas->cell_mV[5],
        (unsigned)meas->min_cell_index,
        (unsigned)meas->max_cell_index,
        (unsigned)meas->cell_delta_mV);
    BMS_Diagnostic_SendLine(line);
}

static void BMS_Diagnostic_SendCurrent(const bms_register_snapshot_t *snapshot)
{
    char line[144];
    const bms_meas_reg_t *meas = &snapshot->regs.meas;

    (void)snprintf(
        line,
        sizeof(line),
        "RESP,CURRENT,CURRENT_MA=%ld,CURRENT_ABS_MA=%lu,ADC_MV=%u,VALID=%u",
        (long)meas->current_mA,
        (unsigned long)meas->current_abs_mA,
        (unsigned)snapshot->regs.acq.adc_mV[BMS_ADC_CHANNEL_CURRENT],
        (unsigned)meas->current_valid);
    BMS_Diagnostic_SendLine(line);
}

static void BMS_Diagnostic_SendTemp(const bms_register_snapshot_t *snapshot)
{
    char line[176];
    const bms_meas_reg_t *meas = &snapshot->regs.meas;
    char temp0[12];
    char temp1[12];
    char temp2[12];
    char temp3[12];

    BMS_Diagnostic_FormatTemperature(meas, 0U, temp0, sizeof(temp0));
    BMS_Diagnostic_FormatTemperature(meas, 1U, temp1, sizeof(temp1));
    BMS_Diagnostic_FormatTemperature(meas, 2U, temp2, sizeof(temp2));
    BMS_Diagnostic_FormatTemperature(meas, 3U, temp3, sizeof(temp3));

    (void)snprintf(
        line,
        sizeof(line),
        "RESP,TEMP,TEMP_DC=[%s,%s,%s,%s],ADC_MV=[%u,%u,%u,%u],VALID=0x%08lX",
        temp0,
        temp1,
        temp2,
        temp3,
        (unsigned)snapshot->regs.acq.adc_mV[BMS_ADC_CHANNEL_TEMP_1],
        (unsigned)snapshot->regs.acq.adc_mV[BMS_ADC_CHANNEL_TEMP_2],
        (unsigned)snapshot->regs.acq.adc_mV[BMS_ADC_CHANNEL_TEMP_3],
        (unsigned)snapshot->regs.acq.adc_mV[BMS_ADC_CHANNEL_TEMP_4],
        (unsigned long)meas->temperature_valid_bitmap);
    BMS_Diagnostic_SendLine(line);
}

static void BMS_Diagnostic_SendFault(const bms_register_snapshot_t *snapshot)
{
    char line[192];
    const bms_fault_reg_t *fault = &snapshot->regs.fault;

    (void)snprintf(
        line,
        sizeof(line),
        "RESP,FAULT,WARN=0x%08lX,ACTIVE=0x%08lX,LATCHED=0x%08lX,PRIMARY=0x%04X,SEVERITY=%s,EVENTS=%lu",
        (unsigned long)fault->warning_bitmap,
        (unsigned long)fault->active_fault_bitmap,
        (unsigned long)fault->latched_fault_bitmap,
        (unsigned)fault->primary_fault_code,
        BMS_FaultSeverity_ToString(fault->fault_severity),
        (unsigned long)fault->event_counter);
    BMS_Diagnostic_SendLine(line);
}

static void BMS_Diagnostic_SendSleep(const bms_register_snapshot_t *snapshot)
{
    char line[192];
    const bms_register_map_t *regs = &snapshot->regs;

    (void)snprintf(
        line,
        sizeof(line),
        "RESP,SLEEP,DECISION=%s,REASON=%s,ALLOWED=%u,LOAD_MA=%lu,THRESHOLD_MA=%lu,FAULT=0x%08lX,EVALS=%lu",
        BMS_SleepDecision_ToString(regs->sleep.decision),
        BMS_SleepReason_ToString(regs->sleep.reason),
        (unsigned)regs->sleep.sleep_allowed,
        (unsigned long)regs->meas.current_abs_mA,
        (unsigned long)regs->sleep.load_active_threshold_mA,
        (unsigned long)regs->fault.active_fault_bitmap,
        (unsigned long)regs->sleep.evaluated_count);
    BMS_Diagnostic_SendLine(line);
}

static void BMS_Diagnostic_SendTaps(const bms_register_snapshot_t *snapshot)
{
    char line[256];
    const bms_register_map_t *regs = &snapshot->regs;

    (void)snprintf(
        line,
        sizeof(line),
        "RESP,TAPS,ADC_MV=[%u,%u,%u,%u,%u,%u],TAP_MV=[%lu,%lu,%lu,%lu,%lu,%lu],CELL_MV=[%u,%u,%u,%u,%u,%u]",
        (unsigned)regs->acq.adc_mV[BMS_ADC_CHANNEL_CELL_1],
        (unsigned)regs->acq.adc_mV[BMS_ADC_CHANNEL_CELL_2],
        (unsigned)regs->acq.adc_mV[BMS_ADC_CHANNEL_CELL_3],
        (unsigned)regs->acq.adc_mV[BMS_ADC_CHANNEL_CELL_4],
        (unsigned)regs->acq.adc_mV[BMS_ADC_CHANNEL_CELL_5],
        (unsigned)regs->acq.adc_mV[BMS_ADC_CHANNEL_CELL_6],
        (unsigned long)regs->meas.tap_mV[0],
        (unsigned long)regs->meas.tap_mV[1],
        (unsigned long)regs->meas.tap_mV[2],
        (unsigned long)regs->meas.tap_mV[3],
        (unsigned long)regs->meas.tap_mV[4],
        (unsigned long)regs->meas.tap_mV[5],
        (unsigned)regs->meas.cell_mV[0],
        (unsigned)regs->meas.cell_mV[1],
        (unsigned)regs->meas.cell_mV[2],
        (unsigned)regs->meas.cell_mV[3],
        (unsigned)regs->meas.cell_mV[4],
        (unsigned)regs->meas.cell_mV[5]);
    BMS_Diagnostic_SendLine(line);
}

static bms_diag_command_id_t BMS_Diagnostic_Classify(const char *payload)
{
    if (strcmp(payload, "HELP") == 0) {
        return BMS_DIAG_COMMAND_HELP;
    }

    if (strcmp(payload, "GET SNAPSHOT") == 0) {
        return BMS_DIAG_COMMAND_GET_SNAPSHOT;
    }

    if (strcmp(payload, "GET VOLT") == 0) {
        return BMS_DIAG_COMMAND_GET_VOLT;
    }

    if (strcmp(payload, "GET CURRENT") == 0) {
        return BMS_DIAG_COMMAND_GET_CURRENT;
    }

    if (strcmp(payload, "GET TEMP") == 0) {
        return BMS_DIAG_COMMAND_GET_TEMP;
    }

    if (strcmp(payload, "GET FAULT") == 0) {
        return BMS_DIAG_COMMAND_GET_FAULT;
    }

    if (strcmp(payload, "GET SLEEP") == 0) {
        return BMS_DIAG_COMMAND_GET_SLEEP;
    }

    if (strcmp(payload, "GET TAPS") == 0) {
        return BMS_DIAG_COMMAND_GET_TAPS;
    }

    return BMS_DIAG_COMMAND_NONE;
}

static void BMS_Diagnostic_ExecuteCommand(
    bms_diagnostic_t *diag,
    bms_context_t *ctx,
    char *command)
{
    BMS_Diagnostic_Normalize(command);
    const char *payload = BMS_Diagnostic_PayloadAfterBmsPrefix(command);
    const bms_diag_command_id_t command_id = BMS_Diagnostic_Classify(payload);

    ctx->regs.diag.diagnostic_active = true;
    ctx->regs.diag.command_id = (uint16_t)command_id;
    ctx->regs.diag.target_service = 0U;
    ctx->regs.diag.test_id = 0U;

    if (command_id == BMS_DIAG_COMMAND_NONE) {
        ctx->regs.diag.response_code = BMS_DIAG_RESPONSE_INVALID_COMMAND;
        BMS_Diagnostic_SendLine("RESP,ERR,INVALID_COMMAND");
        ctx->regs.diag.diagnostic_active = false;
        return;
    }

    ctx->regs.diag.response_code = BMS_DIAG_RESPONSE_OK;

    if (command_id == BMS_DIAG_COMMAND_HELP) {
        BMS_Diagnostic_SendHelp();
        ctx->regs.diag.diagnostic_active = false;
        return;
    }

    bms_register_snapshot_t snapshot;
    const bms_status_t status = BMS_RegisterSnapshot_Capture(ctx, &snapshot);
    if (status != BMS_STATUS_OK) {
        BMS_Diagnostic_SendLine("RESP,ERR,SNAPSHOT_UNAVAILABLE");
        ctx->regs.diag.response_code = BMS_DIAG_RESPONSE_INVALID_COMMAND;
        ctx->regs.diag.diagnostic_active = false;
        return;
    }

    switch (command_id) {
    case BMS_DIAG_COMMAND_GET_SNAPSHOT:
        BMS_Diagnostic_SendSnapshot(&snapshot);
        break;
    case BMS_DIAG_COMMAND_GET_VOLT:
        BMS_Diagnostic_SendVoltage(&snapshot);
        break;
    case BMS_DIAG_COMMAND_GET_CURRENT:
        BMS_Diagnostic_SendCurrent(&snapshot);
        break;
    case BMS_DIAG_COMMAND_GET_TEMP:
        BMS_Diagnostic_SendTemp(&snapshot);
        break;
    case BMS_DIAG_COMMAND_GET_FAULT:
        BMS_Diagnostic_SendFault(&snapshot);
        break;
    case BMS_DIAG_COMMAND_GET_SLEEP:
        BMS_Diagnostic_SendSleep(&snapshot);
        break;
    case BMS_DIAG_COMMAND_GET_TAPS:
        BMS_Diagnostic_SendTaps(&snapshot);
        break;
    default:
        break;
    }

    diag->command_length = 0U;
    ctx->regs.diag.diagnostic_active = false;
}

bms_status_t BMS_Diagnostic_Init(bms_diagnostic_t *diag, bms_context_t *ctx)
{
    if ((diag == NULL) || !BMS_Context_IsInitialized(ctx)) {
        return BMS_STATUS_INVALID_ARGUMENT;
    }

    memset(diag, 0, sizeof(*diag));
    diag->initialized = true;
    ctx->regs.diag.response_code = BMS_DIAG_RESPONSE_OK;

    return BMS_STATUS_OK;
}

bms_status_t BMS_Diagnostic_Poll(bms_diagnostic_t *diag, bms_context_t *ctx)
{
    if ((diag == NULL) || !diag->initialized) {
        return BMS_STATUS_NOT_INITIALIZED;
    }

    if (!BMS_Context_IsInitialized(ctx)) {
        return BMS_STATUS_NOT_INITIALIZED;
    }

    uint8_t byte = 0U;

    while (BMS_HAL_UART_ReadByte(&byte) == BMS_STATUS_OK) {
        if (byte == '\r') {
            continue;
        }

        if (byte == '\n') {
            diag->command_buffer[diag->command_length] = '\0';
            if (diag->command_length > 0U) {
                BMS_Diagnostic_ExecuteCommand(
                    diag,
                    ctx,
                    diag->command_buffer);
            }
            diag->command_length = 0U;
            continue;
        }

        if (diag->command_length >=
            (BMS_DIAGNOSTIC_COMMAND_BUFFER_SIZE - 1U)) {
            diag->command_length = 0U;
            ctx->regs.diag.response_code = BMS_DIAG_RESPONSE_BUFFER_OVERFLOW;
            BMS_Diagnostic_SendLine("RESP,ERR,COMMAND_TOO_LONG");
            continue;
        }

        diag->command_buffer[diag->command_length++] = (char)byte;
    }

    return BMS_STATUS_OK;
}
