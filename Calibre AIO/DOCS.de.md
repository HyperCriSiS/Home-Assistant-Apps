# Calibre AIO konfigurieren

Deutsch | [English](DOCS.md)

## Erste Schritte

Öffne Calibre AIO innerhalb von Home Assistant. Beim ersten Aufruf ohne
konfigurierten App-Administrator wird Dein angemeldetes HA-Administratorkonto
automatisch übernommen und die App neu gestartet. Die Oberfläche lädt
automatisch neu, sobald beide Anwendungen bereit sind. HA prüft Deine
Administratorberechtigung, bevor Dein Anmeldename gespeichert wird. Alternativ
trägst Du ihn manuell in der App-Konfiguration ein. Die App erhält dafür keinen
zusätzlichen HA-API-Zugriff.
**Entdecken** enthält Shelfmark mit Suche, Anfragen, Downloads und den
Einstellungen für Quellen und Clients. **Bibliothek** enthält die Bibliotheks-,
Lese- und Verwaltungsfunktionen von CWA. Die Navigation bleibt in beiden
Anwendungen sichtbar. Beide nativen Oberflächen bleiben vollständig erhalten.

Shelfmarks Link „Go To Library“ öffnet CWA bei einem normalen Klick innerhalb
dieser gemeinsamen Oberfläche; die Navigationsleiste bleibt erhalten.

Der in `sso.admin_username` konfigurierte HA-Anmeldename erhält
Administratorzugriff auf beide Anwendungen. Andere HA-Benutzer bekommen ein
eigenes CWA-Lese- und Downloadkonto sowie ein Shelfmark-Konto für Anfragen;
Shelfmarks Anfrageregeln je Quelle bestimmen, was sie anfragen oder laden
dürfen. Die gemeinsame Calibre-Bibliothek ist entsprechend den
CWA-Inhaltsfreigaben sichtbar; es gibt keine private Bibliothek je Benutzer.
CWA-Administratoren teilen sich das gewählte CWA-Administratorkonto. Shelfmark
führt getrennte HA-Identitäten.

## Optionen

Das Design **Modern** verwendet zurückhaltende Graphitflächen und gedämpfte
Goldakzente aus dem Modern-Skin des Wormhole Connectors (Designs), abgeleitet
von PlexTraktSync. Bibliothekskarten, Sortierelemente und Formulare brauchen
weniger Platz. Sortierkriterien haben eigene Symbole (Titel, Autor,
Hinzugefügt, Veröffentlichung, Serie oder Downloads); ein separater Pfeil zeigt
die Richtung. Buchstaben werden nie gespiegelt. Tooltips bei Hover und Fokus
behalten die vollständigen CWA-Beschreibungen. Auf Telefonen bricht die
Werkzeugleiste um und die Berührungsflächen bleiben größer. Auf dem Desktop ist
die Sortierung in der Titelzeile zentriert. Listenmarker und Buchstabenfilter
bleiben an ihrer nativen Position mit kompakter Größe und eingerücktem Rand.

`library_theme: modern` ist der Standard, auch für bestehende Konfigurationen.
Setze `library_theme: upstream` und starte die App neu, um das Originaldesign
von CWA zu verwenden. Das Design ändert nur das Aussehen, nicht
Bibliotheksdaten, Sortierlogik oder Berechtigungen. Shelfmark behält seine
native Oberfläche; die gemeinsame Navigation verwendet passende Farben.

```yaml
start_page: library
library_dir: calibre-aio/library
ingest_dir: calibre-aio/ingest
network_share_mode: false
shelfmark:
  external_bypass_url: ""
sso:
  enabled: true
  admin_username: dein_ha_anmeldename
  admin_account: admin
  auto_create_users: true
```

- `start_page`: Startansicht, `library` (Bibliothek, Standard) oder
  `shelfmark` (Entdecken). Die kompakte Navigation nennt die Bibliothek immer
  zuerst. Nach einer Änderung die App neu starten und die Weboberfläche erneut
  öffnen.
- `library_dir`: Bibliothekspfad relativ zu `/share`. Der Wert muss ein
  relativer Pfad ohne `.`- oder `..`-Segmente sein; sonst startet die App nicht.
- `ingest_dir`: Übergabepfad für fertige Bücher relativ zu `/share`, mit
  denselben Regeln. Nicht denselben Pfad wie für die Bibliothek oder den
  aktiven Downloadordner einer anderen App verwenden.
- `network_share_mode`: regelmäßige Prüfung statt Dateisystemereignissen für
  SMB/NFS.
- `shelfmark.external_bypass_url`: optionaler HTTP(S)-Endpunkt eines
  kompatiblen externen Browser-Challenge-Dienstes. Leer lassen, um das
  enthaltene Chromium zu nutzen und den Bypass in den Shelfmark-Einstellungen
  zu konfigurieren. Ein Wert sperrt diese Einstellungen auf den externen
  Dienst. Die App enthält keinen Tor- oder VPN-Stack; ausgehendes Routing wird
  separat konfiguriert.
