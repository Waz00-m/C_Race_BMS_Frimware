#include "bms_diagnostic.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "bms_adc_hal.h"
#include "bms_config.h"
#include "bms_fault_codes.h"
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
        "RESP,HELP,CMDS=HELP|GET,SNAPSHOT|GET,VOLT|GET,CURRENT|GET,TEMP|GET,FAULT|GET,SLEEP|GET,TAPS|GET,CFG|CFG,SET,...|CFG,SAVE|CFG,LOAD|CFG,RESET");
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

static void BMS_Diagnostic_SendConfig(const bms_register_snapshot_t *snapshot)
{
    char line[256];
    const bms_cfg_reg_t *cfg = &snapshot->regs.cfg;

    (void)snprintf(
        line,
        sizeof(line),
        "RESP,CFG,VERSION=%lu,CRC=0x%08lX,DIRTY=%u,CAPACITY_MAH=%lu",
        (unsigned long)cfg->config_version,
        (unsigned long)cfg->config_crc,
        (unsigned)cfg->config_dirty,
        (unsigned long)cfg->battery_capacity_mAh);
    BMS_Diagnostic_SendLine(line);

    (void)snprintf(
        line,
        sizeof(line),
        "RESP,CFG,THRESHOLDS,VLOW_WARN=%u,VLOW_FAULT=%u,VHIGH_WARN=%u,VHIGH_FAULT=%u,PACK_LOW=%u,PACK_HIGH=%u,IMBALANCE=%u,CUR_WARN=%ld,CUR_FAULT=%ld,TEMP_WARN=%d,TEMP_FAULT=%d",
        (unsigned)cfg->voltage_thresholds_mV[
            BMS_VOLTAGE_THRESHOLD_CELL_LOW_WARNING_MV],
        (unsigned)cfg->voltage_thresholds_mV[
            BMS_VOLTAGE_THRESHOLD_CELL_LOW_FAULT_MV],
        (unsigned)cfg->voltage_thresholds_mV[
            BMS_VOLTAGE_THRESHOLD_CELL_HIGH_WARNING_MV],
        (unsigned)cfg->voltage_thresholds_mV[
            BMS_VOLTAGE_THRESHOLD_CELL_HIGH_FAULT_MV],
        (unsigned)cfg->voltage_thresholds_mV[
            BMS_VOLTAGE_THRESHOLD_PACK_LOW_FAULT_MV],
        (unsigned)cfg->voltage_thresholds_mV[
            BMS_VOLTAGE_THRESHOLD_PACK_HIGH_FAULT_MV],
        (unsigned)cfg->voltage_thresholds_mV[
            BMS_VOLTAGE_THRESHOLD_CELL_IMBALANCE_WARNING_MV],
        (long)cfg->current_thresholds_mA[
            BMS_CURRENT_THRESHOLD_OVERCURRENT_WARNING_MA],
        (long)cfg->current_thresholds_mA[
            BMS_CURRENT_THRESHOLD_OVERCURRENT_FAULT_MA],
        (int)cfg->temperature_thresholds_dC[
            BMS_TEMPERATURE_THRESHOLD_HIGH_WARNING_DC],
        (int)cfg->temperature_thresholds_dC[
            BMS_TEMPERATURE_THRESHOLD_HIGH_FAULT_DC]);
    BMS_Diagnostic_SendLine(line);

    (void)snprintf(
        line,
        sizeof(line),
        "RESP,CFG,VOLT_RATIO_PPM=[%lu,%lu,%lu,%lu,%lu,%lu]",
        (unsigned long)cfg->voltage_divider_ratio_ppm[0],
        (unsigned long)cfg->voltage_divider_ratio_ppm[1],
        (unsigned long)cfg->voltage_divider_ratio_ppm[2],
        (unsigned long)cfg->voltage_divider_ratio_ppm[3],
        (unsigned long)cfg->voltage_divider_ratio_ppm[4],
        (unsigned long)cfg->voltage_divider_ratio_ppm[5]);
    BMS_Diagnostic_SendLine(line);

    (void)snprintf(
        line,
        sizeof(line),
        "RESP,CFG,VOLT_GAIN_PPM=[%ld,%ld,%ld,%ld,%ld,%ld]",
        (long)cfg->voltage_gain_ppm[0],
        (long)cfg->voltage_gain_ppm[1],
        (long)cfg->voltage_gain_ppm[2],
        (long)cfg->voltage_gain_ppm[3],
        (long)cfg->voltage_gain_ppm[4],
        (long)cfg->voltage_gain_ppm[5]);
    BMS_Diagnostic_SendLine(line);

    (void)snprintf(
        line,
        sizeof(line),
        "RESP,CFG,VOLT_OFFSET_MV=[%ld,%ld,%ld,%ld,%ld,%ld]",
        (long)cfg->voltage_offset_mV[0],
        (long)cfg->voltage_offset_mV[1],
        (long)cfg->voltage_offset_mV[2],
        (long)cfg->voltage_offset_mV[3],
        (long)cfg->voltage_offset_mV[4],
        (long)cfg->voltage_offset_mV[5]);
    BMS_Diagnostic_SendLine(line);

    (void)snprintf(
        line,
        sizeof(line),
        "RESP,CFG,NTC_GAIN_PPM=[%ld,%ld,%ld,%ld],NTC_OFFSET_MV=[%d,%d,%d,%d]",
        (long)cfg->ntc_adc_gain_ppm[0],
        (long)cfg->ntc_adc_gain_ppm[1],
        (long)cfg->ntc_adc_gain_ppm[2],
        (long)cfg->ntc_adc_gain_ppm[3],
        (int)cfg->ntc_adc_offset_mV[0],
        (int)cfg->ntc_adc_offset_mV[1],
        (int)cfg->ntc_adc_offset_mV[2],
        (int)cfg->ntc_adc_offset_mV[3]);
    BMS_Diagnostic_SendLine(line);
}

