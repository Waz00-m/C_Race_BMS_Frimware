"""Browser GUI for the Drone BMS PC UART tester."""

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import sys
import threading
import time
from urllib.parse import unquote
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from pc_bms_uart_tester import (
    BmsSerialClient,
    DEFAULT_BAUD,
    DEFAULT_TIMEOUT_S,
    EXPECTED_CELL_VALID_MASK,
    EXPECTED_CURRENT_REASON,
    EXPECTED_CURRENT_VALID,
    EXPECTED_TAP_VALID_MASK,
    EXPECTED_TEMP_REASON,
    EXPECTED_TEMP_VALID_MASK,
    EXPECTED_VOLTAGE_REASON,
    parse_int,
)

try:
    from serial.tools import list_ports
except ImportError:
    list_ports = None


SCRIPT_DIR = Path(__file__).resolve().parent
PROFILE_PATH = SCRIPT_DIR / "test_profiles.json"
REPORT_DIR = SCRIPT_DIR / "reports"

DEFAULT_PROFILES = {
    "Strict all-valid": {
        "expected": {
            "cell_valid_mask": EXPECTED_CELL_VALID_MASK,
            "tap_valid_mask": EXPECTED_TAP_VALID_MASK,
            "voltage_reason": EXPECTED_VOLTAGE_REASON,
            "current_valid": EXPECTED_CURRENT_VALID,
            "current_reason": EXPECTED_CURRENT_REASON,
            "temp_valid_mask": EXPECTED_TEMP_VALID_MASK,
            "temp_reason": EXPECTED_TEMP_REASON,
        },
        "known": {
            "enabled": False,
            "fault_codes": [],
        },
    },
    "Known T1 temp sensor": {
        "expected": {
            "cell_valid_mask": EXPECTED_CELL_VALID_MASK,
            "tap_valid_mask": EXPECTED_TAP_VALID_MASK,
            "voltage_reason": EXPECTED_VOLTAGE_REASON,
            "current_valid": EXPECTED_CURRENT_VALID,
            "current_reason": EXPECTED_CURRENT_REASON,
            "temp_valid_mask": EXPECTED_TEMP_VALID_MASK,
            "temp_reason": EXPECTED_TEMP_REASON,
        },
        "known": {
            "enabled": True,
            "fault_codes": [0x3003],
        },
    },
    "Known current sensor": {
        "expected": {
            "cell_valid_mask": EXPECTED_CELL_VALID_MASK,
            "tap_valid_mask": EXPECTED_TAP_VALID_MASK,
            "voltage_reason": EXPECTED_VOLTAGE_REASON,
            "current_valid": EXPECTED_CURRENT_VALID,
            "current_reason": EXPECTED_CURRENT_REASON,
            "temp_valid_mask": EXPECTED_TEMP_VALID_MASK,
            "temp_reason": EXPECTED_TEMP_REASON,
        },
        "known": {
            "enabled": True,
            "fault_codes": [0x2003],
        },
    },
}


HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Drone BMS Tester</title>
  <style>
    :root {
      --bg: #f6f7f9;
      --panel: #ffffff;
      --panel-2: #f0f3f5;
      --ink: #1f252b;
      --muted: #697580;
      --line: #d7dde2;
      --good: #16865b;
      --warn: #b7791f;
      --bad: #b42318;
      --focus: #256f9c;
      --shadow: 0 10px 26px rgba(31, 37, 43, 0.08);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--ink);
      letter-spacing: 0;
    }
    button, input, select {
      font: inherit;
      letter-spacing: 0;
    }
    button {
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
      padding: 8px 11px;
      min-height: 36px;
      cursor: pointer;
    }
    button.primary {
      background: var(--focus);
      color: #fff;
      border-color: var(--focus);
    }
    button.danger {
      color: var(--bad);
      border-color: #e2aaa4;
    }
    button.icon {
      width: 36px;
      min-width: 36px;
      padding: 0;
      font-weight: 800;
    }
    button:disabled {
      opacity: 0.55;
      cursor: not-allowed;
    }
    input, select {
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
      min-height: 36px;
      padding: 7px 9px;
      min-width: 0;
    }
    input[type="range"] {
      padding: 0;
      accent-color: var(--focus);
    }
    .app {
      width: min(1460px, calc(100vw - 28px));
      margin: 14px auto 24px;
    }
    .topbar {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 14px;
      align-items: center;
      margin-bottom: 12px;
    }
    h1 {
      margin: 0;
      font-size: 24px;
      line-height: 1.2;
      font-weight: 700;
    }
    .subtle {
      color: var(--muted);
      font-size: 13px;
    }
    .status-strip {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }
    .pill {
      display: inline-flex;
      align-items: center;
      min-height: 28px;
      padding: 4px 9px;
      border-radius: 999px;
      background: var(--panel-2);
      border: 1px solid var(--line);
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
    }
    .pill.good { color: var(--good); background: #e9f6ef; border-color: #bfe3cf; }
    .pill.bad { color: var(--bad); background: #fff0ee; border-color: #efc2bc; }
    .pill.warn { color: var(--warn); background: #fff7e8; border-color: #ebd19a; }
    .mode-badge {
      position: fixed;
      right: 16px;
      bottom: 14px;
      z-index: 20;
      padding: 7px 10px;
      border-radius: 7px;
      border: 1px solid #ebd19a;
      background: #fff7e8;
      color: var(--warn);
      font-size: 12px;
      font-weight: 800;
      box-shadow: var(--shadow);
    }
    .mode-badge[hidden] { display: none; }
    .toolbar, .commandbar {
      display: grid;
      grid-template-columns: minmax(170px, 1fr) 94px 88px auto auto auto;
      gap: 8px;
      align-items: center;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      box-shadow: var(--shadow);
      margin-bottom: 12px;
    }
    .commandbar {
      grid-template-columns: minmax(240px, 1fr) repeat(7, auto);
      box-shadow: none;
    }
    .layout {
      display: grid;
      grid-template-columns: minmax(300px, 390px) 1fr;
      gap: 12px;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }
    .panel h2 {
      margin: 0;
      padding: 11px 12px;
      border-bottom: 1px solid var(--line);
      font-size: 15px;
      line-height: 1.2;
      background: #fbfcfd;
    }
    .panel-body {
      padding: 12px;
    }
    .stack {
      display: grid;
      gap: 12px;
    }
    .form-grid {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 8px;
      align-items: center;
    }
    .code-row {
      display: grid;
      grid-template-columns: 1fr 36px;
      gap: 8px;
      align-items: center;
    }
    .field-label {
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
      text-transform: uppercase;
    }
    .switch-line {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: center;
    }
    .switch-line input[type="checkbox"] {
      width: 42px;
      min-height: 22px;
      accent-color: var(--focus);
    }
    .slider-field {
      display: grid;
      grid-template-columns: 112px 1fr 72px;
      gap: 9px;
      align-items: center;
      min-height: 34px;
    }
    .slider-field label {
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
    }
    .value {
      text-align: right;
      font-variant-numeric: tabular-nums;
      color: var(--ink);
      font-size: 13px;
    }
    .meter-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(230px, 1fr));
      gap: 12px;
    }
    .metric-list {
      display: grid;
      gap: 8px;
    }
    .metric {
      display: grid;
      grid-template-columns: 42px minmax(110px, 1fr) 78px;
      gap: 8px;
      align-items: center;
      min-height: 32px;
    }
    .metric strong {
      font-size: 12px;
    }
    .metric input[type="range"] {
      width: 100%;
    }
    .small-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
      gap: 8px;
    }
    .stat {
      background: #fbfcfd;
      border: 1px solid var(--line);
      border-radius: 7px;
      padding: 9px;
      min-height: 58px;
    }
    .stat span {
      display: block;
      color: var(--muted);
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      margin-bottom: 5px;
    }
    .stat strong {
      font-size: 17px;
      font-variant-numeric: tabular-nums;
      word-break: break-word;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }
    th, td {
      padding: 8px 7px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }
    th {
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
    }
    .raw {
      min-height: 140px;
      max-height: 260px;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: #101418;
      color: #e8edf2;
      padding: 10px;
      font-family: Consolas, "SFMono-Regular", monospace;
      font-size: 12px;
      white-space: pre-wrap;
    }
    .two-col {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }
    .hidden { display: none; }
    @media (max-width: 1060px) {
      .layout, .meter-grid, .two-col {
        grid-template-columns: 1fr;
      }
      .toolbar, .commandbar {
        grid-template-columns: 1fr 1fr;
      }
      .topbar {
        grid-template-columns: 1fr;
      }
      .status-strip {
        justify-content: flex-start;
      }
    }
  </style>
