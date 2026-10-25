# Calibre AIO konfigurieren

Deutsch | [English](DOCS.md)

Starte die App und öffne sie innerhalb von Home Assistant. Beim ersten Aufruf
kannst Du **Angemeldeten Administrator übernehmen und neu starten** wählen.
Home Assistant prüft Deine Administratorberechtigung und speichert Deinen
HA-Anmeldenamen. Öffne die Oberfläche nach dem Neustart erneut. Die App erhält
dafür keinen zusätzlichen HA-API-Zugriff. Falls die direkte Übernahme in Deinem
Browser nicht verfügbar ist, trage Deinen HA-Anmeldenamen in der
App-Konfiguration unter **SSO → Administrator** ein und starte die App neu.

**Bibliothek** öffnet Calibre-Web Automated zum Lesen und Verwalten.
**Entdecken** öffnet Shelfmark für Suche, Anfragen, Downloads und deren
Einstellungen. Die schmale gemeinsame Navigation bleibt sichtbar.

## Optionen

- **Startseite**: `library` öffnet zuerst die Bibliothek (Standard),
  `shelfmark` öffnet zuerst Entdecken. Änderungen benötigen einen Neustart.
- **Bibliotheksordner**: Pfad relativ zu `/share` für die Calibre-Bibliothek.
- **Importordner**: Pfad relativ zu `/share` für abgeschlossene Buchdownloads.
  Einen anderen Ordner als die Bibliothek verwenden.
- **Netzwerkfreigabe**: Für SMB/NFS regelmäßige Prüfung statt
  Dateisystemereignissen verwenden.
- **Shelfmark → Externer Browser-Dienst**: optionaler HTTP(S)-Dienst für
  Browser-Challenges. Für Debrid-Clients nicht erforderlich.
- **SSO → SSO aktivieren**: aktiviert lassen; beide Anwendungen sind
  ausschließlich über HA Ingress erreichbar.
- **SSO → Administrator**: HA-Anmeldename, exakt und unter Beachtung der
  Groß-/Kleinschreibung. Kein Anzeigename und keine Benutzer-ID. Leer öffnet
  die Einrichtung; bis zur Konfiguration erhält niemand Administratorrechte.
- **SSO → CWA-Administratorkonto**: vorhandenes CWA-Administratorkonto,
  standardmäßig `admin`. Betrifft nicht das Shelfmark-Konto.
- **SSO → Benutzer automatisch anlegen**: normale CWA-Lesekonten für andere
  HA-Benutzer erstellen. Shelfmark verwaltet deren Anfragekonten unabhängig.

Die technischen YAML-Schlüssel bleiben für bestehende Konfigurationen gleich.
Die Beschriftungen folgen Deiner HA-Profilsprache (Deutsch oder Englisch).
Die gemeinsame Navigation und Einrichtung verwenden die HA-Sprache, ersatzweise
die Browsersprache. CWA bietet eine eigene Spracheinstellung pro Benutzer.
Die hier verwendete Shelfmark-Version 1.4.0 hat eine englische Oberfläche;
Buch-Sprachfilter ändern deren Sprache nicht. Die statische Dokumentation hat
separate deutsche und englische Seiten.

## Konten und Berechtigungen

Der konfigurierte Anmeldename wird automatisch an seine stabile HA-ID gebunden;
ein neu angelegtes Konto mit gleichem Namen übernimmt diese Bindung nicht.
Beide Anwendungen verwenden dieselbe Bindungsdatenbank unter
`/data/config/ha_admin_bindings.db`. Andere Benutzer erhalten normale Rechte.
Die Bibliothek wird gemeinsam genutzt, entsprechend den CWA-Inhaltsfreigaben.
Die Administratorzuweisung bleibt unabhängig von späteren HA-Rollenänderungen:
Bei Entzug der HA-Administratorrolle gegebenenfalls auch diese App-Option ändern
und neu starten. Gelieferte Gruppen-Header werden nicht als Rollenquelle vertraut.

## Downloads und Sicherungen

Suchquellen, Real-Debrid und andere Download-Clients werden in Shelfmark selbst
konfiguriert. Zugangsdaten bleiben in dessen privater Konfiguration. Downloads
werden zunächst unter `/data/shelfmark-staging` abgelegt und danach über den
Importordner an CWA übergeben. Shelfmark liest die Calibre-Datenbank zur
Bestandsprüfung; CWA übernimmt Import und Konvertierung. Hörbücher werden separat
unter `/data/shelfmark-audiobooks` gespeichert. Audiobookshelf ist nicht enthalten.
Externe Download-Clients benötigen passende gemeinsame Pfade unter `/share`
und gegebenenfalls Shelfmark-Pfadzuordnungen.

HA sichert die privaten App-Daten: CWA unter `/data/config`, Shelfmark unter
`/data/shelfmark`. Die Bibliothek unter `/share` zusätzlich sichern oder den
Share-Ordner in die HA-Sicherung aufnehmen. Es werden keine Backend-Ports im
Netz veröffentlicht. Externe Kobo-/KOReader-Synchronisation gehört nicht zum
Funktionsumfang dieser Ingress-App.

## Dev-Version und Fehlersuche

Im bestehenden `#dev-store` **Calibre AIO (Dev)** installieren. Die Quellen
kommen aus `dev-calibre`; die Veröffentlichung auf `main` ist ein separater
Schritt nach dem Test. Die Standardordner der Dev-Version sind von der stabilen
App getrennt. Zwei laufende Installationen dürfen nicht dieselbe Bibliothek
oder denselben Importordner bearbeiten.

Bei Problemen App-Logs nach dem Neustart prüfen. 403 bedeutet fehlende
Identität oder Berechtigung; 502 deutet meist auf einen noch startenden Backend-
Prozess hin. Keine Tokens oder vollständigen Ingress-Adressen weitergeben.
Weitere technische Angaben: [Updates](UPDATING.md), [Tests](TESTING.md).