static void BMS_Diagnostic_SendConfigStatus(
    const char *action,
    bms_status_t status,
    const bms_context_t *ctx)
{
    char line[128];
    const uint32_t crc = BMS_Context_IsInitialized(ctx) ?
        ctx->regs.cfg.config_crc :
        0UL;

    (void)snprintf(
        line,
        sizeof(line),
        "RESP,CFG,%s,STATUS=%s,CRC=0x%08lX,DIRTY=%u",
        action,
        BMS_Status_ToString(status),
        (unsigned long)crc,
        (unsigned)(BMS_Context_IsInitialized(ctx) ?
            ctx->regs.cfg.config_dirty :
            false));
    BMS_Diagnostic_SendLine(line);
}

static bool BMS_Diagnostic_ParseInt32(const char *text, int32_t *value)
{
    if ((text == NULL) || (value == NULL)) {
        return false;
    }

    char *end = NULL;
    const long parsed = strtol(text, &end, 0);
    if ((end == text) || (*end != '\0')) {
        return false;
    }

    *value = (int32_t)parsed;
    return true;
}

static bool BMS_Diagnostic_ParseUint32(const char *text, uint32_t *value)
{
    if ((text == NULL) || (value == NULL) || (text[0] == '-')) {
        return false;
    }

    char *end = NULL;
    const unsigned long parsed = strtoul(text, &end, 0);
    if ((end == text) || (*end != '\0')) {
        return false;
    }

    *value = (uint32_t)parsed;
    return true;
}

static uint8_t BMS_Diagnostic_SplitTokens(
    char *text,
    char *tokens[],
    uint8_t max_tokens)
{
    uint8_t count = 0U;
    char *cursor = text;

    while ((cursor != NULL) && (*cursor != '\0') && (count < max_tokens)) {
        while (*cursor == ' ') {
            cursor++;
        }

        if (*cursor == '\0') {
            break;
        }

        tokens[count++] = cursor;

        while ((*cursor != '\0') && (*cursor != ' ')) {
            cursor++;
        }

        if (*cursor == ' ') {
            *cursor = '\0';
            cursor++;
        }
    }

    return count;
}

typedef struct {
    const char *name;
    bms_config_threshold_id_t id;
} bms_diagnostic_threshold_name_t;

