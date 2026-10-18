"use strict";
const modes = ["openai", "cloudflare", "tailscale"];
const stateNames = {
  gateway_ready: ["Gateway ready", "success", "The MCP gateway is ready; Funnel is managed separately."],
  ready: ["Ready", "success", "The local tunnel is connected."],
  starting: ["Starting", "warning", "Connecting…"],
  retrying: ["Retrying", "warning", "Reconnecting…"],
  degraded: ["Degraded", "warning", "The local connection is not ready."],
  stale: ["Check outdated", "warning", "The last status is outdated."],
  stopped: ["Stopped", "neutral", "The tunnel has stopped."],
  unavailable: ["Unavailable", "error", "The tunnel service is not responding."],
  error: ["Error", "error", "The tunnel could not be started."]
};
const title = {mcp:"MCP endpoint", "control-plane":"Control plane",
  "response-delivery":"Response delivery", queue:"Queue",
  proxy:"Proxy"};
let refreshing = false;
const busy = new Set();

async function api(path, opts) {
  const response = await fetch(path, {cache:"no-store", ...opts});
  if (!response.ok) throw Error("HTTP " + response.status);
  return response.json();
}
function label(s) {
  return stateNames[s] || ["Unknown", "neutral", "No definitive status is available."];
}
function text(el, value) {
  el.textContent = String(value === undefined || value === null ? "–" : value);
}
function feedback(mode, message, error=false) {
  const el = document.querySelector("#t-" + mode + " .feedback");
  text(el, message);
  el.dataset.error = error ? "true" : "false";
}
function render(mode, state) {
  const card = document.getElementById("t-" + mode);
  const s = state || {};
  const [name, tone, summary] = label(s.state);
  const badge = card.querySelector(".badge");
  badge.dataset.tone = tone;
  text(badge, name);
  text(card.querySelector(".summary"), s.last_error || summary);
  if (mode === "tailscale") {
    text(card.querySelector('[data-field="gateway"]'),
      s.gateway_ready ? "Ready in the App" : s.configured ? "Not ready" : "Disabled");
    text(card.querySelector('[data-field="funnel"]'), "External App · manual");
    text(card.querySelector('[data-field="route"]'), s.route || "–");
    text(card.querySelector('[data-field="https"]'),
      s.public_check === "gateway_answered" ? "Gateway answered" :
      s.public_check === "not_verified" ? "Not confirmed" : "Not checked");
    text(card.querySelector('[data-field="public-url"]'),
      s.public_url || (s.public_url_invalid ? "Invalid URL" : "Not configured"));
  } else {
    text(card.querySelector('[data-field="configured"]'),
      typeof s.configured === "boolean" ? (s.configured ? "Yes" : "No") : "Unknown");
  text(card.querySelector('[data-field="connection"]'),
    s.transport_ready ? "Locally ready" : "Not ready");
  text(card.querySelector('[data-field="route"]'), s.route || "–");
  text(card.querySelector('[data-field="age"]'),
    typeof s.health_age_seconds === "number" ? "" + s.health_age_seconds + " s" : "–");
  }
  for (const button of card.querySelectorAll("button[data-action]")) {
    const action = button.dataset.action;
    button.disabled = busy.has(mode) ||
      (action === "start" && (!s.configured || s.requested)) ||
      (action === "stop" && !s.requested) ||
      (action === "reload" && s.state === "unavailable");
  }
}
function message(container, str) {
  container.replaceChildren(document.createTextNode(str));
}
function detailLine(name, detail, container) {
  const item = document.createElement("li");
  const strong = document.createElement("b");
  text(strong, name);
  const sub = document.createElement("span");
  text(sub, detail);
  item.append(strong, sub);
  container.append(item);
}
async function loadDetails(mode, kind) {
  const card = document.getElementById("t-" + mode);
  const section = card.querySelector('details[data-panel="' + kind + '"]');
  if (!section.open) return;
  const target = section.querySelector(kind === "diagnostics" ? "[data-diagnostics]" : "[data-logs]");
  try {
    const report = await api("api/" + (kind === "logs" ? "logs/" : "diagnostics/") + mode);
    if (!section.open) return;
    if (kind === "logs") {
      text(target, Array.isArray(report.lines) && report.lines.length ?
        report.lines.join("\n") : "No logs are available yet.");
      return;
    }
    if (report.note) { message(target, report.note); return; }
    const list = document.createElement("ul");
    list.className = "diag-lines";
    if (mode === "tailscale") {
      message(target, report.note || "Tailscale diagnostics are available only in the Tailscale add-on.");
      return;
    }
    if (mode === "openai") {
      for (const [name, item] of Object.entries(report.components || {})) {
        if (!item || typeof item !== "object") continue;
        const status = [item.status, item.state, item.reason_code].filter(Boolean).join(" · ");
        detailLine(title[name] || name, status || "No details", list);
      }
      if (!list.children.length) {
        message(target, "No component data available yet.");
        return;
      }
    } else {
      for (const item of report.prechecks || []) {
        if (!item || typeof item !== "object") continue;
        const detail = [item.status, item.details, item.action].filter(Boolean).join(" · ");
        detailLine(item.component || "Network check", detail || "No details", list);
      }
      if (!list.children.length) {
        message(target, "No network check available yet.");
        return;
      }
    }
    target.replaceChildren(list);
  } catch {
    message(target, "Details are temporarily unavailable.");
  }
}
async function refresh() {
  if (refreshing) return;
  refreshing = true;
  try {
    const all = await api("api/status");
    for (const mode of modes) render(mode, all[mode]);
  } catch {
    for (const mode of modes) render(mode, {state:"unavailable"});
  } finally { refreshing = false; }
}
for (const button of document.querySelectorAll("button[data-action]")) {
  button.addEventListener("click", async () => {
    const {mode, action} = button.dataset;
    if (busy.has(mode)) return;
    busy.add(mode);
    for (const control of document.querySelectorAll("#t-" + mode + " button[data-action]"))
      control.disabled = true;
    feedback(mode, "Running action…");
    try {
      await api("api/control/" + mode + "/" + action, {
        method:"POST",
        headers:{"Content-Type":"application/json", "X-MCPHub-Tunnel-Control":"1"},
        body:"{}"
      });
      feedback(mode, mode === "tailscale"
        ? (action === "stop" ? "Local MCP gateway stopped. Funnel unchanged." :
          "Local MCP gateway started. Funnel unchanged.")
        : action === "stop" ? "Tunnel stopped." :
          action === "reload" ? "Settings reloaded." : "Start requested.");
    } catch (error) {
      feedback(mode, "Action failed: " + error.message, true);
    } finally {
      busy.delete(mode);
      await refresh();
    }
  });
}
for (const section of document.querySelectorAll('details[data-panel="logs"], details[data-panel="diagnostics"]')) {
  section.addEventListener("toggle", () => {
    if (section.open) loadDetails(section.dataset.mode, section.dataset.panel);
  });
}
function keyMessage(message) {
  text(document.getElementById("key-message"), message);
}
async function keyRequest(path, method) {
  return api("api/client-key" + path, {
    method:method || "GET",
    headers:{"X-MCPHub-Tunnel-Control":"1",
      ...(method ? {"Content-Type":"application/json"} : {})},
    ...(method ? {body:"{}"} : {})
  });
}
document.getElementById("copy-key").addEventListener("click", async () => {
  const button = document.getElementById("copy-key");
  button.disabled = true;
  try {
    const data = await keyRequest("");
    if (!data.key) throw Error("Key unavailable");
    if (navigator.clipboard && navigator.clipboard.writeText) {
      try {
        await navigator.clipboard.writeText(data.key);
        keyMessage("Key copied to clipboard.");
        return;
      } catch { /* Clipboard unavailable in non-secure contexts. */ }
    }
    let field = document.getElementById("key-fallback");
    if (!field) {
      field = document.createElement("textarea");
      field.id = "key-fallback"; field.readOnly = true; field.rows = 2;
      button.parentElement.after(field);
    }
    field.value = data.key;
    field.select();
    keyMessage("Select and copy the key manually.");
  } catch {
    keyMessage("Client key is currently unavailable.");
  } finally { button.disabled = false; }
});
document.getElementById("rotate-key").addEventListener("click", async () => {
  if (!confirm("Rotate client key? The previous key will be invalidated immediately.")) return;
  const button = document.getElementById("rotate-key");
  button.disabled = true;
  try {
    await keyRequest("/rotate", "POST");
    const field = document.getElementById("key-fallback");
    if (field) field.remove();
    keyMessage("New key generated. Copy it again and update your MCP clients.");
  } catch {
    keyMessage("Key could not be rotated.");
  } finally { button.disabled = false; }
});