- `sso.enabled`: muss in dieser AIO-Version `true` bleiben. Beide Anwendungen
  sind nur über Ingress erreichbar; native Logins und Geräte-Clients werden
  nicht veröffentlicht.
- `sso.admin_username`: HA-Anmeldename, exakt und unter Beachtung der
  Groß-/Kleinschreibung. Den Namen eingeben, mit dem Du Dich bei HA anmeldest,
  nicht den Anzeigenamen oder eine ID. Leer öffnet die Einrichtung; bis zur
  Konfiguration erhält niemand Administratorrechte. Diese Option wählt den
  Administrator in beiden Anwendungen; andere HA-Benutzer erhalten normale
  Konten.
- `sso.admin_account`: Name des vorhandenen CWA-Administratorkontos (Standard
  `admin`). Die erste CWA-Datenbank legt dieses Konto an. Ein fehlendes Konto
  oder ein Konto ohne Administratorrechte verhindert den Start von CWA. Diese
  Option wählt keine Shelfmark-Konten.
- `sso.auto_create_users`: CWA-Lesekonten für normale HA-Benutzer anlegen. Bei
  `false` erlaubt CWA nur vorhandene gebundene Leser und gewählte
  Administratoren. Shelfmarks Benutzeranlage über den Proxy bleibt an die
  HA-Identität gebunden; diese Option schaltet deren Anfragekonten nicht ab.

Die App verlässt sich auf die authentifizierten Benutzer-ID- und
Anmeldenamen-Header des Supervisors, verfügbar ab Supervisor 2026.10. Sie
vertraut keinen Gruppen-Headern und braucht keinen HA-API-Zugriff. Der gewählte
Anmeldename wird automatisch an seine HA-ID in der privaten Datei
`/data/config/ha_admin_bindings.db` gebunden; ein Ersatzkonto mit demselben
Namen übernimmt diese Bindung nicht automatisch. Beide Anwendungen verwenden
dieselbe Bindung. Nimm sie in App-Sicherungen auf.

Diese Zuweisung ist unabhängig von der HA-Administratorrolle. Wenn Du jemandem
die HA-Administratorrolle entziehst, ändere auch `sso.admin_username` und
starte die App neu, falls der Calibre-AIO-Administratorzugriff enden soll. Ein
deaktiviertes HA-Konto verhindert weiterhin neue authentifizierte
Ingress-Sitzungen. Ein CWA- oder Shelfmark-Cookie, ein API-Schlüssel, ein
Anzeigename oder ein mitgelieferter Gruppen-Header kann die HA-Identität nicht
ersetzen. Leser sehen den Shelfmark-Einrichtungsassistenten für
Administratoren nicht.

## Downloads und Bibliotheksübergabe

Quellen sowie Real-Debrid und andere Clients werden in den
Shelfmark-Einstellungen konfiguriert, nicht im HA-YAML. Zugangsdaten bleiben in
Shelfmarks privaten, persistenten Einstellungen. Real-Debrid übernimmt
Torrent- und Magnet-Downloads; Suchquellen werden weiterhin benötigt. Externe
Torrent- oder Usenet-Clients brauchen Pfade, die dieser Container sieht. Nur
`/share` wird vom Host eingebunden; verwende gemeinsame `/share`-Pfade und
Shelfmarks Remote-Pfadzuordnungen, falls ein solcher Client andere Pfade meldet.

Shelfmark legt Downloads unter `/data/shelfmark-staging` ab und veröffentlicht
fertige E-Books nach `/cwa-book-ingest`, hinterlegt durch `/share/<ingest_dir>`.
Die Hardlink-Zustellung ist deaktiviert, weil CWA die Importdateien verbraucht.
Shelfmark liest Calibres `metadata.db`, um bereits vorhandene Bücher zu
markieren; es schreibt nicht direkt in die Bibliotheksdatenbank. CWA übernimmt
den eigentlichen Import und die Konvertierung. Die Admin-Seite **Downloads** in
Calibre Web gruppiert stattdessen aufgezeichnete Downloads nach Benutzer. Sie
füllt sich, wenn Benutzer Bibliotheksbücher über Calibre Web laden oder an
einen E-Reader senden; Shelfmark-Importe erscheinen dort nicht. Hörbücher
landen im separaten Speicher `/data/shelfmark-audiobooks`; CWA ist kein
Hörbuchserver. Audiobookshelf ist nicht enthalten.

## Persistenz und Sicherungen

| Daten | Containerpfad |
| --- | --- |
| CWA-Zustand und Kontobindungen | `/data/config` (über `/config`) |
| Shelfmark-Einstellungen, Konten und Geheimnisse | `/data/shelfmark` |
| Shelfmark-Zwischenspeicher | `/data/shelfmark-staging` |
| E-Book-Bibliothek | `/share/<library_dir>` |
| Übergabe fertiger Bücher | `/share/<ingest_dir>` |