static bool BMS_Diagnostic_LookupThreshold(
    const char *name,
    bms_config_threshold_id_t *id)
{
    static const bms_diagnostic_threshold_name_t names[] = {
        {"CELL_LOW_WARN", BMS_CONFIG_THRESHOLD_CELL_LOW_WARN},
        {"VLOW_WARN", BMS_CONFIG_THRESHOLD_CELL_LOW_WARN},
        {"CELL_LOW_FAULT", BMS_CONFIG_THRESHOLD_CELL_LOW_FAULT},
        {"VLOW_FAULT", BMS_CONFIG_THRESHOLD_CELL_LOW_FAULT},
        {"CELL_HIGH_WARN", BMS_CONFIG_THRESHOLD_CELL_HIGH_WARN},
        {"VHIGH_WARN", BMS_CONFIG_THRESHOLD_CELL_HIGH_WARN},
        {"CELL_HIGH_FAULT", BMS_CONFIG_THRESHOLD_CELL_HIGH_FAULT},
        {"VHIGH_FAULT", BMS_CONFIG_THRESHOLD_CELL_HIGH_FAULT},
        {"PACK_LOW_FAULT", BMS_CONFIG_THRESHOLD_PACK_LOW_FAULT},
        {"PACK_HIGH_FAULT", BMS_CONFIG_THRESHOLD_PACK_HIGH_FAULT},
        {"CELL_IMBALANCE_WARN", BMS_CONFIG_THRESHOLD_CELL_IMBALANCE_WARN},
        {"IMBALANCE_WARN", BMS_CONFIG_THRESHOLD_CELL_IMBALANCE_WARN},
        {"OVERCURRENT_WARN", BMS_CONFIG_THRESHOLD_OVERCURRENT_WARN},
        {"CUR_WARN", BMS_CONFIG_THRESHOLD_OVERCURRENT_WARN},
        {"OVERCURRENT_FAULT", BMS_CONFIG_THRESHOLD_OVERCURRENT_FAULT},
        {"CUR_FAULT", BMS_CONFIG_THRESHOLD_OVERCURRENT_FAULT},
        {"TEMP_HIGH_WARN", BMS_CONFIG_THRESHOLD_TEMP_HIGH_WARN},
        {"TEMP_WARN", BMS_CONFIG_THRESHOLD_TEMP_HIGH_WARN},
        {"TEMP_HIGH_FAULT", BMS_CONFIG_THRESHOLD_TEMP_HIGH_FAULT},
        {"TEMP_FAULT", BMS_CONFIG_THRESHOLD_TEMP_HIGH_FAULT},
    };

    if ((name == NULL) || (id == NULL)) {
        return false;
    }

    for (uint8_t i = 0U; i < (uint8_t)(sizeof(names) / sizeof(names[0])); ++i) {
        if (strcmp(name, names[i].name) == 0) {
            *id = names[i].id;
            return true;
        }
    }

    return false;
}

static void BMS_Diagnostic_SendConfigSetStatus(
    const char *field,
    const char *name,
    int32_t index,
    int32_t value,
    bms_status_t status,
    const bms_context_t *ctx)
{
    char line[192];
    const uint32_t crc = BMS_Context_IsInitialized(ctx) ?
        ctx->regs.cfg.config_crc :
        0UL;
    const unsigned dirty = BMS_Context_IsInitialized(ctx) ?
        (unsigned)ctx->regs.cfg.config_dirty :
        0U;

    if (name != NULL) {
        (void)snprintf(
            line,
            sizeof(line),
            "RESP,CFG,SET,STATUS=%s,FIELD=%s,NAME=%s,VALUE=%ld,DIRTY=%u,CRC=0x%08lX",
            BMS_Status_ToString(status),
            field,
            name,
            (long)value,
            dirty,
            (unsigned long)crc);
    } else if (index > 0L) {
        (void)snprintf(
            line,
            sizeof(line),
            "RESP,CFG,SET,STATUS=%s,FIELD=%s,INDEX=%ld,VALUE=%ld,DIRTY=%u,CRC=0x%08lX",
            BMS_Status_ToString(status),
            field,
            (long)index,
            (long)value,
            dirty,
            (unsigned long)crc);
    } else {
        (void)snprintf(
            line,
            sizeof(line),
            "RESP,CFG,SET,STATUS=%s,FIELD=%s,VALUE=%ld,DIRTY=%u,CRC=0x%08lX",
            BMS_Status_ToString(status),
            field,
            (long)value,
            dirty,
            (unsigned long)crc);
    }

    BMS_Diagnostic_SendLine(line);
}

