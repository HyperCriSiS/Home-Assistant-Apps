# MCP-Zugriff im lokalen Netzwerk

MCP-Clients im lokalen Netzwerk erreichen MCPHub standardmäßig über **Host-Port 3001**:

```text
http://<HA-IP>:3001/mcp
Authorization: Bearer <KEY>
```

Statt `/mcp` sind auch `/mcp/<gruppe>`, `/mcp/<server>` und `/mcp/$smart` möglich. Den Bearer-Key in MCPHub unter **Keys** anlegen; dort lässt er sich auf einzelne Server oder Gruppen beschränken.

## Was Port 3001 kann und was nicht

Port 3001 ist ein **reiner MCP-Eingang**. Er leitet nur die MCP-Endpunkte weiter, und MCPHub prüft dabei den Bearer-Key. Die MCPHub-Weboberfläche, der Login, die Verwaltungs-API und die Tunnelseite sind dort **nicht** erreichbar (Antwort 404).

Die Weboberfläche öffnest du ausschließlich über die Home-Assistant-Seitenleiste (Ingress), angemeldet mit deinem Home-Assistant-Konto. Die gleiche Einschränkung gilt für andere Apps im internen Home-Assistant-Netzwerk.

## Netzwerkport ändern

1. In Home Assistant **Einstellungen → Apps → MCPHub → Netzwerk** öffnen.
2. Falls der Port nicht angezeigt wird, **„Deaktivierte Ports einblenden“** aktivieren.
3. Links steht der Host-Port, standardmäßig **3001**. Bei einer Portkollision einen anderen freien Port wählen, speichern und die App neu starten. `3001/tcp` rechts ist der feste interne Containerport, nicht die Eingabe.
4. Zum Deaktivieren das Host-Port-Feld leeren.

## Sicherheit

Die Verbindung nutzt unverschlüsseltes HTTP, der Bearer-Key wird also im Klartext übertragen. Nur in vertrauenswürdigen lokalen Netzen verwenden. Für den Zugriff von unterwegs den OpenAI-Tunnel oder die separate Cloudflared- bzw. Tailscale-App nutzen, die an diesen Port weiterleiten; der LAN-Port selbst wird nicht automatisch ins Internet weitergeleitet.