HA sichert die privaten App-Daten. Sichere die Bibliothek unter `/share`
separat oder nimm den Share-Ordner in Deine HA-Sicherung auf. Diese App hat
einen eigenen Slug und übernimmt nicht die privaten Datenbanken der früheren
CWA-Testinstallation. Teste mit den getrennten Standardordnern, bevor Du
vorhandene Bibliotheksdaten kopierst.

Es werden keine Backend-Ports veröffentlicht. CWA bindet `127.0.0.1:8083`,
Shelfmark `127.0.0.1:8085`; der nginx-Ingress auf 8084 akzeptiert nur den
Supervisor unter `172.30.32.2`. CWA-OAuth, Magic Links sowie die Kobo- und
KOReader-Authentifizierung bleiben unter SSO gesperrt. Eine externe
Reader-Synchronisation gehört nicht zum Umfang dieser AIO-Version.

## Fehlersuche

Wenn Shelfmark einen abgeschlossenen Download meldet, das Buch aber in der
Bibliothek fehlt, prüfe das anschließende CWA-Importprotokoll.
`apsw.ReadOnlyError: attempt to write a readonly database` bedeutet, dass CWA
die Bibliotheksdatenbank nicht schreiben kann; die frühere Shelfmark-Meldung
bestätigt nur die Zustellung in den Importordner. Version 1.1.4 repariert die
Besitzrechte lokaler Bibliotheken nach der Initialisierung, auch bei
bestehenden Installationen, und prüft den Schreibzugriff als UID/GID 911 vor
dem Start von CWA. Aktualisiere die App, starte sie neu und wiederhole den
Import der betroffenen Datei. Bei `network_share_mode: true` bleiben die
Besitzrechte unverändert; die Freigabe muss UID/GID 911 Schreibzugriff auf
`metadata.db` und das Bibliotheksverzeichnis gewähren, damit SQLite seine
Journaldateien anlegen kann. Lösche `metadata.db` nicht und lege sie nicht neu
an, um einen Berechtigungsfehler zu beheben.

Prüfe die App-Protokolle nach einem Neustart. Der CWA-Starter bestätigt die
konfigurierte Regel für den HA-Anmeldenamen. Ein leeres `sso.admin_username`
öffnet die automatische Einrichtung in HA für einen HA-Administrator.
Bestehende Zuweisungen werden von der Einrichtung nie überschrieben. Schlägt
die Einrichtung fehl, nennt die Meldung den fehlgeschlagenen Schritt;
wiederhole sie oder konfiguriere den Anmeldenamen manuell und starte neu. Der
Start von Shelfmark ist getrennt; ein Backend kann nicht erreichbar sein,
während das andere neu startet. 403 bedeutet, dass der Anfrage eine
vertrauenswürdige HA-Identität oder Berechtigung fehlt; 502 bedeutet
normalerweise, dass das Ziel-Backend noch nicht gestartet ist. Gib nur
relevante Protokollauszüge weiter; vermeide API-Tokens oder Ingress-Adressen
mit Sitzungskennungen.

Bei jedem Start fragt das Init-Skript von CWA selbst `api.github.com` nach der
neuesten CWA-Version für seinen Aktualisierungshinweis. Die Anfrage hat einen
kurzen Timeout, und der Start läuft ohne Internetzugang weiter; eine
zugehörige Warnung im Protokoll ist harmlos. Diese App aktualisiert CWA nur
über ihre eigenen Releases.

Die Upstream-Versionen stehen in `upstream.json`. Alle Aktualisierungen sollen
über den in [UPDATING.md](UPDATING.md) beschriebenen Manifest- und
Update-Ablauf laufen, mit einer Sicherung, bevor eine echte Installation
aktualisiert wird.

## Sprachen und Entwicklungsversionen

HA zeigt die Optionsbeschriftungen in Deiner Profilsprache (Deutsch oder
Englisch). Die AIO-Navigation und die Einrichtung verwenden die HA-Sprache,
ersatzweise die Browsersprache. CWA hat eine eigene Spracheinstellung je
Benutzer. Die Shelfmark-Oberfläche ist englisch; Buch-Sprachfilter übersetzen
sie nicht. Die statische Dokumentation hat getrennte Sprachdateien.

Verwende das bestehende Repository `#dev-store` und installiere **Calibre AIO
(Dev)**. Es wird aus `dev-calibre` erzeugt; die Veröffentlichung auf `main`
ist ein separater Schritt nach dem Test. Die Standardordner für Bibliothek und
Import sind von der stabilen App getrennt. Zwei gleichzeitig laufende
Installationen dürfen nicht dieselbe Bibliothek oder denselben Importordner
verwenden.

## Installationsimages

Home Assistant lädt das versionierte GHCR-Image für seine Architektur. GitHub
Actions baut und testet beide Images, bevor ein Dev-Update angeboten wird. Der
erste Download kann groß sein; spätere Updates verwenden unveränderte
Image-Schichten wieder. Eine Registry-Anmeldung ist nicht nötig. Das
unterstützte Entwicklungsrepository ist `#dev-store`; `dev-calibre` ist ein
Integrationsbranch, kein Installationskanal.