static void BMS_Diagnostic_ExecuteConfigSet(
    bms_context_t *ctx,
    char *payload)
{
    char *tokens[5] = {0};
    const uint8_t count = BMS_Diagnostic_SplitTokens(payload, tokens, 5U);
    const char *field = (count >= 3U) ? tokens[2] : "UNKNOWN";
    const char *name = NULL;
    int32_t index = -1L;
    int32_t value = 0L;
    bms_status_t status = BMS_STATUS_INVALID_ARGUMENT;

    if ((count == 4U) && (strcmp(field, "CAPACITY") == 0)) {
        uint32_t parsed = 0UL;
        if (BMS_Diagnostic_ParseUint32(tokens[3], &parsed)) {
            value = (int32_t)parsed;
            status = BMS_Config_SetCapacityMah(ctx, parsed);
        }
    } else if ((count == 5U) && (strcmp(field, "THRESHOLD") == 0)) {
        bms_config_threshold_id_t threshold = BMS_CONFIG_THRESHOLD_CELL_LOW_WARN;
        name = tokens[3];
        if (BMS_Diagnostic_LookupThreshold(tokens[3], &threshold) &&
            BMS_Diagnostic_ParseInt32(tokens[4], &value)) {
            status = BMS_Config_SetThreshold(ctx, threshold, value);
        }
    } else if (count == 5U) {
        uint32_t parsed_index = 0UL;
        if (BMS_Diagnostic_ParseUint32(tokens[3], &parsed_index) &&
            BMS_Diagnostic_ParseInt32(tokens[4], &value) &&
            (parsed_index > 0UL) &&
            (parsed_index <= 255UL)) {
            const uint8_t zero_based_index = (uint8_t)(parsed_index - 1UL);
            index = (int32_t)parsed_index;

            if (strcmp(field, "VOLT_RATIO") == 0) {
                status = BMS_Config_SetVoltageRatioPpm(
                    ctx,
                    zero_based_index,
                    (uint32_t)value);
            } else if (strcmp(field, "VOLT_GAIN") == 0) {
                status = BMS_Config_SetVoltageGainPpm(
                    ctx,
                    zero_based_index,
                    value);
            } else if (strcmp(field, "VOLT_OFFSET") == 0) {
                status = BMS_Config_SetVoltageOffsetMv(
                    ctx,
                    zero_based_index,
                    value);
            } else if (strcmp(field, "NTC_GAIN") == 0) {
                status = BMS_Config_SetNtcGainPpm(
                    ctx,
                    zero_based_index,
                    value);
            } else if (strcmp(field, "NTC_OFFSET") == 0) {
                status = BMS_Config_SetNtcOffsetMv(
                    ctx,
                    zero_based_index,
                    value);
            }
        }
    }

    BMS_Diagnostic_SendConfigSetStatus(
        field,
        name,
        index,
        value,
        status,
        ctx);
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

    if (strcmp(payload, "GET CFG") == 0) {
        return BMS_DIAG_COMMAND_GET_CFG;
    }

    if ((strncmp(payload, "CFG SET", 7U) == 0) &&
        ((payload[7U] == '\0') || (payload[7U] == ' '))) {
        return BMS_DIAG_COMMAND_CFG_SET;
    }

    if (strcmp(payload, "CFG SAVE") == 0) {
        return BMS_DIAG_COMMAND_CFG_SAVE;
    }

    if (strcmp(payload, "CFG LOAD") == 0) {
        return BMS_DIAG_COMMAND_CFG_LOAD;
    }

    if (strcmp(payload, "CFG RESET") == 0) {
        return BMS_DIAG_COMMAND_CFG_RESET;
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

    if (command_id == BMS_DIAG_COMMAND_CFG_SET) {
        BMS_Diagnostic_ExecuteConfigSet(ctx, (char *)payload);
        ctx->regs.diag.diagnostic_active = false;
        return;
    }

    if (command_id == BMS_DIAG_COMMAND_CFG_SAVE) {
        const bms_status_t status = BMS_Config_Save(ctx);
        BMS_Diagnostic_SendConfigStatus("SAVE", status, ctx);
        ctx->regs.diag.diagnostic_active = false;
        return;
    }

    if (command_id == BMS_DIAG_COMMAND_CFG_LOAD) {
        const bms_status_t status = BMS_Config_Load(ctx);
        if (status == BMS_STATUS_OK) {
            BMS_Config_RefreshCrc(ctx);
        }
        BMS_Diagnostic_SendConfigStatus("LOAD", status, ctx);
        ctx->regs.diag.diagnostic_active = false;
        return;
    }

    if (command_id == BMS_DIAG_COMMAND_CFG_RESET) {
        const bms_status_t status = BMS_Config_ResetToDefaults(ctx);
        BMS_Diagnostic_SendConfigStatus("RESET", status, ctx);
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
    case BMS_DIAG_COMMAND_GET_CFG:
        BMS_Diagnostic_SendConfig(&snapshot);
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