const funnelCommand = "/opt/tailscale funnel --bg --https=443 http://127.0.0.1:3002";
async function copyToClipboard(value) {
  if (!navigator.clipboard || !navigator.clipboard.writeText) return false;
  try { await navigator.clipboard.writeText(value); return true; }
  catch { return false; }
}
document.getElementById("copy-tailscale-command").addEventListener("click", async () => {
  const done = await copyToClipboard(funnelCommand);
  feedback("tailscale", done ? "CLI command copied." :
    "Clipboard unavailable. Copy the command above manually.", !done);
});
document.getElementById("tailscale-check").addEventListener("click", async () => {
  const button = document.getElementById("tailscale-check");
  button.disabled = true;
  feedback("tailscale", "Checking HTTPS without sending credentials…");
  try {
    const report = await api("api/tailscale/https-check", {
      headers: {"X-MCPHub-Tunnel-Control": "1"}
    });
    feedback("tailscale", report.result === "gateway_answered" ?
      "HTTPS gateway responded. Public Internet reachability is not confirmed." :
      "No confirmed HTTPS response from the MCP gateway.", report.result !== "gateway_answered");
    await refresh();
  } catch {
    feedback("tailscale", "Configure a valid Funnel URL in the app settings first.", true);
  } finally { button.disabled = false; }
});
document.getElementById("tailscale-copy-key").addEventListener("click", async () => {
  const button = document.getElementById("tailscale-copy-key");
  button.disabled = true;
  const target = document.getElementById("tailscale-key-message");
  try {
    const data = await api("api/tailscale/client-key", {
      headers: {"X-MCPHub-Tunnel-Control": "1"}
    });
    if (!data.key) throw Error("Missing key");
    if (await copyToClipboard(data.key)) {
      text(target, "Client key copied.");
    } else {
      let field = document.getElementById("tailscale-key-fallback");
      if (!field) {
        field = document.createElement("textarea");
        field.id = "tailscale-key-fallback"; field.readOnly = true; field.rows = 2;
        field.style.width = "100%";
        button.parentElement.after(field);
      }
      field.value = data.key; field.select();
      text(target, "Select and copy the key manually.");
    }
  } catch { text(target, "Client key could not be loaded."); }
  finally { button.disabled = false; }
});
document.getElementById("tailscale-rotate-key").addEventListener("click", async () => {
  if (!confirm("Rotate Tailscale client key? The previous key will immediately be invalidated.")) return;
  const button = document.getElementById("tailscale-rotate-key");
  button.disabled = true;
  try {
    await api("api/tailscale/client-key/rotate", {
      method: "POST", headers: {
        "Content-Type": "application/json", "X-MCPHub-Tunnel-Control": "1"
      }, body: "{}"
    });
    const field = document.getElementById("tailscale-key-fallback");
    if (field) field.remove();
    text(document.getElementById("tailscale-key-message"),
      "Key rotated. Copy the new key and update Claude.");
  } catch {
    text(document.getElementById("tailscale-key-message"), "Key rotation failed.");
  } finally { button.disabled = false; }
});

refresh();
setInterval(refresh, 10000);