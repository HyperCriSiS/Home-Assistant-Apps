(() => {
  "use strict";
  // Only the Home Assistant Ingress route offers this administrative link.
  // The LAN MCP gateway never serves MCPHub's web interface at all.
  const match = location.pathname.match(/^(.*\/api\/hassio_ingress\/[^/]+)(?:\/|$)/);
  if (!match) return;
  const destination = match[1] + "/_mcphub_tunnels/";
  const ID = "mcphub-ha-tunnel-link";

  const create = () => {
    const link = document.createElement("a");
    link.id = ID;
    link.href = destination;
    link.textContent = "Remote access";
    link.title = "Open remote access status and control";
    link.setAttribute("aria-label", "Open remote access status and control");
    return link;
  };

  const mount = () => {
    if (document.getElementById(ID)) return;
    const topbar = document.querySelector(".hub-topbar");
    const link = create();
    if (topbar) {
      link.style.cssText =
        "display:inline-flex;align-items:center;flex-shrink:0;padding:6px 11px;" +
        "border-radius:7px;border:1px solid var(--hub-line);" +
        "background:var(--hub-surface);color:var(--hub-ink);" +
        "text-decoration:none;font-size:12px;font-weight:600";
      const controls = topbar.querySelector(".ml-auto");
      if (controls) controls.prepend(link);
      else topbar.append(link);
      return;
    }
    // Upstream layout changed: keep the link reachable as a small floating button.
    if (!document.body) return;
    link.style.cssText =
      "position:fixed;right:16px;bottom:16px;z-index:2147483000;padding:8px 13px;" +
      "border-radius:9px;border:1px solid #64748b88;background:Canvas;color:CanvasText;" +
      "text-decoration:none;font:600 12px system-ui,sans-serif;box-shadow:0 2px 8px #0003";
    document.body.append(link);
  };

  const start = () => {
    mount();
    new MutationObserver(() => {
      const existing = document.getElementById(ID);
      // Prefer the topbar once the SPA has rendered it.
      if (existing && existing.parentElement === document.body &&
          document.querySelector(".hub-topbar")) {
        existing.remove();
      }
      mount();
    }).observe(document.getElementById("root") || document.body, {
      childList: true, subtree: true
    });
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