</head>
<body>
  <main class="app">
    <div class="topbar">
      <div>
        <h1>Drone BMS Tester</h1>
        <div class="subtle">PC diagnostic harness for Stage 16</div>
      </div>
      <div class="status-strip">
        <span id="connectionPill" class="pill bad">Disconnected</span>
        <span id="resultPill" class="pill">No test</span>
        <span id="diagPill" class="pill">Snapshot idle</span>
      </div>
    </div>

    <section class="toolbar">
      <select id="portSelect"></select>
      <input id="baudInput" type="number" value="115200" min="9600" step="9600">
      <input id="timeoutInput" type="number" value="1.8" min="0.2" step="0.1">
      <button id="refreshPortsBtn">Refresh</button>
      <button id="connectBtn" class="primary">Connect</button>
      <button id="disconnectBtn" class="danger">Disconnect</button>
    </section>

    <section class="commandbar">
      <input id="commandInput" value="GET,TAPS">
      <button data-command="GET,TAPS">Taps</button>
      <button data-command="GET,VOLT">Voltage</button>
      <button data-command="GET,CURRENT">Current</button>
      <button data-command="GET,TEMP">Temp</button>
      <button data-command="GET,FAULT">Fault</button>
      <button data-command="GET,INJECT">Inject</button>
      <button id="sendBtn" class="primary">Send</button>
    </section>

    <div class="layout">
      <aside class="stack">
        <section class="panel">
          <h2>Automated Test</h2>
          <div class="panel-body stack">
            <button id="autoTestBtn" class="primary">Run Automated Test</button>
            <button id="snapshotBtn">Refresh Snapshot</button>
            <div id="reportStatus" class="subtle">No report yet</div>
            <div class="switch-line">
              <div>
                <div class="field-label">Known fault exclusions</div>
                <div id="knownText" class="subtle">OFF</div>
              </div>
              <input id="knownEnabled" type="checkbox">
            </div>
            <div class="stack">
              <label class="field-label" for="knownFaultCodes">Known fault codes</label>
              <div class="code-row">
                <input id="knownFaultCodes" value="" placeholder="0x3003, 0x2003">
                <button id="faultInfoBtn" class="icon" title="Open fault code table">i</button>
              </div>
            </div>
          </div>
        </section>

        <section class="panel">
          <h2>Test Profiles</h2>
          <div class="panel-body stack">
            <select id="profileSelect"></select>
            <input id="profileName" value="Strict all-valid">
            <button id="loadProfileBtn">Load Profile</button>
            <button id="saveProfileBtn" class="primary">Save Profile</button>
          </div>
        </section>

        <section class="panel">
          <h2>Expected Baseline</h2>
          <div class="panel-body stack">
            <div class="slider-field">
              <label for="expectedCellMask">Cell mask</label>
              <input id="expectedCellMask" type="range" min="0" max="63" value="63">
              <div id="expectedCellMaskValue" class="value">0x3F</div>
            </div>
            <div class="slider-field">
              <label for="expectedTapMask">Tap mask</label>
              <input id="expectedTapMask" type="range" min="0" max="63" value="63">
              <div id="expectedTapMaskValue" class="value">0x3F</div>
            </div>
            <div class="slider-field">
              <label for="expectedTempMask">Temp mask</label>
              <input id="expectedTempMask" type="range" min="0" max="15" value="15">
              <div id="expectedTempMaskValue" class="value">0xF</div>
            </div>
            <div class="switch-line">
              <span class="field-label">Current valid</span>
              <input id="expectedCurrentValid" type="checkbox" checked>
            </div>
            <div class="form-grid">
              <label class="field-label" for="expectedVoltageReason">Voltage reason</label>
              <input id="expectedVoltageReason" value="0x0">
              <label class="field-label" for="expectedCurrentReason">Current reason</label>
              <input id="expectedCurrentReason" value="0x0">
              <label class="field-label" for="expectedTempReason">Temp reason</label>
              <input id="expectedTempReason" value="0x0">
            </div>
          </div>
        </section>

        <section class="panel">
          <h2>ADC Injection Stimulus</h2>
          <div class="panel-body stack">
            <div class="switch-line">
              <div>
                <div class="field-label">Firmware ADC injection</div>
                <div id="injectText" class="subtle">OFF</div>
              </div>
              <input id="injectEnabled" type="checkbox">
            </div>
            <div class="form-grid">
              <label class="field-label" for="allCellTarget">All cells target mV</label>
              <input id="allCellTarget" type="number" value="2600" min="0" max="5000" step="10">
            </div>
            <button id="computeCellAdcBtn">Compute Cell ADC Sliders</button>
            <div id="stimCellSliders" class="metric-list"></div>
            <div class="slider-field">
              <label for="stimCurrentAdc">Current ADC</label>
              <input id="stimCurrentAdc" type="range" min="0" max="3300" value="1650">
              <div id="stimCurrentAdcValue" class="value">1650 mV</div>
            </div>
            <div id="stimTempSliders" class="metric-list"></div>
            <button id="applyStimulusBtn" class="primary">Apply ADC Stimulus</button>
            <button id="clearStimulusBtn" class="danger">Clear Injection</button>
          </div>
        </section>
      </aside>

      <section class="stack">
        <section class="panel">
          <h2>Response Meters</h2>
          <div class="panel-body stack">
            <div class="small-grid">
              <div class="stat"><span>Pack</span><strong id="packValue">--</strong></div>
              <div class="stat"><span>Current</span><strong id="currentValue">--</strong></div>
              <div class="stat"><span>Current ADC</span><strong id="currentAdcValue">--</strong></div>
              <div class="stat"><span>Primary</span><strong id="primaryValue">--</strong></div>
              <div class="stat"><span>Severity</span><strong id="severityValue">--</strong></div>
            </div>
            <div class="meter-grid">
              <div class="panel">
                <h2>Cells</h2>
                <div id="cellMeters" class="panel-body metric-list"></div>
              </div>
              <div class="panel">
                <h2>Taps</h2>
                <div id="tapMeters" class="panel-body metric-list"></div>
              </div>
              <div class="panel">
                <h2>ADC</h2>
                <div id="adcMeters" class="panel-body metric-list"></div>
              </div>
            </div>
            <div class="two-col">
              <div class="panel">
                <h2>Temperatures</h2>
                <div id="tempMeters" class="panel-body metric-list"></div>
              </div>
              <div class="panel">
                <h2>Validity</h2>
                <div class="panel-body small-grid">
                  <div class="stat"><span>Cell valid</span><strong id="cellValidValue">--</strong></div>
                  <div class="stat"><span>Tap valid</span><strong id="tapValidValue">--</strong></div>
                  <div class="stat"><span>Temp valid</span><strong id="tempValidValue">--</strong></div>
                  <div class="stat"><span>Current valid</span><strong id="currentValidValue">--</strong></div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section class="panel">
          <h2>Test Results</h2>
          <div class="panel-body">
            <table>
              <thead>
                <tr><th>Status</th><th>Check</th><th>Expected</th><th>Actual</th></tr>
              </thead>
              <tbody id="resultsBody"></tbody>
            </table>
          </div>
        </section>

        <section class="panel">
          <h2>Run History</h2>
          <div class="panel-body stack">
            <button id="refreshHistoryBtn">Refresh History</button>
            <table>
              <thead>
                <tr><th>Result</th><th>Time</th><th>Profile</th><th>Checks</th><th>Port</th><th>Report</th></tr>
              </thead>
              <tbody id="historyBody"></tbody>
            </table>
          </div>
        </section>

        <section class="panel">
          <h2>Raw Responses</h2>
          <div class="panel-body">
            <div id="rawOutput" class="raw"></div>
          </div>
        </section>
      </section>
    </div>
  </main>
  <div id="diagModeBadge" class="mode-badge" hidden>DIAG_MODE</div>

  <script>
    const $ = (id) => document.getElementById(id);
    const commands = {
      TAPS: "GET,TAPS",
      VOLT: "GET,VOLT",
      CURRENT: "GET,CURRENT",
      TEMP: "GET,TEMP",
      FAULT: "GET,FAULT",
      SNAPSHOT: "GET,SNAPSHOT",
    };
    const responseState = {};

    function hex(value, width = 0) {
      const parsed = Number(value || 0);
      const text = parsed.toString(16).toUpperCase();
      return "0x" + (width ? text.padStart(width, "0") : text);
    }

    function parseNumeric(text) {
      if (text === undefined || text === null || text === "") return 0;
      const value = String(text).trim();
      const parsed = value.toLowerCase().startsWith("0x")
        ? parseInt(value, 16)
        : parseInt(value, 10);
      return Number.isNaN(parsed) ? 0 : parsed;
    }

    function parseList(text) {
      if (!text) return [];
      return String(text)
        .replace(/^\[/, "")
        .replace(/\]$/, "")
        .split(",")
        .map((item) => item.trim())
        .filter((item) => item.length > 0);
    }

    function parseCodeList(text) {
      return parseList(String(text || "").replace(/;/g, ","))
        .map(parseNumeric)
        .filter((item) => item > 0);
    }

    function setPill(el, text, cls) {
      el.className = "pill" + (cls ? " " + cls : "");
      el.textContent = text;
    }

    function setDiagMode(active) {
      $("diagModeBadge").hidden = !active;
    }

    function appendRaw(line) {
      if (!line) return;
      const out = $("rawOutput");
      out.textContent = [line, out.textContent].filter(Boolean).join("\n");
      const lines = out.textContent.split("\n");
      if (lines.length > 80) out.textContent = lines.slice(0, 80).join("\n");
    }

    function makeMeters(container, prefix, count, max, unit) {
      container.innerHTML = "";
      for (let i = 0; i < count; i++) {
        const row = document.createElement("div");
        row.className = "metric";
        row.innerHTML = `
          <strong>${prefix}${i + 1}</strong>
          <input id="${prefix.toLowerCase()}${i}Range" type="range" min="0" max="${max}" value="0" disabled>
          <span id="${prefix.toLowerCase()}${i}Value" class="value">-- ${unit}</span>
        `;
        container.appendChild(row);
      }
    }

    function makeStimSliders(container, prefix, count, value) {
      container.innerHTML = "";
      for (let i = 0; i < count; i++) {
        const row = document.createElement("div");
        row.className = "metric";
        row.innerHTML = `
          <strong>${prefix}${i + 1}</strong>
          <input id="stim${prefix}${i}" type="range" min="0" max="3300" value="${value}">
          <span id="stim${prefix}${i}Value" class="value">${value} mV</span>
        `;
        container.appendChild(row);
      }
    }

    function setMeter(prefix, index, value, max, unit) {
      const range = $(`${prefix}${index}Range`);
      const label = $(`${prefix}${index}Value`);
      if (!range || !label) return;
      if (value === "FAULT") {
        range.max = max;
        range.value = 0;
        label.textContent = "FAULT";
        return;
      }
      const numeric = Number(value || 0);
      range.max = max;
      range.value = Math.max(0, Math.min(max, numeric));
      label.textContent = value === null || value === undefined ? "--" : `${value} ${unit}`;
    }

    function updateMaskLabels() {
      $("expectedCellMaskValue").textContent = hex($("expectedCellMask").value);
      $("expectedTapMaskValue").textContent = hex($("expectedTapMask").value);
      $("expectedTempMaskValue").textContent = hex($("expectedTempMask").value);
      const knownCodes = parseCodeList($("knownFaultCodes").value).map((code) => hex(code, 4));
      $("knownText").textContent = $("knownEnabled").checked
        ? (knownCodes.length ? `ON ${knownCodes.join(", ")}` : "ON, no codes")
        : "OFF";
      $("injectText").textContent = $("injectEnabled").checked ? "ON" : "OFF";
      $("stimCurrentAdcValue").textContent = `${$("stimCurrentAdc").value} mV`;
      for (let i = 0; i < 6; i++) {
        const input = $(`stimC${i}`);
        const label = $(`stimC${i}Value`);
        if (input && label) label.textContent = `${input.value} mV`;
      }
      for (let i = 0; i < 4; i++) {
        const input = $(`stimTemp${i}`);
        const label = $(`stimTemp${i}Value`);
        if (input && label) label.textContent = `${input.value} mV`;
      }
    }

    function expectedPayload() {
      return {
        expected: {
          cell_valid_mask: parseNumeric($("expectedCellMask").value),
          tap_valid_mask: parseNumeric($("expectedTapMask").value),
          voltage_reason: parseNumeric($("expectedVoltageReason").value),
          current_valid: $("expectedCurrentValid").checked ? 1 : 0,
          current_reason: parseNumeric($("expectedCurrentReason").value),
          temp_valid_mask: parseNumeric($("expectedTempMask").value),
          temp_reason: parseNumeric($("expectedTempReason").value),
        },
        known: {
          enabled: $("knownEnabled").checked,
          fault_codes: parseCodeList($("knownFaultCodes").value),
        },
      };
    }

    function currentProfile() {
      return {
        ...expectedPayload(),
        stimulus: stimulusPayload(),
      };
    }

    function applyProfile(profile) {
      const expected = profile.expected || {};
      const known = profile.known || {};
      const stimulus = profile.stimulus || {};

      $("expectedCellMask").value = expected.cell_valid_mask ?? 63;
      $("expectedTapMask").value = expected.tap_valid_mask ?? 63;
      $("expectedTempMask").value = expected.temp_valid_mask ?? 15;
      $("expectedCurrentValid").checked = parseNumeric(expected.current_valid ?? 1) !== 0;
      $("expectedVoltageReason").value = hex(expected.voltage_reason ?? 0);
      $("expectedCurrentReason").value = hex(expected.current_reason ?? 0);
      $("expectedTempReason").value = hex(expected.temp_reason ?? 0);
      $("knownEnabled").checked = Boolean(known.enabled);
      $("knownFaultCodes").value = (known.fault_codes || [])
        .map((code) => hex(code, 4))
        .join(", ");

      if (Array.isArray(stimulus.cell_adc_mv)) {
        stimulus.cell_adc_mv.slice(0, 6).forEach((value, i) => {
          const input = $(`stimC${i}`);
          if (input) input.value = value;
        });
      }
      if (stimulus.current_adc_mv !== undefined) {
        $("stimCurrentAdc").value = stimulus.current_adc_mv;
      }
      if (Array.isArray(stimulus.temp_adc_mv)) {
        stimulus.temp_adc_mv.slice(0, 4).forEach((value, i) => {
          const input = $(`stimTemp${i}`);
          if (input) input.value = value;
        });
      }
      if (stimulus.enabled !== undefined) {
        $("injectEnabled").checked = Boolean(stimulus.enabled);
      }
      updateMaskLabels();
    }

    async function api(path, options = {}) {
      const response = await fetch(path, {
        headers: { "Content-Type": "application/json" },
        ...options,
      });
      const data = await response.json();
      if (!response.ok || data.ok === false) {
        throw new Error(data.error || "Request failed");
      }
      return data;
    }

    async function refreshPorts() {
      try {
        const data = await api("/api/ports");
        const select = $("portSelect");
        select.innerHTML = "";
        if (!data.ports.length) {
          const opt = document.createElement("option");
          opt.textContent = "No serial ports";
          opt.value = "";
          select.appendChild(opt);
          return;
        }
        for (const item of data.ports) {
          const opt = document.createElement("option");
          opt.value = item.device;
          opt.textContent = `${item.device} - ${item.description}`;
          select.appendChild(opt);
        }
      } catch (err) {
        appendRaw("PORT ERROR: " + err.message);
      }
    }

    async function refreshProfiles() {
      try {
        const data = await api("/api/profiles");
        const select = $("profileSelect");
        const previous = select.value;
        select.innerHTML = "";
        for (const name of data.names || []) {
          const opt = document.createElement("option");
          opt.value = name;
          opt.textContent = name;
          select.appendChild(opt);
        }
        if (previous) select.value = previous;
        if (!select.value && select.options.length) select.selectedIndex = 0;
        if (!$("profileName").value && select.value) $("profileName").value = select.value;
      } catch (err) {
        appendRaw("PROFILE ERROR: " + err.message);
      }
    }

    async function loadSelectedProfile() {
      try {
        const name = $("profileSelect").value;
        const data = await api("/api/profiles/load", {
          method: "POST",
          body: JSON.stringify({ name }),
        });
        $("profileName").value = data.name;
        applyProfile(data.profile || {});
        appendRaw("PROFILE LOADED: " + data.name);
      } catch (err) {
        appendRaw("PROFILE LOAD ERROR: " + err.message);
      }
    }

    async function saveCurrentProfile() {
      try {
        const name = $("profileName").value.trim() || "Untitled profile";
        const data = await api("/api/profiles/save", {
          method: "POST",
          body: JSON.stringify({ name, profile: currentProfile() }),
        });
        await refreshProfiles();
        $("profileSelect").value = data.name;
        appendRaw("PROFILE SAVED: " + data.name);
      } catch (err) {
        appendRaw("PROFILE SAVE ERROR: " + err.message);
      }
    }

    function renderHistory(data) {
      const body = $("historyBody");
      body.innerHTML = "";
      for (const item of data.runs || []) {
        const row = document.createElement("tr");
        const cls = item.result === "PASS" ? "good" : "bad";
        const checks = `${item.passed || 0}/${(item.passed || 0) + (item.failed || 0)}`;
        const report = item.pdf_url
          ? `<a href="${item.pdf_url}" target="_blank">${item.pdf_name}</a>`
          : "--";
        row.innerHTML = `
          <td><span class="pill ${cls}">${item.result || "--"}</span></td>
          <td>${item.timestamp || "--"}</td>
          <td>${item.profile_name || "--"}</td>
          <td>${checks}</td>
          <td>${item.port || "--"}</td>
          <td>${report}</td>
        `;
        body.appendChild(row);
      }
      if (!data.runs || data.runs.length === 0) {
        const row = document.createElement("tr");
        row.innerHTML = `<td colspan="6" class="subtle">No report history yet</td>`;
        body.appendChild(row);
      }
    }

    async function refreshHistory() {
      try {
        const data = await api("/api/history");
        renderHistory(data);
      } catch (err) {
        appendRaw("HISTORY ERROR: " + err.message);
      }
    }

    async function refreshState() {
      try {
        const data = await api("/api/state");
        setPill(
          $("connectionPill"),
          data.connected ? `Connected ${data.port}` : "Disconnected",
          data.connected ? "good" : "bad"
        );
      } catch (err) {
        setPill($("connectionPill"), "Disconnected", "bad");
      }
    }

    async function connect() {
      const port = $("portSelect").value;
      const baud = parseNumeric($("baudInput").value);
      const timeout = Number($("timeoutInput").value || 1.8);
      await api("/api/connect", {
        method: "POST",
        body: JSON.stringify({ port, baud, timeout }),
      });
      await refreshState();
    }

    async function disconnect() {
      await api("/api/disconnect", { method: "POST", body: "{}" });
      await refreshState();
    }

    function rememberResponse(kind, data) {
      if (!kind) return;
      responseState[kind] = data;
      if (kind === "INJECT") {
        renderInjectionState(data);
      }
      renderMeters();
      seedStimulusFromSnapshot();
    }

    function renderInjectionState(data) {
      const injectionActive = parseNumeric(data.ENABLED) !== 0;
      $("injectEnabled").checked = injectionActive;
      setDiagMode(injectionActive);
      const values = parseList(data.ADC_MV).map(parseNumeric);
      values.slice(0, 6).forEach((value, i) => {
        const input = $(`stimC${i}`);
        if (input) input.value = value;
      });
      if (values.length > 6) $("stimCurrentAdc").value = values[6];
      values.slice(7, 11).forEach((value, i) => {
        const input = $(`stimTemp${i}`);
        if (input) input.value = value;
      });
      updateMaskLabels();
    }

    function seedStimulusFromSnapshot() {
      if ($("injectEnabled").checked) return;

      const taps = responseState.TAPS || {};
      const current = responseState.CURRENT || {};
      const temp = responseState.TEMP || {};
      const adcValues = parseList(taps.ADC_MV);
      const tempAdcValues = parseList(temp.ADC_MV);

      adcValues.forEach((value, i) => {
        const input = $(`stimC${i}`);
        if (input && parseNumeric(input.value) === 0) input.value = parseNumeric(value);
      });
      if (current.ADC_MV && parseNumeric($("stimCurrentAdc").value) === 1650) {
        $("stimCurrentAdc").value = parseNumeric(current.ADC_MV);
      }
      tempAdcValues.forEach((value, i) => {
        const input = $(`stimTemp${i}`);
        if (input && parseNumeric(input.value) === 1400) input.value = parseNumeric(value);
      });
      updateMaskLabels();
    }

    function computeCellAdcFromTarget() {
      const targetCell = parseNumeric($("allCellTarget").value);
      const taps = responseState.TAPS || {};
      const tapValues = parseList(taps.TAP_MV).map(parseNumeric);
      const adcValues = parseList(taps.ADC_MV).map(parseNumeric);

      if (tapValues.length < 6 || adcValues.length < 6) {
        appendRaw("STIMULUS: refresh snapshot before computing cell ADC targets");
        return;
      }

      for (let i = 0; i < 6; i++) {
        const ratio = adcValues[i] > 0 ? tapValues[i] / adcValues[i] : 0;
        const targetTap = targetCell * (i + 1);
        const targetAdc = ratio > 0 ? Math.round(targetTap / ratio) : 0;
        const input = $(`stimC${i}`);
        if (input) input.value = Math.max(0, Math.min(3300, targetAdc));
      }
      updateMaskLabels();
    }

    function stimulusPayload() {
      const cellAdc = [];
      const tempAdc = [];
      for (let i = 0; i < 6; i++) cellAdc.push(parseNumeric($(`stimC${i}`).value));
      for (let i = 0; i < 4; i++) tempAdc.push(parseNumeric($(`stimTemp${i}`).value));
      return {
        enabled: $("injectEnabled").checked,
        cell_adc_mv: cellAdc,
        current_adc_mv: parseNumeric($("stimCurrentAdc").value),
        temp_adc_mv: tempAdc,
      };
    }

    async function applyStimulus() {
      try {
        setPill($("diagPill"), "Applying injection", "warn");
        const data = await api("/api/stimulus", {
          method: "POST",
          body: JSON.stringify(stimulusPayload()),
        });
        for (const line of data.lines || []) appendRaw(line);
        for (const item of data.responses || []) {
          appendRaw(item.line);
          rememberResponse(item.kind, item.data);
        }
        setPill($("diagPill"), "Injection applied", "good");
      } catch (err) {
        appendRaw("STIMULUS ERROR: " + err.message);
        setPill($("diagPill"), "Injection failed", "bad");
      }
    }

    async function clearStimulus() {
      try {
        setPill($("diagPill"), "Clearing injection", "warn");
        const data = await api("/api/stimulus/clear", { method: "POST", body: "{}" });
        for (const line of data.lines || []) appendRaw(line);
        for (const item of data.responses || []) {
          appendRaw(item.line);
          rememberResponse(item.kind, item.data);
        }
        $("injectEnabled").checked = false;
        setDiagMode(false);
        updateMaskLabels();
        setPill($("diagPill"), "Injection cleared", "good");
      } catch (err) {
        appendRaw("CLEAR ERROR: " + err.message);
        setPill($("diagPill"), "Clear failed", "bad");
      }
    }

    function renderMeters() {
      const taps = responseState.TAPS || {};
      const volt = responseState.VOLT || {};
      const temp = responseState.TEMP || {};
      const current = responseState.CURRENT || {};
      const fault = responseState.FAULT || {};

      const cells = parseList(volt.CELL_MV || taps.CELL_MV);
      const tapValues = parseList(taps.TAP_MV);
      const adcValues = parseList(taps.ADC_MV);
      const tempValues = parseList(temp.TEMP_DC);

      cells.forEach((value, i) => setMeter("c", i, value, 5000, "mV"));
      tapValues.forEach((value, i) => setMeter("t", i, value, 26000, "mV"));
      adcValues.forEach((value, i) => setMeter("a", i, value, 3300, "mV"));
      tempValues.forEach((value, i) => {
        const numeric = value === "FAULT" ? 0 : parseNumeric(value);
        setMeter("temp", i, value === "FAULT" ? "FAULT" : (numeric / 10).toFixed(1), 100, "C");
      });

      $("packValue").textContent = volt.PACK_MV ? (parseNumeric(volt.PACK_MV) / 1000).toFixed(3) + " V" : "--";
      $("currentValue").textContent = current.CURRENT_MA ? (parseNumeric(current.CURRENT_MA) / 1000).toFixed(3) + " A" : "--";
      $("currentAdcValue").textContent = current.ADC_MV ? `${parseNumeric(current.ADC_MV)} mV` : "--";
      $("primaryValue").textContent = fault.PRIMARY || "--";
      $("severityValue").textContent = fault.SEVERITY || "--";

      $("cellValidValue").textContent = volt.VALID || taps.CELL_VALID || fault.CELL_VALID || "--";
      $("tapValidValue").textContent = volt.TAP_VALID || taps.TAP_VALID || fault.TAP_VALID || "--";
      $("tempValidValue").textContent = temp.VALID || fault.TEMP_VALID || "--";
      $("currentValidValue").textContent = current.VALID || fault.CURRENT_VALID || "--";
    }

    async function sendCommand(command) {
      try {
        setPill($("diagPill"), "Command pending", "warn");
        const expected = command.toUpperCase().startsWith("GET,")
          ? command.toUpperCase().split(",", 2)[1]
          : "";
        const data = await api("/api/command", {
          method: "POST",
          body: JSON.stringify({ command, expected }),
        });
        appendRaw(data.line || "No response");
        rememberResponse(data.kind, data.data);
        setPill($("diagPill"), "Snapshot updated", "good");
      } catch (err) {
        appendRaw("COMMAND ERROR: " + err.message);
        setPill($("diagPill"), "Command failed", "bad");
      }
    }

    async function runSnapshot() {
      try {
        setPill($("diagPill"), "Snapshot pending", "warn");
        const data = await api("/api/snapshot", { method: "POST", body: "{}" });
        for (const item of data.responses) {
          appendRaw(item.line);
          rememberResponse(item.kind, item.data);
        }
        setPill($("diagPill"), "Snapshot updated", "good");
      } catch (err) {
        appendRaw("SNAPSHOT ERROR: " + err.message);
        setPill($("diagPill"), "Snapshot failed", "bad");
      }
    }

    function renderResults(data) {
      const body = $("resultsBody");
      body.innerHTML = "";
      for (const test of data.tests || []) {
        for (const check of test.checks || []) {
          const row = document.createElement("tr");
          const statusClass = check.excluded ? "warn" : (check.pass ? "good" : "bad");
          const statusText = check.excluded ? "EXCLUDED" : (check.pass ? "PASS" : "FAIL");
          row.innerHTML = `
            <td><span class="pill ${statusClass}">${statusText}</span></td>
            <td>${test.name}: ${check.label}</td>
            <td>${check.expected}</td>
            <td>${check.actual}</td>
          `;
          body.appendChild(row);
        }
      }
      setPill(
        $("resultPill"),
        data.failed === 0 ? `PASS ${data.passed}` : `FAIL ${data.failed}`,
        data.failed === 0 ? "good" : "bad"
      );
    }

    async function runAutoTest() {
      try {
        setPill($("diagPill"), "Test running", "warn");
        const data = await api("/api/auto-test", {
          method: "POST",
          body: JSON.stringify({
            ...expectedPayload(),
            profile_name: $("profileName").value.trim() || $("profileSelect").value || "Ad hoc",
          }),
        });
        renderResults(data);
        for (const test of data.tests || []) {
          if (test.line) appendRaw(test.line);
          if (test.kind) rememberResponse(test.kind, test.data);
        }
        if (data.report && data.report.pdf_url) {
          $("reportStatus").innerHTML = `<a href="${data.report.pdf_url}" target="_blank">${data.report.pdf_name}</a>`;
          appendRaw("REPORT PDF: " + data.report.pdf_path);
        }
        await refreshHistory();
        setPill($("diagPill"), "Test complete", data.failed === 0 ? "good" : "bad");
      } catch (err) {
        appendRaw("TEST ERROR: " + err.message);
        setPill($("resultPill"), "ERROR", "bad");
        setPill($("diagPill"), "Test failed", "bad");
      }
    }

    function initMeters() {
      makeMeters($("cellMeters"), "C", 6, 5000, "mV");
      makeMeters($("tapMeters"), "T", 6, 26000, "mV");
      makeMeters($("adcMeters"), "A", 6, 3300, "mV");
      makeMeters($("tempMeters"), "Temp", 4, 100, "C");
      makeStimSliders($("stimCellSliders"), "C", 6, 0);
      makeStimSliders($("stimTempSliders"), "Temp", 4, 1400);
    }

    document.addEventListener("DOMContentLoaded", () => {
      initMeters();
      $("knownEnabled").checked = false;
      $("knownFaultCodes").value = "";
      $("injectEnabled").checked = false;
      setDiagMode(false);
      updateMaskLabels();
      refreshPorts();
      refreshProfiles();
      refreshHistory();
      refreshState();

      for (const id of ["expectedCellMask", "expectedTapMask", "expectedTempMask", "knownFaultCodes", "knownEnabled", "injectEnabled", "stimCurrentAdc"]) {
        $(id).addEventListener("input", updateMaskLabels);
        $(id).addEventListener("change", updateMaskLabels);
      }
      for (let i = 0; i < 6; i++) {
        $(`stimC${i}`).addEventListener("input", updateMaskLabels);
      }
      for (let i = 0; i < 4; i++) {
        $(`stimTemp${i}`).addEventListener("input", updateMaskLabels);
      }
      $("refreshPortsBtn").addEventListener("click", refreshPorts);
      $("connectBtn").addEventListener("click", () => connect().catch((err) => appendRaw("CONNECT ERROR: " + err.message)));
      $("disconnectBtn").addEventListener("click", () => disconnect().catch((err) => appendRaw("DISCONNECT ERROR: " + err.message)));
      $("sendBtn").addEventListener("click", () => sendCommand($("commandInput").value));
      $("autoTestBtn").addEventListener("click", runAutoTest);
      $("snapshotBtn").addEventListener("click", runSnapshot);
      $("refreshHistoryBtn").addEventListener("click", refreshHistory);
      $("loadProfileBtn").addEventListener("click", loadSelectedProfile);
      $("saveProfileBtn").addEventListener("click", saveCurrentProfile);
      $("profileSelect").addEventListener("change", () => {
        $("profileName").value = $("profileSelect").value;
      });
      $("computeCellAdcBtn").addEventListener("click", computeCellAdcFromTarget);
      $("applyStimulusBtn").addEventListener("click", applyStimulus);
      $("clearStimulusBtn").addEventListener("click", clearStimulus);
      $("faultInfoBtn").addEventListener("click", () => window.open("/fault-table", "_blank"));
      document.querySelectorAll("[data-command]").forEach((button) => {
        button.addEventListener("click", () => {
          $("commandInput").value = button.dataset.command;
          sendCommand(button.dataset.command);
        });
      });
    });
  </script>
