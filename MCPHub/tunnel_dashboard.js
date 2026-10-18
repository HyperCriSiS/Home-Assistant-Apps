"use strict";
const modes = ["openai"];
const stateNames = {
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
    text(card.querySelector('[data-field="configured"]'),
      typeof s.configured === "boolean" ? (s.configured ? "Yes" : "No") : "Unknown");
  text(card.querySelector('[data-field="connection"]'),
    s.transport_ready ? "Locally ready" : "Not ready");
  text(card.querySelector('[data-field="route"]'), s.route || "–");
  text(card.querySelector('[data-field="age"]'),
    typeof s.health_age_seconds === "number" ? "" + s.health_age_seconds + " s" : "–");
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
    for (const [name, item] of Object.entries(report.components || {})) {
      if (!item || typeof item !== "object") continue;
      const status = [item.status, item.state, item.reason_code].filter(Boolean).join(" · ");
      detailLine(title[name] || name, status || "No details", list);
    }
    if (!list.children.length) {
      message(target, "No component data available yet.");
      return;
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
    renderRemote(all.remote);
  } catch {
    for (const mode of modes) render(mode, {state:"unavailable"});
    renderRemote({});
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
      feedback(mode, action === "stop" ? "Tunnel stopped." :
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
const appStates = {
  started: "Running", stopped: "Stopped", error: "Error",
  not_installed: "Not installed", unknown: "Unknown"
};
const checkStates = {
  reachable: ["Reaches MCPHub", "success"],
  redirect: ["Redirected", "warning"],
  other_service: ["Answers, but not MCPHub", "error"],
  unreachable: ["Not reachable", "error"]
};
function remoteFeedback(message, error=false) { feedback("remote", message, error); }
function renderRemote(state) {
  const card = document.getElementById("t-remote");
  const s = state || {};
  const badge = card.querySelector(".badge");
  const check = s.check && checkStates[s.check.result];
  let tone = "neutral", name = "Not configured";
  if (s.external_url_invalid) { tone = "error"; name = "Invalid address"; }
  else if (s.external_url && check) { name = check[0]; tone = check[1]; }
  else if (s.external_url) { name = "Not checked"; }
  badge.dataset.tone = tone;
  text(badge, name);
  text(card.querySelector('[data-field="external-url"]'),
    s.external_url || (s.external_url_invalid ? "Invalid, see App configuration" : "Not configured"));
  text(card.querySelector('[data-field="check"]'), !check ? "Not checked" :
    check[0] + (typeof s.check.age_seconds === "number" ? " · " + s.check.age_seconds + " s ago" : ""));
  const gw = s.gateway || {};
  const port = gw.host_port;
  text(card.querySelector('[data-field="gateway"]'), port ?
    (gw.host_ip || "<Home Assistant IP>") + ":" + port : "Host port disabled (Network settings)");
  for (const key of ["cloudflared", "tailscale"]) {
    const app = (s.apps || {})[key] || {};
    text(card.querySelector('[data-field="' + key + '"]'),
      (appStates[app.state] || "Unknown") + (app.version ? " · " + app.version : "") +
      (app.update_available ? " · update available" : ""));
    const link = card.querySelector('[data-link="' + key + '"]');
    if (app.link && /^https:\/\/my\.home-assistant\.io\//.test(app.link)) link.href = app.link;
    text(link, app.state === "not_installed" ? "Install App ↗" : "Open App ↗");
  }
  const target = "http://" + (gw.host_ip || "<Home Assistant IP>") + ":" + (port || 3001);
  let hostname = "mcp.example.com";
  try { if (s.external_url) hostname = new URL(s.external_url).hostname; } catch { /* keep example */ }
  text(document.getElementById("cloudflare-entry"),
    "- hostname: " + hostname + "\n  service: " + target);
  text(document.getElementById("tailnet-url"),
    "http://<Home Assistant Tailscale name>:" + (port || 3001) + "/mcp");
  text(document.getElementById("funnel-command"),
    "/opt/tailscale funnel --bg --https=8443 http://127.0.0.1:" + (port || 3001));
}
async function copyFrom(button) {
  const source = document.getElementById(button.dataset.copy);
  const value = source.textContent;
  if (navigator.clipboard && navigator.clipboard.writeText) {
    try { await navigator.clipboard.writeText(value); remoteFeedback("Copied."); return; }
    catch { /* Clipboard unavailable in non-secure contexts. */ }
  }
  let field = button.nextElementSibling;
  if (!field || !field.classList.contains("copy-fallback")) {
    field = document.createElement("textarea");
    field.className = "copy-fallback"; field.readOnly = true; field.rows = 3;
    button.after(field);
  }
  field.value = value; field.select();
  remoteFeedback("Select and copy the text manually.");
}
for (const button of document.querySelectorAll("button[data-copy]"))
  button.addEventListener("click", () => copyFrom(button));
document.getElementById("remote-check").addEventListener("click", async () => {
  const button = document.getElementById("remote-check");
  button.disabled = true;
  remoteFeedback("Checking the external address without credentials…");
  try {
    const response = await fetch("api/remote/check", {
      cache: "no-store", headers: {"X-MCPHub-Tunnel-Control": "1"}
    });
    if (response.status === 409) throw Error(await response.text());
    if (!response.ok) throw Error("HTTP " + response.status);
    const report = await response.json();
    const state = checkStates[report.result] || ["Unknown result", "warning"];
    const detail = report.result === "redirect" && report.detail ? " → " + report.detail :
      report.result === "other_service" && report.status ? " (HTTP " + report.status + ")" :
      report.result === "unreachable" && report.detail ? " (" + report.detail + ")" : "";
    remoteFeedback(state[0] + detail, state[1] === "error");
    await refresh();
  } catch (error) {
    remoteFeedback(error.message || "Check failed.", true);
  } finally { button.disabled = false; }
});

refresh();
setInterval(refresh, 10000);