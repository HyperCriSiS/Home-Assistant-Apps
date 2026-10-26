'use strict';

const $ = id => document.getElementById(id);
const all = selector => [...document.querySelectorAll(selector)];
const pages = {
  backups: ['Sicherungen', 'DEINE TRAKT-DATEN', 'Einzeln oder vollständig sichern, langfristig aufbewahren und gezielt wiederherstellen.'],
  overview: ['Übersicht', 'ALLES IM BLICK', 'Deine Bibliotheken, verbunden durch einen gemeinsamen Verlauf.'],
  connections: ['Verbindungen', 'DEINE KONTEN', 'Plex und Trakt einrichten. Zugangsdaten sicher in der App speichern.'],
  sync: ['Synchronisierung', 'DEINE REGELN', 'Wähle bewusst, welche Daten in welche Richtung fließen.'],
  libraries: ['Bibliotheken & Filter', 'DEINE AUSWAHL', 'Bestimme, welche Medien und Wiedergabegeräte berücksichtigt werden.'],
  advanced: ['Erweitert', 'FEINABSTIMMUNG', 'Zeitlimits, Metadaten und Protokollierung an deinen Server anpassen.'],
  analysis: ['Analyse & Freigabe', 'VOR DEM SCHREIBEN', 'Prüfe den Umfang, bevor du die Synchronisierung freigibst.'],
};
let snapshot = null, status = null, dirty = false, pending = false, online = false;
let toastTimer, deviceTimer, deviceExpires = 0, deviceInterval = 5, lastReport = '';
const fields = new Map();
function element(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
}
function field(parent, key, label, help, type = 'text', choices = null, limits = null) {
  const wrap = element('div', 'field');
  const title = element('label', '', label); title.htmlFor = 'setting-' + key;
  const input = element(choices ? 'select' : type === 'lines' ? 'textarea' : 'input');
  input.id = 'setting-' + key; input.dataset.setting = key;
  if (choices) choices.forEach(([value, name]) => {
    const option = element('option', '', name); option.value = value; input.append(option);
  });
  else if (type !== 'lines') input.type = type;
  if (limits) { input.min = limits[0]; input.max = limits[1]; input.step = 1; input.required = true; }
  if (type === 'text') input.maxLength = key === 'plex_username' ? 256 : 2048;
  if (type === 'lines') { input.rows = 4; input.placeholder = 'Ein Eintrag pro Zeile'; }
  if (key === 'plex_url') input.placeholder = 'http://192.168.1.10:32400';
  if (key === 'plex_username') input.placeholder = 'Dein Plex-Benutzername';
  const hint = element('p', 'field-help', help); hint.id = 'help-' + key;
  input.setAttribute('aria-describedby', hint.id);
  wrap.append(title, input, hint); parent.append(wrap); fields.set(key, { input, type });
}
function toggle(parent, key, label, help) {
  const row = element('label', 'toggle-row');
  const copy = element('div'); copy.append(element('span', 'toggle-title', label), element('p', '', help));
  const input = element('input', 'switch'); input.type = 'checkbox'; input.role = 'switch';
  input.id = 'setting-' + key; input.dataset.setting = key; input.setAttribute('aria-label', label);
  row.append(copy, input); parent.append(row); fields.set(key, { input, type: 'boolean' });
}
function group(target, title, description) {
  const card = element('article', 'card settings-group');
  card.append(element('h2', '', title), element('p', 'group-description', description));
  $(target + '-fields').append(card); return card;
}
function warning(parent, text) { parent.append(element('p', 'inline-warning', text)); }
function buildFields() {
  field($('plex-fields'), 'plex_url', 'Plex-Server-URL', 'Lokale Adresse oder HTTPS-Adresse deines Plex Media Servers.');
  field($('plex-fields'), 'plex_username', 'Plex-Benutzername', 'Exakter Kontoname des Token-Inhabers. Keine fremden Benutzer.');
  let g = group('sync', 'Zeitplan & Ereignisse', 'Automatische Läufe starten erst nach einer gültigen Analyse und Freigabe.');
  toggle(g, 'sync_enabled', 'Regelmäßig synchronisieren', 'Führt einen vollständigen Abgleich im gewählten Intervall aus.');
  field(g, 'sync_interval_minutes', 'Sync-Intervall in Minuten', '15 bis 1.440 Minuten. Gilt für den vollständigen Abgleich.', 'number', null, [15, 1440]);
  toggle(g, 'watch_enabled', 'Auf Plex-Wiedergabe reagieren', 'Plex-Ereignisse lösen einen gezielten Abgleich abgeschlossener Wiedergaben aus. Benötigt Plex → Trakt für den Gesehen-Status.');
  warning(g, 'Die Ereignisüberwachung verwendet denselben geschützten Sync-Prozess. Sie fügt keine zusätzlichen Rewatch-Einträge per Live-Scrobbling hinzu.');
  g = group('sync', 'Gesehen-Status', 'Einträge werden ergänzt. Bereits vorhandener Verlauf wird nicht erneut als Wiedergabe hinzugefügt.');
  toggle(g, 'plex_to_trakt_watched', 'Plex → Trakt', 'Überträgt in Plex gesehene Filme und Episoden nach Trakt.');
  toggle(g, 'trakt_to_plex_watched', 'Trakt → Plex', 'Markiert in Trakt gesehene Medien auch in Plex als gesehen.');
  g = group('sync', 'Bewertungen', 'Aktiviere den Bewertungsabgleich und wähle anschließend die Richtungen.');
  toggle(g, 'ratings', 'Bewertungen synchronisieren', 'Hauptschalter für sämtliche Bewertungsänderungen.');
  toggle(g, 'plex_to_trakt_ratings', 'Bewertungen: Plex → Trakt', 'Übernimmt deine Plex-Bewertungen nach Trakt, wenn der Hauptschalter aktiv ist.');
  toggle(g, 'trakt_to_plex_ratings', 'Bewertungen: Trakt → Plex', 'Übernimmt deine Trakt-Bewertungen nach Plex, wenn der Hauptschalter aktiv ist.');
  field(g, 'rating_priority', 'Bei unterschiedlichen Bewertungen', 'Ohne Priorität bleiben bereits vorhandene, unterschiedliche Bewertungen bestehen.', 'select', [['none', 'Konflikte behalten (empfohlen)'], ['plex', 'Plex hat Vorrang'], ['trakt', 'Trakt hat Vorrang']]);
  g = group('sync', 'Watchlists & Playlists', 'Diese Funktionen sind standardmäßig aus. Aktiviere nur die benötigten Richtungen.');
  toggle(g, 'plex_to_trakt_watchlist', 'Watchlist: Plex → Trakt', 'Gleicht die Trakt-Watchlist mit der Plex-Watchlist ab.');
  toggle(g, 'trakt_to_plex_watchlist', 'Watchlist: Trakt → Plex', 'Übernimmt die Trakt-Watchlist in Plex.');
  toggle(g, 'watchlist_as_playlist', 'Trakt-Watchlist als Plex-Playlist', 'Verwendet beim Import Trakt → Plex eine verwaltete Playlist statt der Plex-Watchlist.');
  warning(g, 'Watchlist-Abgleiche können Einträge hinzufügen UND entfernen. Bei einer Richtung wird die Quelle gespiegelt. Verwaltete Playlist-Inhalte können ersetzt werden.');
  g = group('sync', 'Gelikte Trakt-Listen', 'Importiere gelikte Listen als Plex-Playlists. Die ursprünglichen Trakt-Listen bleiben unverändert.');
  toggle(g, 'liked_lists', 'Gelikte Listen importieren', 'Erstellt oder aktualisiert die dazugehörigen Plex-Playlists.');
  toggle(g, 'liked_lists_keep_watched', 'Gesehene Medien in Playlists behalten', 'Standardwert für alle importierten Listen. Einzelne Listen lassen sich unten abweichend einstellen.');
  const overrides = element('div', 'field'); overrides.dataset.setting = 'liked_list_overrides';
  overrides.append(element('h3', '', 'Ausnahmen pro Liste'), element('p', 'field-help', 'Exakter Trakt-Listenname. Doppelte Namen sind nicht erlaubt.'));
  const rows = element('div'); rows.id = 'override-rows'; overrides.append(rows);
  const add = element('button', 'button override-add', '+ Liste hinzufügen'); add.type = 'button'; add.id = 'add-override';
  add.addEventListener('click', () => { addOverride('', true); markDirty(); }); overrides.append(add); g.append(overrides);
  warning(g, 'Beim Import können bestehende Inhalte der verwalteten Plex-Playlists ersetzt werden. Exakte Playlist-Unterschiede sind im Analysebericht nicht verfügbar.');
  g = group('sync', 'Wiedergabefortschritt', 'Optionaler Import begonnener Wiedergaben von Trakt nach Plex.');
  toggle(g, 'trakt_to_plex_playback', 'Fortschritt: Trakt → Plex', 'Übernimmt die aktuelle Abspielposition aus Trakt.');
  warning(g, 'Überschreibt vorhandenen Plex-Fortschritt. Ab 99 % kann Plex Medien als gesehen markieren – auch wenn der umgekehrte Gesehen-Abgleich ausgeschaltet ist.');
  g = group('libraries', 'Medien & Bibliotheken', 'Leere Bibliotheksfilter berücksichtigen alle passenden Bibliotheken. Ausschlüsse haben Vorrang.');
  field(g, 'sync_media', 'Medientyp', 'Wähle den Umfang des vollständigen und ereignisbezogenen Abgleichs.', 'select', [['all', 'Filme & Serien'], ['movies', 'Nur Filme'], ['tv', 'Nur Serien']]);
  const grid = element('div', 'fields-grid'); g.append(grid);
  field(grid, 'include_libraries', 'Bibliotheken einschließen', 'Exakte Plex-Bibliotheksnamen, ein Name pro Zeile. Leer = alle.', 'lines');
  field(grid, 'exclude_libraries', 'Bibliotheken ausschließen', 'Diese Bibliotheken werden immer übersprungen.', 'lines');
  g = group('libraries', 'Gezielte Ausschlüsse', 'Filter begrenzen die Analyse und die anschließende Synchronisierung.');
  field(g, 'ignore_ids', 'Plex-Medien-IDs ignorieren', 'Numerische Plex-IDs (ratingKey), eine ID pro Zeile. Maximal 12 Stellen je ID.', 'lines');
  field(g, 'watch_ignore_clients', 'Wiedergabegeräte ignorieren', 'Plex-Client-IDs für die Ereignisüberwachung. Eine ID pro Zeile.', 'lines');
  g = group('advanced', 'Verbindungen & Verarbeitung', 'Zeitlimits gelten für Verbindungsversuche. Eine Stapelpause reduziert die Anzahl schneller API-Aufrufe.');
  const timing = element('div', 'fields-grid'); g.append(timing);
  field(timing, 'plex_timeout', 'Plex-Zeitlimit in Sekunden', '5 bis 300 Sekunden.', 'number', null, [5, 300]);
  field(timing, 'request_timeout', 'API-Zeitlimit in Sekunden', '5 bis 300 Sekunden für HTTP-Anfragen.', 'number', null, [5, 300]);
  field(timing, 'batch_delay', 'Stapelpause in Sekunden', '0 bis 300 Sekunden zwischen Übertragungsstapeln.', 'number', null, [0, 300]);
  g = group('advanced', 'Metadaten-Zuordnung', 'Anbieter für die Auflösung unterstützter Metadaten-IDs. Bestehende Plex-Metadaten werden nicht verändert.');
  const providers = element('div', 'fields-grid'); g.append(providers);
  field(providers, 'movie_provider', 'Anbieter für Filme', 'Standard: IMDb.', 'select', [['imdb', 'IMDb'], ['tmdb', 'TMDb']]);
  field(providers, 'show_provider', 'Anbieter für Serien', 'Standard: TheTVDB.', 'select', [['tvdb', 'TheTVDB'], ['tmdb', 'TMDb'], ['imdb', 'IMDb']]);
  g = group('advanced', 'Protokollierung', 'Die App protokolliert Betriebsereignisse ohne Zugangsdaten.');
  field(g, 'log_level', 'Protokollstufe', 'Debug-Protokolle und rohe HTTP-Antworten werden nicht angeboten.', 'select', [['info', 'Informationen'], ['warning', 'Nur Warnungen & Fehler'], ['error', 'Nur Fehler']]);
}
function addOverride(name, keepWatched) {
  const row = element('div', 'override-row');
  const input = element('input'); input.type = 'text'; input.value = name; input.placeholder = 'Name der Trakt-Liste'; input.maxLength = 512;
  input.required = true; input.setAttribute('aria-label', 'Listenname');
  const label = element('label'); const keep = element('input'); keep.type = 'checkbox'; keep.checked = keepWatched;
  label.append(keep, document.createTextNode('Gesehene behalten'));
  const remove = element('button', 'override-remove', '×'); remove.type = 'button'; remove.setAttribute('aria-label', 'Listenausnahme entfernen');
  remove.addEventListener('click', () => { row.remove(); markDirty(); });
  row.append(input, label, remove); $('override-rows').append(row); return input;
}
function collect() {
  const options = {};
  fields.forEach(({ input, type }, key) => {
    options[key] = type === 'boolean' ? input.checked : type === 'lines' ? input.value.split(/\r?\n/).map(x => x.trim()).filter(Boolean)
      : type === 'number' ? Number(input.value) : input.value.trim();
  });
  options.liked_list_overrides = all('.override-row').map(row => ({ name: row.querySelector('input[type=text]').value.trim(), keep_watched: row.querySelector('input[type=checkbox]').checked }));
  return options;
}
function credentials() {
  return Object.fromEntries(all('[data-secret]').filter(el => el.value).map(el => [el.dataset.secret, el.value]));
}
function sameOptions(a, b) { return Object.keys(a).length === Object.keys(b).length && Object.keys(a).every(key => JSON.stringify(a[key]) === JSON.stringify(b[key])); }
function fill(data) {
  snapshot = data;
  fields.forEach(({ input, type }, key) => {
    const value = data.options[key];
    if (type === 'boolean') input.checked = value;
    else input.value = type === 'lines' ? value.join('\n') : value;
  });
  $('override-rows').replaceChildren(); data.options.liked_list_overrides.forEach(x => addOverride(x.name, x.keep_watched));
  all('[data-secret]').forEach(input => {
    input.value = ''; input.type = 'password';
    input.placeholder = data.stored_credentials[input.dataset.secret] ? 'Gespeichert · leer lassen zum Beibehalten' : 'Noch nicht hinterlegt';
    $('help-' + input.dataset.secret).textContent = data.stored_credentials[input.dataset.secret]
      ? 'Sicher gespeichert. Zum Ersetzen einen neuen Wert eingeben.' : 'Noch kein Wert gespeichert.';
  });
  all('[data-reveal]').forEach(el => { el.textContent = 'Anzeigen'; el.setAttribute('aria-label', 'Plex-Token anzeigen'); });
  markDirty();
}
function markDirty() {
  dirty = Boolean(snapshot && (!sameOptions(collect(), snapshot.options) || Object.keys(credentials()).length));
  $('save-bar').hidden = !dirty; document.body.classList.toggle('has-changes', dirty); updateButtons();
}
function navigate(focus = false) {
  const page = location.hash.slice(1) in pages ? location.hash.slice(1) : 'overview';
  all('.page').forEach(el => { el.hidden = el.id !== 'page-' + page; });
  all('[data-page]').forEach(el => {
    if (el.dataset.page === page) el.setAttribute('aria-current', 'page'); else el.removeAttribute('aria-current');
  });
  const [title, eyebrow, description] = pages[page];
  $('page-title').textContent = title; $('breadcrumb').textContent = title;
  $('eyebrow').textContent = eyebrow; $('page-description').textContent = description;
  document.title = title + ' · PlexTraktSync'; closeMenu();
  if (focus) { window.scrollTo(0, 0); $('main').focus({ preventScroll: true }); }
}
function syncDrawer() {
  const mobile = window.matchMedia('(max-width: 820px)').matches;
  const open = $('sidebar').classList.contains('open');
  $('sidebar').inert = mobile && !open;
  if (mobile && !open) $('sidebar').setAttribute('aria-hidden', 'true'); else $('sidebar').removeAttribute('aria-hidden');
  $('backdrop').hidden = !mobile || !open;
  $('menu').setAttribute('aria-expanded', String(mobile && open));
}
function closeMenu() { $('sidebar').classList.remove('open'); syncDrawer(); }
function updateButtons() {
  const blocked = pending || !online || !snapshot || Boolean(status?.busy);
  const connected = status?.plex_configured && status?.trakt_authorized && snapshot?.options.plex_url && snapshot?.options.plex_username;
  all('[data-action]').forEach(el => { el.disabled = blocked || dirty || !connected || (el.dataset.action === 'sync' && (!status?.approved || status?.paused)); });
  $('save').disabled = blocked || !dirty; $('discard').disabled = pending;
  $('approve').disabled = blocked || dirty || !status?.analysis || status?.approved;
  $('plex-test').disabled = blocked || dirty || !status?.plex_configured || !snapshot?.options.plex_url || !snapshot?.options.plex_username;
  $('trakt-start').disabled = blocked || dirty || !snapshot?.stored_credentials.client_id;
  $('trakt-poll').disabled = blocked || dirty;
  $('pause').disabled = pending || !online || !snapshot;
  // Freeze editing during saves so newer keystrokes cannot be discarded by the response.
  all('[data-setting] input, input[data-setting], textarea[data-setting], select[data-setting], [data-secret], .override-row input, #add-override, .override-remove').forEach(el => { el.disabled = pending || !snapshot; });
}
const errors = {
  'Settings changed in another session; reload before saving': 'Die Einstellungen wurden in einer anderen Sitzung geändert. Lade die Seite neu, bevor du speicherst.',
  'Wait until the current job finishes': 'Bitte warte, bis der laufende Auftrag beendet ist.',
  'Run a fresh analysis first': 'Starte zuerst eine neue Analyse.',
  'Token account differs from configured Plex username': 'Der Plex-Token gehört zu einem anderen Benutzernamen.',
  'plex_url requires an HTTP or HTTPS server URL without credentials': 'Bitte gib eine gültige HTTP- oder HTTPS-Adresse ohne eingebettete Zugangsdaten ein.',
  'ignore_ids must contain numeric Plex item IDs': 'Plex-Medien-IDs dürfen nur aus bis zu 12 Ziffern bestehen.',
  'Liked-list overrides require unique names and boolean keep_watched': 'Listenausnahmen benötigen eindeutige, nicht leere Namen.',
  'ConnectionError': 'Verbindung fehlgeschlagen. Prüfe Serveradresse und Netzwerk.',
  'HTTPError': 'Der Dienst hat die Anfrage abgelehnt. Prüfe deine Zugangsdaten.',
  'Unauthorized': 'Zugriff verweigert. Prüfe den Plex-Token.',
};
async function api(path, data) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), path === 'plex-test' ? ((snapshot?.options.plex_timeout || 30) + 10) * 1000 : 20000);
  try {
    const response = await fetch('api/' + path, { method: data === undefined ? 'GET' : 'POST', cache: 'no-store', signal: controller.signal,
      headers: { 'Content-Type': 'application/json', ...(data === undefined ? {} : { 'X-CSRF-Token': status?.csrf || '' }) },
      ...(data === undefined ? {} : { body: JSON.stringify(data) }) });
    const result = await response.json();
    if (!response.ok) throw new Error(errors[result.error] || result.error || (response.status === 403 ? 'Sitzung abgelaufen. Lade die Seite neu.' : 'Anfrage fehlgeschlagen.'));
    return result;
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('Zeitlimit erreicht. Prüfe den Status, bevor du die Aktion wiederholst.');
    if (error instanceof TypeError) throw new Error('Die App ist nicht erreichbar. Prüfe die Verbindung.');
    throw error;
  } finally { clearTimeout(timeout); }
}
function toast(message, error = false) {
  clearTimeout(toastTimer); $('toast').textContent = message; $('toast').classList.toggle('error', error); $('toast').hidden = false;
  toastTimer = setTimeout(() => { $('toast').hidden = true; }, error ? 10000 : 5000);
}
function date(value) { return value ? new Date(value * 1000).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : 'Noch kein Lauf'; }
function renderStatus() {
  if (!status) return;
  const s = status;
  $('plex-status').textContent = s.plex_configured ? 'Zugang hinterlegt' : 'Noch nicht verbunden';
  $('trakt-status').textContent = s.trakt_authorized ? 'Autorisierung hinterlegt' : 'Noch nicht autorisiert';
  $('plex-badge').textContent = s.plex_configured ? 'Token gespeichert' : 'Nicht eingerichtet';
  $('trakt-badge').textContent = s.trakt_authorized ? 'OAuth gespeichert' : 'Nicht autorisiert';
  $('plex-badge').classList.toggle('teal', s.plex_configured); $('trakt-badge').classList.toggle('teal', s.trakt_authorized);
  $('last-success').textContent = date(s.last_success);
  $('next-sync').textContent = snapshot?.options.sync_enabled ? (s.approved && !s.paused ? 'Nächster Lauf: ' + date(s.next_sync) : 'Automatik wartet auf Freigabe / Fortsetzen') : 'Automatik aus';
  $('approval-state').textContent = s.approved ? 'Freigegeben' : 'Nicht freigegeben'; $('approval-state').classList.toggle('teal', s.approved);
  [['connection', s.plex_configured && s.trakt_authorized], ['analysis', s.analysis], ['approval', s.approved]].forEach(([key, done]) => {
    $('step-' + key).textContent = done ? '✓' : '○'; $('step-' + key).classList.toggle('done', Boolean(done));
  });
  $('operation').textContent = s.busy ? 'Auftrag läuft …' : s.paused ? 'Synchronisierung pausiert' : s.approved ? 'Bereit zum Synchronisieren' : s.analysis ? 'Analyse bereit zur Prüfung' : 'Wartet auf Einrichtung';
  $('operation-description').textContent = s.busy ? 'Der Status wird automatisch aktualisiert.' : s.approved ? 'Die aktuelle Konfiguration ist freigegeben.' : 'Prüfe Verbindungen und Einstellungen, bevor du Änderungen freigibst.';
  $('pause').textContent = s.paused ? 'Fortsetzen' : 'Pausieren';
  $('activity-dot').classList.toggle('active', Boolean(s.busy || s.watch_running));
  $('watch-state').textContent = s.watch_running ? 'Ereignisüberwachung aktiv' : snapshot?.options.watch_enabled ? 'Ereignisüberwachung wartet auf Freigabe' : 'Ereignisüberwachung aus';
  $('server-error').hidden = !s.last_error; $('server-error').textContent = s.last_error ? 'Letzter Auftrag: ' + (errors[s.last_error] || s.last_error) : '';
  renderAnalysis(s.analysis); updateButtons(); document.dispatchEvent(new Event('pts-status-updated'));
}
function renderAnalysis(report) {
  const serialized = JSON.stringify(report);
  if (serialized === lastReport) return; lastReport = serialized;
  const target = $('analysis-content'); target.replaceChildren();
  if (!report) {
    const empty = element('div', 'empty-state'); empty.append(element('span', '', '⌕'), element('h3', '', 'Noch keine Analyse vorhanden'), element('p', '', 'Verbinde deine Konten, speichere die Einstellungen und starte eine Analyse.')); target.append(empty); return;
  }
  const counts = element('div', 'analysis-counts');
  [[report.missing_in_trakt, 'Gesehene Medien fehlen in Trakt'], [report.already_in_trakt, 'Bereits in Trakt vorhanden'], [report.rating_conflicts, 'Bewertungskonflikte']].forEach(([value, label]) => {
    const tile = element('div', 'analysis-count'); tile.append(element('strong', '', String(value ?? 0)), element('span', '', label)); counts.append(tile);
  }); target.append(counts);
  target.append(element('p', 'field-help', `${report.watched_movies ?? 0} gesehene Filme · ${report.watched_episodes ?? 0} gesehene Episoden in der Plex-Auswahl. Die Zahlen sind keine vollständige Änderungsliste für optionale Funktionen.`));
  if (report.warnings?.length) { const block = element('div', 'analysis-block'); block.append(element('h3', '', 'Vor der Freigabe beachten')); report.warnings.forEach(text => warning(block, translateWarning(text))); target.append(block); }
  const block = element('div', 'analysis-block'); block.append(element('h3', '', 'Aktivierte Richtungen'));
  const list = element('ul'); const names = { watched_status: 'Gesehen-Status', ratings: 'Bewertungen', watchlist: 'Watchlist', liked_lists: 'Gelikte Listen → Plex-Playlists', playback_status: 'Wiedergabefortschritt' };
  Object.entries(report.sync_options || {}).forEach(([direction, options]) => {
    if (!options || typeof options !== 'object') return;
    Object.entries(options).forEach(([key, enabled]) => { if (enabled) list.append(element('li', '', `${direction === 'plex_to_trakt' ? 'Plex → Trakt' : 'Trakt → Plex'} · ${names[key] || key}`)); });
  });
  if (!list.children.length) list.append(element('li', '', 'Keine Schreibfunktion aktiviert.'));
  block.append(list);
  [['missing_titles', 'In Trakt fehlende Titel'], ['existing_titles', 'Bereits vorhandene Titel'], ['rating_conflict_titles', 'Titel mit Bewertungskonflikten'], ['unmatched', 'Nicht zugeordnete / übersprungene Titel']].forEach(([key, label]) => {
    const items = report[key] || []; const details = element('details'); details.append(element('summary', '', `${label} (${items.length})`));
    const entries = element('ul'); items.forEach(text => entries.append(element('li', '', text))); details.append(entries); block.append(details);
  }); target.append(block);
}
function translateWarning(text) {
  if (text.startsWith('Watchlist sync')) return 'Watchlists können Einträge hinzufügen und entfernen. Eine Richtung spiegelt die gewählte Quelle.';
  if (text.startsWith('Managed Plex playlist')) return 'Verwaltete Plex-Playlists können ersetzt werden. Exakte Playlist-Unterschiede sind in diesem Bericht nicht enthalten.';
  if (text.startsWith('Trakt playback progress')) return 'Trakt-Fortschritt überschreibt Plex-Fortschritt. Ab 99 % können Medien als gesehen markiert werden, auch ohne umgekehrten Gesehen-Abgleich.';
  return text;
}
async function refresh(loadSettings = false) {
  try {
    const next = await api('status');
    if (loadSettings) fill(await api('settings'));
    status = next; online = true; $('load-error').hidden = true;
    $('connection').className = 'connection-indicator online'; $('connection').lastElementChild.textContent = 'App erreichbar'; renderStatus();
  } catch (error) {
    online = false; $('load-error').hidden = false; $('connection').className = 'connection-indicator offline'; $('connection').lastElementChild.textContent = 'Verbindung unterbrochen'; updateButtons();
  }
}
async function perform(fn) {
  if (pending) return; pending = true; updateButtons();
  try { await fn(); await refresh(); } catch (error) { toast(error.message, true); }
  finally { pending = false; updateButtons(); }
}
function requireSaved() { if (dirty) throw new Error('Speichere zuerst deine Änderungen.'); }
async function pollTrakt() {
  requireSaved();
  const result = await api('trakt-poll', {});
  if (result.authorized) { clearTimeout(deviceTimer); $('device-flow').hidden = true; toast('Trakt-Autorisierung gespeichert. Du kannst jetzt analysieren.'); }
  else $('device-state').textContent = 'Noch nicht bestätigt. Gib den Code bei Trakt ein und prüfe erneut.';
  return result;
}
function scheduleDevicePoll() {
  clearTimeout(deviceTimer);
  deviceTimer = setTimeout(async () => {
    if (Date.now() >= deviceExpires) { $('device-state').textContent = 'Der Code ist abgelaufen. Starte die Verbindung erneut.'; return; }
    if (pending || dirty || !online) { scheduleDevicePoll(); return; }
    let authorized = false;
    await perform(async () => { authorized = Boolean((await pollTrakt()).authorized); });
    if (!authorized) scheduleDevicePoll();
  }, deviceInterval * 1000);
}
buildFields();
$('settings-form').noValidate = true;
$('settings-form').addEventListener('input', markDirty);
$('settings-form').addEventListener('change', markDirty);
$('settings-form').addEventListener('submit', event => {
  event.preventDefault(); if (!dirty || pending || status?.busy || !online) return;
  const invalid = all('#settings-form input, #settings-form textarea, #settings-form select').find(el => !el.disabled && !el.checkValidity());
  if (invalid) { const page = invalid.closest('.page'); if (page) { location.hash = page.id.slice(5); navigate(); } invalid.reportValidity(); return; }
  perform(async () => {
    const result = await api('settings', { options: collect(), credentials: credentials(), revision: snapshot.revision });
    fill(result); clearTimeout(deviceTimer); $('device-flow').hidden = true;
    $('plex-test-result').textContent = 'Einstellungen gespeichert. Die Verbindung kann geprüft werden.';
    toast('Gespeichert. Die Einstellungen gelten sofort. Eine neue Analyse ist erforderlich.');
  });
});
$('discard').addEventListener('click', () => { fill(snapshot); toast('Änderungen verworfen.'); });
all('[data-action]').forEach(button => button.addEventListener('click', () => perform(async () => {
  requireSaved(); await api(button.dataset.action, {});
  if (button.dataset.action === 'analyze') { location.hash = 'analysis'; toast('Analyse gestartet. Der Bericht erscheint nach Abschluss.'); }
  else toast('Synchronisierung gestartet.');
})));
$('pause').addEventListener('click', () => perform(async () => { await api('pause', { paused: !status.paused }); toast(status.paused ? 'Betrieb fortgesetzt.' : 'Betrieb pausiert.'); }));
$('plex-test').addEventListener('click', () => perform(async () => {
  requireSaved(); const result = await api('plex-test', {});
  $('plex-test-result').textContent = 'Verbindung bestätigt. Bibliotheken: ' + (result.libraries.join(', ') || 'keine'); toast('Plex-Konto und Verbindung bestätigt.');
}));
$('trakt-start').addEventListener('click', () => perform(async () => {
  requireSaved(); const result = await api('trakt-start', {});
  const url = new URL(result.verification_url);
  if (url.protocol !== 'https:' || !['trakt.tv', 'www.trakt.tv'].includes(url.hostname)) throw new Error('Ungültige Trakt-Aktivierungsadresse.');
  $('device-code').textContent = result.user_code; $('device-link').href = url.href; $('device-flow').hidden = false;
  $('device-state').textContent = 'Warte auf Bestätigung. Die App prüft automatisch.';
  deviceInterval = Math.max(5, Number(result.interval) || 5); deviceExpires = Date.now() + result.expires_in * 1000; scheduleDevicePoll();
}));
$('trakt-poll').addEventListener('click', () => perform(pollTrakt));
$('approve').addEventListener('click', () => $('approval-dialog').showModal());
$('cancel-approve').addEventListener('click', () => $('approval-dialog').close());
$('confirm-approve').addEventListener('click', () => { $('approval-dialog').close(); perform(async () => { requireSaved(); await api('approve', {}); toast('Freigabe für die analysierte Konfiguration erteilt.'); }); });
all('[data-reveal]').forEach(button => button.addEventListener('click', () => {
  const input = $(button.dataset.reveal); const reveal = input.type === 'password'; input.type = reveal ? 'text' : 'password';
  button.textContent = reveal ? 'Verbergen' : 'Anzeigen'; button.setAttribute('aria-label', 'Plex-Token ' + (reveal ? 'verbergen' : 'anzeigen'));
}));
$('menu').addEventListener('click', () => { const open = $('sidebar').classList.toggle('open'); syncDrawer(); if (open) $('sidebar').querySelector('[aria-current=page]').focus(); });
$('backdrop').addEventListener('click', closeMenu);
document.addEventListener('keydown', event => { if (event.key === 'Escape') { closeMenu(); $('menu').focus(); } });
window.addEventListener('hashchange', () => navigate(true));
window.addEventListener('resize', syncDrawer);
window.addEventListener('beforeunload', event => { if (dirty) { event.preventDefault(); event.returnValue = ''; } });
$('retry').addEventListener('click', () => refresh(!snapshot));
navigate(); updateButtons(); refresh(true);
// One request at a time; status polling never replaces unsaved form values.
async function pollStatus() { if (!pending && !document.hidden) await refresh(!snapshot); setTimeout(pollStatus, 5000); }
setTimeout(pollStatus, 5000);