</body>
</html>
"""


SNAPSHOT_COMMANDS = (
    ("GET,INJECT", "INJECT"),
    ("GET,TAPS", "TAPS"),
    ("GET,VOLT", "VOLT"),
    ("GET,CURRENT", "CURRENT"),
    ("GET,TEMP", "TEMP"),
    ("GET,FAULT", "FAULT"),
)


def as_hex(value, width=8):
    return "0x%0*X" % (width, int(value))


FAULT_CODE_TABLE = (
    (0x0000, "No fault", "No active primary fault"),
    (0x1001, "Cell overvoltage", "One or more cells exceed high fault threshold"),
    (0x1002, "Cell undervoltage", "One or more cells are below low fault threshold"),
    (0x1003, "Pack overvoltage", "Pack voltage exceeds high pack fault threshold"),
    (0x1004, "Pack undervoltage", "Pack voltage is below low pack fault threshold"),
    (0x2002, "Discharge overcurrent", "Absolute current exceeds overcurrent fault threshold"),
    (0x2003, "Current sensor fault", "Current sensor invalid or not responding"),
    (0x3001, "Cell temperature high", "One or more temperature channels exceed high fault threshold"),
    (0x3003, "Temperature sensor fault", "Temperature channel open, short, or implausible"),
    (0x4001, "ADC read failure", "One or more expected ADC channels are not valid"),
    (0x4002, "Measurement invalid", "Converted measurement failed validation before fault checks"),
)

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


def parse_code_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        items = value
    else:
        items = str(value).replace(";", ",").split(",")
    codes = []
    for item in items:
        text = str(item).strip()
        if not text:
            continue
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


def read_json(handler):
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def write_json(handler, status, payload):
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def write_html(handler):
    body = HTML.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def write_fault_table(handler):
    rows = "\n".join(
        "<tr><td>%s</td><td>%s</td><td>%s</td></tr>" %
        (as_hex(code, 4), name, meaning)
        for code, name, meaning in FAULT_CODE_TABLE
    )
    body = ("""<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\">
