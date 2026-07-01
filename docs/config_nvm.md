# Config And NVM

Stage 13 added the first persistent configuration path. Stage 14 adds
controlled runtime config edits through diagnostics.

## Ownership

Factory/default values still come from the active board profile.

Runtime configuration lives in:

```text
CFG_REG
```

Persistent storage is accessed only through:

```text
bms_hal/bms_nvm_hal.h
```

ESP32 storage is implemented in:

```text
bms_platform/esp32/esp32_nvm_hal.cpp
```

The BMS core does not include Arduino, ESP32, or Preferences headers.

## Persisted Values

The Stage 13 persisted config record stores `bms_cfg_reg_t`, including:

- voltage divider ratio ppm
- voltage gain ppm
- voltage offset mV
- NTC ADC gain ppm
- NTC ADC offset mV
- voltage/current/temperature thresholds
- generic calibration gain/offset arrays
- battery capacity
- CRC

Measurement conversion now reads voltage and NTC calibration from `CFG_REG`.
Stage 14 also tracks whether the runtime config has unsaved edits through
`CFG_REG.config_dirty`.

## Diagnostic Commands

```text
GET,CFG
CFG,SET,VOLT_RATIO,<index>,<ppm>
CFG,SET,VOLT_GAIN,<index>,<ppm>
CFG,SET,VOLT_OFFSET,<index>,<mV>
CFG,SET,NTC_GAIN,<index>,<ppm>
CFG,SET,NTC_OFFSET,<index>,<mV>
CFG,SET,CAPACITY,<mAh>
CFG,SET,THRESHOLD,<name>,<value>
CFG,SAVE
CFG,LOAD
CFG,RESET
```

Indexes in diagnostic commands are one-based. `CFG,SET,VOLT_RATIO,1,1132427`
edits cell/tap 1.

Supported threshold names:

- `CELL_LOW_WARN` / `VLOW_WARN`
- `CELL_LOW_FAULT` / `VLOW_FAULT`
- `CELL_HIGH_WARN` / `VHIGH_WARN`
- `CELL_HIGH_FAULT` / `VHIGH_FAULT`
- `PACK_LOW_FAULT`
- `PACK_HIGH_FAULT`
- `CELL_IMBALANCE_WARN` / `IMBALANCE_WARN`
- `OVERCURRENT_WARN` / `CUR_WARN`
- `OVERCURRENT_FAULT` / `CUR_FAULT`
- `TEMP_HIGH_WARN` / `TEMP_WARN`
- `TEMP_HIGH_FAULT` / `TEMP_FAULT`

Successful `CFG,SET,...` commands update `CFG_REG`, refresh the config CRC, and
mark the config dirty. They do not write flash.

`CFG,SAVE` writes the current `CFG_REG` to NVM.

`CFG,LOAD` reloads the saved config if a valid record exists.

`CFG,RESET` erases the saved config and restores board-profile defaults into
`CFG_REG`.

No scheduler task writes flash. NVM writes are explicit diagnostic actions only.
