# Calibre AIO Dokumentation

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

Alle Optionen mit ihren Standardwerten:

```yaml
library_theme: modern
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

### `library_theme`

`modern` (Standard) wendet das eigene dunkle Design der App mit Goldakzenten auf CWA an; `upstream`
behält das Originaldesign von CWA. Nach einer Änderung die App neu starten. Das Design ändert nur
das Aussehen, nicht Bibliotheksdaten, Sortierlogik oder Berechtigungen. Shelfmark behält seine
native Oberfläche; die gemeinsame Navigation verwendet passende Farben.

### `start_page`

Startansicht, `library` (Bibliothek, Standard) oder
`shelfmark` (Entdecken). Die kompakte Navigation nennt die Bibliothek immer
zuerst. Nach einer Änderung die App neu starten und die Weboberfläche erneut
öffnen.

### `library_dir`

Bibliothekspfad relativ zu `/share`. Der Wert muss ein
relativer Pfad ohne `.`- oder `..`-Segmente sein; ein leerer oder absoluter
Wert verhindert den Start.

Die Bibliothek ist nie Teil der Sicherung dieser App, und keine Option der App
kann das ändern: Home Assistant sichert `/share` nur über den Ordner **Share**
einer Sicherung, und der gilt für den gemeinsamen Ordner aller Apps zusammen.
Wähle **Share** an, um die Bibliothek einzuschließen, oder sichere sie
anderweitig. Siehe [Persistenz und Sicherungen](#persistenz-und-sicherungen).

### `ingest_dir`

Übergabepfad für fertige Bücher relativ zu `/share`, mit
denselben Regeln. Er darf weder der Bibliotheksordner sein noch darin liegen
oder ihn enthalten, und sollte nicht der aktive Downloadordner einer anderen
App sein.

### `network_share_mode`

Regelmäßige Prüfung statt Dateisystemereignissen für
SMB/NFS.

### `shelfmark.external_bypass_url`

Optionaler HTTP(S)-Endpunkt eines
kompatiblen externen Browser-Challenge-Dienstes. Leer lassen, um das
enthaltene Chromium zu nutzen und den Bypass in den Shelfmark-Einstellungen
zu konfigurieren. Ein Wert sperrt diese Einstellungen auf den externen
Dienst. Die App enthält keinen Tor- oder VPN-Stack; ausgehendes Routing wird
separat konfiguriert.

### `sso.enabled`

Muss in dieser AIO-Version `true` bleiben. Beide Anwendungen
sind nur über Ingress erreichbar; native Logins und Geräte-Clients werden
nicht veröffentlicht.

### `sso.admin_username`

HA-Anmeldename, exakt und unter Beachtung der
Groß-/Kleinschreibung. Den Namen eingeben, mit dem Du Dich bei HA anmeldest,
nicht den Anzeigenamen oder eine ID. Leer öffnet die Einrichtung; bis zur
Konfiguration erhält niemand Administratorrechte. Diese Option wählt den
Administrator in beiden Anwendungen; andere HA-Benutzer erhalten normale
Konten.

### `sso.admin_account`

Name des vorhandenen CWA-Administratorkontos (Standard
`admin`). Die erste CWA-Datenbank legt dieses Konto an. Ein fehlendes Konto
oder ein Konto ohne Administratorrechte verhindert den Start von CWA. Diese
Option wählt keine Shelfmark-Konten.

### `sso.auto_create_users`

CWA-Lesekonten für normale HA-Benutzer anlegen. Bei
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

Über das **+**-Menü der Bibliothek lassen sich Dateien hochladen oder mit
**Ordner hinzufügen …** ein Ordner wählen. Die Ordnerauswahl nimmt unterstützte
E-Book-Dateien auch aus Unterordnern mit; andere Dateitypen werden übersprungen.
Die Bücher durchlaufen den normalen Upload- und Importweg. Calibre ordnet die
Bibliothek selbst; die Ordnerstruktur der Quelle wird nicht als Regale
übernommen.

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
| CWA-Sicherheitskopien verarbeiteter Bücher | `/data/config/processed_books` |
| CWA-Cover-Vorschaubilder (nicht gesichert) | `/data/config/thumbnails` |
| Shelfmark-Einstellungen, Konten und Geheimnisse | `/data/shelfmark` |
| Shelfmark-Cover-Cache der Suchergebnisse (nicht gesichert) | `/data/shelfmark/covers` |
| Shelfmark-Zwischenspeicher und Logs (nicht gesichert) | `/data/shelfmark-staging`, `/data/shelfmark-logs` |
| Shelfmark-Hörbücher | `/data/shelfmark-audiobooks` |
| E-Book-Bibliothek | `/share/<library_dir>` |
| Übergabe fertiger Bücher | `/share/<ingest_dir>` |

> [!WARNING]
> Eine HA-Sicherung dieser App enthält nur den privaten Ordner `/data`:
> CWA-Zustand, Shelfmark-Einstellungen und Hörbücher. Die E-Book-Bibliothek und
> der Übergabeordner liegen unter `/share` und sind **nie Teil der
> App-Sicherung**. Sie gehören zum Ordner **Share** einer HA-Sicherung: Wähle
> **Share** an, um die Bibliothek einzuschließen, oder nimm ihn heraus, wenn Du
> sie anderweitig sicherst.

Die App-Sicherung lässt alles aus, was nach einer Wiederherstellung neu
entsteht oder nicht gebraucht wird: CWAs Cover-Vorschaubilder (beim ersten
Aufruf und durch die nächtliche Aufgabe aus den Bibliothekscovern neu erzeugt),
Shelfmarks Cover-Cache der Suchergebnisse (standardmäßig bis 500 MB, bei der
nächsten Suche neu geladen), Caches, Logs, temporäre Konvertierungsdateien,
Laufzeitmarkierungen, Shelfmarks Download-Zwischenspeicher und CWAs Kopien in
`processed_books/imported`, die Dateien der Bibliothek doppeln.

Der Rest von `processed_books` bleibt in der Sicherung, weil es ihn sonst
nirgends gibt: Originale vor einer automatischen Konvertierung (`converted`)
oder EPUB-Reparatur (`fixed_originals`), gescheiterte Importe (`failed`) und
beim Auflösen von Duplikaten entfernte Bücher (`duplicate_resolutions`). Wer
diese Kopien nicht möchte, schaltet in den CWA Settings die automatischen
Sicherungen von Importen und Konvertierungen ab. Diese App hat
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
bestätigt nur die Zustellung in den Importordner. Die App repariert die
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