<title>BMS Fault Code Table</title>
<style>
body{font-family:Segoe UI,Arial,sans-serif;margin:24px;color:#1f252b;background:#f6f7f9}
table{border-collapse:collapse;width:min(920px,100%%);background:#fff}
th,td{border:1px solid #d7dde2;padding:10px;text-align:left}
th{background:#eef2f5}
code{font-weight:700}
</style></head><body>
<h1>BMS Fault Code Table</h1>
<table><thead><tr><th>Code</th><th>Name</th><th>Meaning</th></tr></thead>
<tbody>%s</tbody></table>
</body></html>""" % rows).encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def load_profiles():
    profiles = dict(DEFAULT_PROFILES)
    if PROFILE_PATH.exists():
        try:
            with PROFILE_PATH.open("r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            if isinstance(loaded, dict):
                profiles.update(loaded)
        except Exception:
            pass
    return profiles


def save_profiles(profiles):
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PROFILE_PATH.open("w", encoding="utf-8") as handle:
        json.dump(profiles, handle, indent=2, sort_keys=True)


def _pdf_escape(text):
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )


PDF_PAGE_W = 612.0
PDF_PAGE_H = 792.0
PDF_MARGIN = 42.0
PDF_FOOTER_Y = 28.0
PDF_HEADER_Y = 750.0

PDF_INK = (0.12, 0.15, 0.18)
PDF_MUTED = (0.38, 0.43, 0.48)
PDF_LINE = (0.78, 0.82, 0.86)
PDF_NAVY = (0.05, 0.16, 0.24)
PDF_PANEL = (0.97, 0.98, 0.99)
PDF_HEAD = (0.90, 0.93, 0.95)
PDF_GOOD = (0.08, 0.53, 0.36)
PDF_BAD = (0.70, 0.14, 0.09)
PDF_WARN = (0.72, 0.47, 0.12)
PDF_WHITE = (1.0, 1.0, 1.0)


def _pdf_num(value):
    text = "%.2f" % float(value)
    return text.rstrip("0").rstrip(".")


def _pdf_rgb(rgb, op):
    return "%.3f %.3f %.3f %s" % (rgb[0], rgb[1], rgb[2], op)


def _wrap_text(text, limit):
    words = str(text).split()
    if not words:
        return [""]
    lines = []
    current = ""
    for word in words:
        if len(word) > limit:
            if current:
                lines.append(current)
                current = ""
            lines.append(word[:limit])
            continue
        candidate = word if not current else current + " " + word
        if len(candidate) <= limit:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _wrap_cell(text, width, size=8.5, max_lines=None):
    limit = max(8, int(width / (size * 0.52)))
    lines = []
    for part in str(text).splitlines() or [""]:
        lines.extend(_wrap_text(part, limit))
    if max_lines is not None and len(lines) > max_lines:
        lines = lines[:max_lines]
        if lines:
            lines[-1] = lines[-1].rstrip(".") + "..."
    return lines or [""]


class PdfDocument:
    def __init__(self):
        self.pages = []
        self.new_page()

    def new_page(self):
        self.pages.append([])

    def cmd(self, command):
        self.pages[-1].append(command)

    def rect(self, x, y, w, h, fill=None, stroke=None):
        if fill is not None:
            self.cmd(
                "%s %s %s %s %s re f" %
                (_pdf_rgb(fill, "rg"), _pdf_num(x), _pdf_num(y),
                 _pdf_num(w), _pdf_num(h))
            )
        if stroke is not None:
            self.cmd(
                "%s %s %s %s %s re S" %
                (_pdf_rgb(stroke, "RG"), _pdf_num(x), _pdf_num(y),
                 _pdf_num(w), _pdf_num(h))
            )

    def line(self, x1, y1, x2, y2, color=PDF_LINE, width=1.0):
        self.cmd(
            "%s %s w %s %s m %s %s l S" %
            (_pdf_rgb(color, "RG"), _pdf_num(width), _pdf_num(x1),
             _pdf_num(y1), _pdf_num(x2), _pdf_num(y2))
        )

    def text(self, x, y, text, size=9.0, font="F1", color=PDF_INK):
        self.cmd(
            "BT /%s %s Tf %s 1 0 0 1 %s %s Tm (%s) Tj ET" %
            (font, _pdf_num(size), _pdf_rgb(color, "rg"), _pdf_num(x),
             _pdf_num(y), _pdf_escape(text))
        )

    def write(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        objects = [
            "<< /Type /Catalog /Pages 2 0 R >>",
            "__PAGES__",
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
            "<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>",
        ]
        page_object_ids = []

        for page_no, commands in enumerate(self.pages, start=1):
            footer = [
                "0.780 0.820 0.860 RG 0.5 w 42 36 m 570 36 l S",
                "BT /F1 7 Tf 0.380 0.430 0.480 rg 1 0 0 1 42 22 Tm "
                "(C-RACE LABS | Drone BMS Firmware Validation) Tj ET",
                "BT /F1 7 Tf 0.380 0.430 0.480 rg 1 0 0 1 520 22 Tm "
                "(Page %u) Tj ET" % page_no,
            ]
            content = "\n".join(commands + footer)
            content_bytes = content.encode("latin-1", errors="replace")
            content_id = len(objects) + 2
            page_id = len(objects) + 1
            page_object_ids.append(page_id)
            objects.append(
                "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                "/Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R >> >> "
                "/Contents %u 0 R >>" % content_id
            )
            objects.append(
                "<< /Length %u >>\nstream\n%s\nendstream" %
                (len(content_bytes), content_bytes.decode("latin-1"))
            )

        kids = " ".join("%u 0 R" % object_id for object_id in page_object_ids)
        objects[1] = "<< /Type /Pages /Kids [%s] /Count %u >>" % (
            kids,
            len(page_object_ids),
        )

        output = bytearray()
        output.extend(b"%PDF-1.4\n")
        offsets = [0]
        for index, body in enumerate(objects, start=1):
            offsets.append(len(output))
            output.extend(("%u 0 obj\n%s\nendobj\n" % (index, body)).encode(
                "latin-1",
                errors="replace",
            ))
        xref_offset = len(output)
        output.extend(("xref\n0 %u\n" % (len(objects) + 1)).encode("ascii"))
        output.extend(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            output.extend(("%010u 00000 n \n" % offset).encode("ascii"))
        output.extend((
            "trailer\n<< /Size %u /Root 1 0 R >>\nstartxref\n%u\n%%%%EOF\n" %
            (len(objects) + 1, xref_offset)
        ).encode("ascii"))
        path.write_bytes(output)


def report_filename(timestamp, profile_name, suffix):
    safe_profile = "".join(
        ch if ch.isalnum() or ch in ("-", "_") else "_"
        for ch in profile_name.strip()
    ).strip("_") or "profile"
    stamp = timestamp.strftime("%Y%m%d_%H%M%S")
    return "bms_test_%s_%s.%s" % (stamp, safe_profile[:36], suffix)


def fault_code_label(code):
    for item_code, name, _ in FAULT_CODE_TABLE:
        if item_code == code:
            return "%s %s" % (as_hex(code, 4), name)
    return as_hex(code, 4)


def status_color(status):
    if status == "PASS":
        return PDF_GOOD
    if status == "FAIL":
        return PDF_BAD
    if status == "EXCLUDED":
        return PDF_WARN
    return PDF_MUTED


def draw_report_header(pdf, report):
    pdf.rect(0, 748, PDF_PAGE_W, 44, fill=PDF_NAVY)
    pdf.text(42, 772, "C-RACE LABS", size=17, font="F2", color=PDF_WHITE)
    pdf.text(
        42,
        756,
        "Drone BMS Firmware Validation Report",
        size=9,
        font="F1",
        color=(0.82, 0.89, 0.94),
    )
    badge_color = PDF_GOOD if report["result"] == "PASS" else PDF_BAD
    pdf.rect(500, 763, 70, 18, fill=badge_color)
    pdf.text(517, 769, report["result"], size=9, font="F2", color=PDF_WHITE)
    return 726.0


def ensure_pdf_space(pdf, report, y, needed):
    if (y - needed) >= 52:
        return y
    pdf.new_page()
    return draw_report_header(pdf, report)


def draw_section_title(pdf, report, y, title):
    y = ensure_pdf_space(pdf, report, y, 30)
    pdf.text(PDF_MARGIN, y, title, size=12, font="F2", color=PDF_NAVY)
    pdf.line(PDF_MARGIN, y - 5, 570, y - 5, color=PDF_LINE, width=0.7)
    return y - 20


def draw_summary_cards(pdf, report, y):
    cards = [
        ("Result", report["result"], status_color(report["result"])),
        ("Passed", str(report["passed"]), PDF_GOOD),
        ("Failed", str(report["failed"]), PDF_BAD if report["failed"] else PDF_MUTED),
        ("Profile", report["profile_name"], PDF_NAVY),
    ]
    widths = [112, 92, 92, 202]
    x = PDF_MARGIN
    for index, (label, value, color) in enumerate(cards):
        width = widths[index]
        pdf.rect(x, y - 48, width, 48, fill=PDF_PANEL, stroke=PDF_LINE)
        pdf.text(x + 8, y - 15, label.upper(), size=7, font="F2", color=PDF_MUTED)
        value_lines = _wrap_cell(value, width - 16, size=12, max_lines=2)
        pdf.text(x + 8, y - 32, value_lines[0], size=12, font="F2", color=color)
        if len(value_lines) > 1:
            pdf.text(x + 8, y - 43, value_lines[1], size=8, font="F1", color=color)
        x += width + 10
    return y - 66


def draw_table(pdf, report, y, headers, rows, widths, row_limit=None):
    header_h = 20
    y = ensure_pdf_space(pdf, report, y, header_h + 18)

    def draw_header(current_y):
        x_pos = PDF_MARGIN
        for index, header in enumerate(headers):
            width = widths[index]
            pdf.rect(x_pos, current_y - header_h, width, header_h, fill=PDF_HEAD, stroke=PDF_LINE)
            pdf.text(x_pos + 5, current_y - 13, header, size=7.5, font="F2", color=PDF_NAVY)
            x_pos += width
        return current_y - header_h

    y = draw_header(y)
    visible_rows = rows if row_limit is None else rows[:row_limit]
    for row_index, row in enumerate(visible_rows):
        cell_lines = []
        row_h = 18
        for index, cell in enumerate(row):
            max_lines = 4 if index == (len(row) - 1) else 3
            lines = _wrap_cell(cell, widths[index] - 10, size=7.4, max_lines=max_lines)
            cell_lines.append(lines)
            row_h = max(row_h, 8 + (len(lines) * 9))

        if (y - row_h) < 52:
            pdf.new_page()
            y = draw_report_header(pdf, report)
            y = draw_header(y)

        x_pos = PDF_MARGIN
        for index, lines in enumerate(cell_lines):
            width = widths[index]
            fill = PDF_WHITE if (row_index % 2 == 0) else (0.985, 0.99, 0.995)
            if index == 0 and str(row[index]) in ("PASS", "FAIL", "EXCLUDED"):
                fill = status_color(str(row[index]))
            pdf.rect(x_pos, y - row_h, width, row_h, fill=fill, stroke=PDF_LINE)
            text_color = PDF_WHITE if index == 0 and str(row[index]) in ("PASS", "FAIL", "EXCLUDED") else PDF_INK
            font = "F2" if index == 0 else "F1"
            for line_index, line in enumerate(lines):
                pdf.text(
                    x_pos + 5,
                    y - 13 - (line_index * 9),
                    line,
                    size=7.4,
                    font=font,
                    color=text_color,
                )
            x_pos += width
        y -= row_h

    if row_limit is not None and len(rows) > row_limit:
        y = ensure_pdf_space(pdf, report, y, 14)
        pdf.text(
            PDF_MARGIN,
            y - 10,
            "%u additional rows omitted from PDF; see JSON log for full data." %
            (len(rows) - row_limit),
            size=7.5,
            font="F1",
            color=PDF_MUTED,
        )
        y -= 18
    return y - 14


def report_check_rows(report):
    rows = []
    for test in report["tests"]:
        for check in test.get("checks", []):
            status = "EXCLUDED" if check.get("excluded") else (
                "PASS" if check.get("pass") else "FAIL"
            )
            rows.append([
                status,
                test.get("name", ""),
                check.get("label", ""),
                check.get("expected", ""),
                check.get("actual", ""),
            ])
    return rows


def report_response_rows(report):
    rows = []
    for test in report["tests"]:
        rows.append([
            test.get("command", ""),
            test.get("kind", ""),
            test.get("line", "") or "No matching response",
        ])
    return rows


def write_report_pdf(path, report):
    pdf = PdfDocument()
    y = draw_report_header(pdf, report)
    y = draw_summary_cards(pdf, report, y)

    y = draw_section_title(pdf, report, y, "Run Metadata")
    metadata_rows = [
        ["Timestamp", report["timestamp"], "Local PC time when the run finished."],
        ["Serial port", str(report["port"]), "BMS diagnostic UART port."],
        ["Baud", str(report["baud"]), "Serial baud rate."],
        ["Timeout", "%.2f s" % report["timeout"], "Per-command response timeout."],
        ["Known exclusions", "ON" if report["known"]["enabled"] else "OFF", "Tester-side expectation only."],
        ["Known fault codes", format_code_list(report["known"]["fault_codes"]), "Allowed active fault-code categories."],
    ]
    y = draw_table(pdf, report, y, ["Field", "Value", "Detail"], metadata_rows, [105, 150, 273])

    expected = report["expected"]
    expected_rows = [
        ["Cell valid mask", as_hex(expected["cell_valid_mask"]), "Expected valid reconstructed cells."],
        ["Tap valid mask", as_hex(expected["tap_valid_mask"]), "Expected valid cumulative taps."],
        ["Voltage reason", as_hex(expected["voltage_reason"]), "Expected voltage validation reason bitmap."],
        ["Current valid", str(expected["current_valid"]), "Expected current validity flag."],
        ["Current reason", as_hex(expected["current_reason"]), "Expected current validation reason bitmap."],
        ["Temp valid mask", as_hex(expected["temp_valid_mask"]), "Expected valid temperature channels."],
        ["Temp reason", as_hex(expected["temp_reason"]), "Expected temperature validation reason bitmap."],
    ]
    y = draw_section_title(pdf, report, y, "Expected Baseline")
    y = draw_table(pdf, report, y, ["Expectation", "Value", "Meaning"], expected_rows, [130, 120, 278])

    y = draw_section_title(pdf, report, y, "Automated Test Results")
    y = draw_table(
        pdf,
        report,
        y,
        ["Status", "Test", "Check", "Expected", "Actual"],
        report_check_rows(report),
        [62, 62, 132, 136, 136],
    )

    y = draw_section_title(pdf, report, y, "Diagnostic Responses")
    y = draw_table(
        pdf,
        report,
        y,
        ["Command", "Kind", "Raw Response"],
        report_response_rows(report),
        [86, 58, 384],
    )

    fault_rows = [
        [as_hex(code, 4), name, meaning]
        for code, name, meaning in FAULT_CODE_TABLE
    ]
    y = draw_section_title(pdf, report, y, "Fault Code Reference")
    y = draw_table(pdf, report, y, ["Code", "Name", "Meaning"], fault_rows, [70, 150, 308])

    pdf.write(path)


def write_test_report(state, profile_name, expected, known, tests, passed, failed):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    result = "PASS" if failed == 0 else "FAIL"
    report = {
        "timestamp": now.isoformat(timespec="seconds"),
        "profile_name": profile_name or "Ad hoc",
        "result": result,
        "port": state.port,
        "baud": state.baud,
        "timeout": state.timeout,
        "expected": expected,
        "known": {
            "enabled": known["enabled"],
            "fault_codes": sorted(known["fault_codes"]),
        },
        "passed": passed,
        "failed": failed,
        "tests": tests,
    }

    json_name = report_filename(now, report["profile_name"], "json")
    pdf_name = report_filename(now, report["profile_name"], "pdf")
    json_path = REPORT_DIR / json_name
    pdf_path = REPORT_DIR / pdf_name

    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    write_report_pdf(pdf_path, report)

    return {
        "json_name": json_name,
        "json_path": str(json_path),
        "json_url": "/reports/" + json_name,
        "pdf_name": pdf_name,
        "pdf_path": str(pdf_path),
        "pdf_url": "/reports/" + pdf_name,
    }


def write_report_file(handler, name):
    filename = unquote(name).replace("\\", "/").split("/")[-1]
    path = (REPORT_DIR / filename).resolve()
    report_root = REPORT_DIR.resolve()
    if report_root not in path.parents and path != report_root:
        write_json(handler, 403, {"ok": False, "error": "Forbidden"})
        return
    if not path.exists() or not path.is_file():
        write_json(handler, 404, {"ok": False, "error": "Report not found"})
        return
    if path.suffix.lower() == ".pdf":
        content_type = "application/pdf"
    else:
        content_type = "application/json"
    body = path.read_bytes()
    handler.send_response(200)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def load_report_history(limit=10):
    if not REPORT_DIR.exists():
        return []

    runs = []
    files = sorted(
        REPORT_DIR.glob("*.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    for path in files[:limit]:
        try:
            with path.open("r", encoding="utf-8") as handle:
                report = json.load(handle)
        except Exception:
            continue

        pdf_name = path.with_suffix(".pdf").name
        pdf_path = REPORT_DIR / pdf_name
        runs.append({
            "timestamp": report.get("timestamp", ""),
            "profile_name": report.get("profile_name", ""),
            "result": report.get("result", ""),
            "passed": report.get("passed", 0),
            "failed": report.get("failed", 0),
            "port": report.get("port", ""),
            "json_name": path.name,
            "json_url": "/reports/" + path.name,
            "pdf_name": pdf_name if pdf_path.exists() else "",
            "pdf_url": "/reports/" + pdf_name if pdf_path.exists() else "",
        })
    return runs


def get_expected(payload):
    expected = payload.get("expected", {})
    return {
        "cell_valid_mask": parse_int(expected.get(
            "cell_valid_mask",
            EXPECTED_CELL_VALID_MASK,
        )),
        "tap_valid_mask": parse_int(expected.get(
            "tap_valid_mask",
            EXPECTED_TAP_VALID_MASK,
        )),
        "voltage_reason": parse_int(expected.get(
            "voltage_reason",
            EXPECTED_VOLTAGE_REASON,
        )),
        "current_valid": parse_int(expected.get(
            "current_valid",
            EXPECTED_CURRENT_VALID,
        )),
        "current_reason": parse_int(expected.get(
            "current_reason",
            EXPECTED_CURRENT_REASON,
        )),
        "temp_valid_mask": parse_int(expected.get(
            "temp_valid_mask",
            EXPECTED_TEMP_VALID_MASK,
        )),
        "temp_reason": parse_int(expected.get(
            "temp_reason",
            EXPECTED_TEMP_REASON,
        )),
    }


def get_known(payload):
    known = payload.get("known", {})
    return {
        "enabled": bool(known.get("enabled", False)),
        "fault_codes": set(parse_code_list(known.get("fault_codes", []))),
    }


def known_fault_context(known, fault_data):
    active_codes = fault_codes_from_data(fault_data)
    allowed_codes = known["fault_codes"] if known["enabled"] else set()
    return {
        "enabled": known["enabled"],
        "allowed_codes": allowed_codes,
        "active_codes": active_codes,
        "matched_codes": active_codes & allowed_codes,
    }


def known_allows_domain(context, domain):
    if not context["enabled"] or not context["matched_codes"]:
        return False
    for code in context["matched_codes"]:
        if domain in KNOWN_FAULT_DOMAINS.get(code, {"fault"}):
            return True
    return False


def apply_known_exclusions(test, context):
    for check in test["checks"]:
        if check["pass"] or check.get("domain") == "fault_codes":
            continue
        if known_allows_domain(context, check.get("domain", "fault")):
            check["pass"] = True
            check["excluded"] = True
            check["expected"] = "%s, excluded by %s" % (
                check["expected"],
                format_code_list(context["matched_codes"]),
            )


def make_check(label, expected, actual, passed, domain="general"):
    return {
        "label": label,
        "expected": expected,
        "actual": actual,
        "pass": bool(passed),
        "domain": domain,
        "excluded": False,
    }


def check_hex(data, key, expected, label, domain="general"):
    if key not in data:
        return make_check(label, as_hex(expected), "missing " + key, False, domain)
    try:
        actual = parse_int(data[key])
        return make_check(label, as_hex(expected), as_hex(actual), actual == expected, domain)
    except Exception as exc:
        return make_check(label, as_hex(expected), "parse error: " + str(exc), False, domain)


def check_int(data, key, expected, label, domain="general"):
    if key not in data:
        return make_check(label, str(expected), "missing " + key, False, domain)
    try:
        actual = parse_int(data[key])
        return make_check(label, str(expected), str(actual), actual == expected, domain)
    except Exception as exc:
        return make_check(label, str(expected), "parse error: " + str(exc), False, domain)


def check_fault_codes(data, context):
    active_codes = fault_codes_from_data(data)
    allowed_codes = context["allowed_codes"] if context["enabled"] else set()
    unexpected_codes = active_codes - allowed_codes
    expected = "none"
    if context["enabled"] and allowed_codes:
        expected = "none except " + format_code_list(allowed_codes)
    return make_check(
        "active fault codes",
        expected,
        format_code_list(active_codes),
        len(unexpected_codes) == 0,
        "fault_codes",
    )


def run_test_case(state, name, command, expected_kind, checks_fn):
    line, kind, data = state.request(command, expected_kind)
    result = {
        "name": name,
        "command": command,
        "line": line,
        "kind": kind,
        "data": data,
        "checks": [],
    }
    if line is None:
        result["checks"].append(make_check("response", "RESP," + expected_kind, "none", False))
        return result
    result["checks"].extend(checks_fn(data))
    return result


class TesterState:
    def __init__(self):
        self.lock = threading.RLock()
        self.client = None
        self.port = None
        self.baud = DEFAULT_BAUD
        self.timeout = DEFAULT_TIMEOUT_S

    def is_connected(self):
        return self.client is not None

    def connect(self, port, baud, timeout):
        if not port:
            raise ValueError("No serial port selected")
        with self.lock:
            self.disconnect()
            self.client = BmsSerialClient(port, baud, timeout, show_raw=False)
            self.client.drain()
            self.port = port
            self.baud = baud
            self.timeout = timeout

    def disconnect(self):
        with self.lock:
            if self.client is not None:
                self.client.close()
            self.client = None
            self.port = None

    def request(self, command, expected_kind=None):
        with self.lock:
            if self.client is None:
                raise RuntimeError("Not connected")
            return self.client.request(command, expected_kind, self.timeout)

    def snapshot(self):
        responses = []
        for command, kind in SNAPSHOT_COMMANDS:
            line, actual_kind, data = self.request(command, kind)
            responses.append({
                "command": command,
                "line": line,
                "kind": actual_kind,
                "data": data,
            })
        return responses

    def _send_diag_adc(self, command):
        line, _, _ = self.request(command, "DIAG")
        return line if line is not None else command + " -> no response"

    def apply_stimulus(self, payload):
        lines = []
        cell_adc = payload.get("cell_adc_mv", [])
        temp_adc = payload.get("temp_adc_mv", [])
        current_adc = payload.get("current_adc_mv", 0)
        enabled = bool(payload.get("enabled", False))

        for index, value in enumerate(cell_adc[:6]):
            adc = max(0, min(3300, parse_int(value)))
            lines.append(self._send_diag_adc(
                "DIAG,ADC,SET,CELL,%u,%u" % (index + 1, adc)
            ))

        lines.append(self._send_diag_adc(
            "DIAG,ADC,SET,CURRENT,%u" % max(0, min(3300, parse_int(current_adc)))
        ))

        for index, value in enumerate(temp_adc[:4]):
            adc = max(0, min(3300, parse_int(value)))
            lines.append(self._send_diag_adc(
                "DIAG,ADC,SET,TEMP,%u,%u" % (index + 1, adc)
            ))

        lines.append(self._send_diag_adc(
            "DIAG,ADC,ON" if enabled else "DIAG,ADC,OFF"
        ))

        time.sleep(0.35)
        return {
            "ok": True,
            "lines": lines,
            "responses": self.snapshot(),
        }

    def clear_stimulus(self):
        lines = [
            self._send_diag_adc("DIAG,ADC,OFF"),
            self._send_diag_adc("DIAG,ADC,CLEAR,ALL"),
        ]
        time.sleep(0.35)
        return {
            "ok": True,
            "lines": lines,
            "responses": self.snapshot(),
        }

    def run_auto_test(self, expected, known, profile_name="Ad hoc"):
        tests = []
        _, _, fault_data = self.request("GET,FAULT", "FAULT")
        context = known_fault_context(known, fault_data)

        tests.append(run_test_case(
            self,
            "TAPS",
            "GET,TAPS",
            "TAPS",
            lambda data: [
                check_hex(data, "TAP_VALID", expected["tap_valid_mask"], "tap valid bitmap", "voltage"),
                check_hex(data, "CELL_VALID", expected["cell_valid_mask"], "cell valid bitmap", "voltage"),
                check_hex(data, "REASON", expected["voltage_reason"], "voltage reason", "voltage"),
            ],
        ))
        tests.append(run_test_case(
            self,
            "VOLT",
            "GET,VOLT",
            "VOLT",
            lambda data: [
                check_hex(data, "VALID", expected["cell_valid_mask"], "cell valid bitmap", "voltage"),
                check_hex(data, "TAP_VALID", expected["tap_valid_mask"], "tap valid bitmap", "voltage"),
                check_hex(data, "REASON", expected["voltage_reason"], "voltage reason", "voltage"),
            ],
        ))
        tests.append(run_test_case(
            self,
            "CURRENT",
            "GET,CURRENT",
            "CURRENT",
            lambda data: [
                check_int(data, "VALID", expected["current_valid"], "current valid flag", "current"),
                check_hex(data, "REASON", expected["current_reason"], "current reason", "current"),
            ],
        ))
        tests.append(run_test_case(
            self,
            "TEMP",
            "GET,TEMP",
            "TEMP",
            lambda data: [
                check_hex(data, "VALID", expected["temp_valid_mask"], "temperature valid bitmap", "temperature"),
                check_hex(data, "REASON", expected["temp_reason"], "temperature reason", "temperature"),
            ],
        ))
        tests.append(run_test_case(
            self,
            "FAULT",
            "GET,FAULT",
            "FAULT",
            lambda data: [
                check_fault_codes(data, context),
                check_hex(data, "CELL_VALID", expected["cell_valid_mask"], "fault cell mirror", "voltage"),
                check_hex(data, "TAP_VALID", expected["tap_valid_mask"], "fault tap mirror", "voltage"),
                check_int(data, "CURRENT_VALID", expected["current_valid"], "fault current mirror", "current"),
                check_hex(data, "TEMP_VALID", expected["temp_valid_mask"], "fault temp mirror", "temperature"),
            ],
        ))

        for test in tests:
            apply_known_exclusions(test, context)

        passed = 0
        failed = 0
        for test in tests:
            for check in test["checks"]:
                if check["pass"]:
                    passed += 1
                else:
                    failed += 1

        report = write_test_report(
            self,
            profile_name,
            expected,
            known,
            tests,
            passed,
            failed,
        )

        return {
            "ok": True,
            "passed": passed,
            "failed": failed,
            "tests": tests,
            "report": report,
        }


class TesterGuiHandler(BaseHTTPRequestHandler):
    state = TesterState()

    def log_message(self, fmt, *args):
        return

    def do_GET(self):
        try:
            if self.path == "/" or self.path.startswith("/?"):
                write_html(self)
                return
            if self.path == "/fault-table":
                write_fault_table(self)
                return
            if self.path == "/api/profiles":
                profiles = load_profiles()
                write_json(self, 200, {
                    "ok": True,
                    "names": sorted(profiles.keys()),
                })
                return
            if self.path == "/api/history":
                write_json(self, 200, {
                    "ok": True,
                    "runs": load_report_history(10),
                })
                return
            if self.path.startswith("/reports/"):
                write_report_file(self, self.path[len("/reports/"):])
                return
            if self.path == "/api/ports":
                ports = []
                if list_ports is not None:
                    for item in list_ports.comports():
                        ports.append({
                            "device": item.device,
                            "description": item.description,
                        })
                write_json(self, 200, {"ok": True, "ports": ports})
                return
            if self.path == "/api/state":
                write_json(self, 200, {
                    "ok": True,
                    "connected": self.state.is_connected(),
                    "port": self.state.port,
                    "baud": self.state.baud,
                    "timeout": self.state.timeout,
                })
                return
            write_json(self, 404, {"ok": False, "error": "Not found"})
        except Exception as exc:
            write_json(self, 500, {"ok": False, "error": str(exc)})

    def do_POST(self):
        try:
            payload = read_json(self)
            if self.path == "/api/connect":
                self.state.connect(
                    payload.get("port"),
                    parse_int(payload.get("baud", DEFAULT_BAUD)),
                    float(payload.get("timeout", DEFAULT_TIMEOUT_S)),
                )
                write_json(self, 200, {"ok": True})
                return
            if self.path == "/api/disconnect":
                self.state.disconnect()
                write_json(self, 200, {"ok": True})
                return
            if self.path == "/api/command":
                command = payload.get("command", "")
                expected = payload.get("expected") or None
                line, kind, data = self.state.request(command, expected)
                write_json(self, 200, {
                    "ok": True,
                    "line": line,
                    "kind": kind,
                    "data": data,
                })
                return
            if self.path == "/api/snapshot":
                write_json(self, 200, {
                    "ok": True,
                    "responses": self.state.snapshot(),
                })
                return
            if self.path == "/api/stimulus":
                write_json(self, 200, self.state.apply_stimulus(payload))
                return
            if self.path == "/api/stimulus/clear":
                write_json(self, 200, self.state.clear_stimulus())
                return
            if self.path == "/api/profiles/load":
                profiles = load_profiles()
                name = payload.get("name", "")
                if name not in profiles:
                    raise ValueError("Profile not found")
                write_json(self, 200, {
                    "ok": True,
                    "name": name,
                    "profile": profiles[name],
                })
                return
            if self.path == "/api/profiles/save":
                name = str(payload.get("name", "")).strip()
                if not name:
                    raise ValueError("Profile name required")
                profiles = load_profiles()
                profiles[name] = payload.get("profile", {})
                save_profiles(profiles)
                write_json(self, 200, {
                    "ok": True,
                    "name": name,
                })
                return
            if self.path == "/api/auto-test":
                expected = get_expected(payload)
                known = get_known(payload)
                profile_name = str(payload.get("profile_name", "Ad hoc")).strip()
                write_json(
                    self,
                    200,
                    self.state.run_auto_test(expected, known, profile_name),
                )
                return
            write_json(self, 404, {"ok": False, "error": "Not found"})
        except Exception as exc:
            write_json(self, 500, {"ok": False, "error": str(exc)})


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Browser GUI for the Drone BMS PC UART tester."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    return parser


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    server = ThreadingHTTPServer((args.host, args.port), TesterGuiHandler)
    url = "http://%s:%d/" % (args.host, args.port)
    print("Drone BMS tester GUI: " + url)
    print("Close this terminal or press Ctrl+C to stop.")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        TesterGuiHandler.state.disconnect()
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
