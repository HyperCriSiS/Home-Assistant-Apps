/* Backup UI uses separate settings and forms; sync settings remain independent. */
(() => {
  'use strict';
  const root = element('section', 'page'); root.id = 'page-backups'; root.hidden = true;
  root.setAttribute('aria-label', 'Sicherungen');
  root.innerHTML = `
    <div class="backup-tabs" role="tablist" aria-label="Sicherungsbereiche">
      <button type="button" role="tab" id="bt-archives" aria-controls="bp-archives" aria-selected="true" data-btab="archives">Archive</button>
      <button type="button" role="tab" id="bt-settings" aria-controls="bp-settings" aria-selected="false" data-btab="settings">Zeitpläne & Aufbewahrung</button>
      <button type="button" role="tab" id="bt-restore" aria-controls="bp-restore" aria-selected="false" data-btab="restore">Wiederherstellen</button>
    </div>
    <div id="backup-error" class="notice danger" role="alert" hidden></div>
    <div class="backup-stats"><div><span>Letzte erfolgreiche Sicherung</span><strong id="backup-last">Noch keine</strong></div><div><span>Archivspeicher</span><strong id="backup-storage">–</strong></div><div><span>Nächster Zeitplan</span><strong id="backup-next">Automatik aus</strong></div></div>
    <div id="backup-job" class="notice backup-job" role="status" aria-live="polite" hidden><div><strong id="backup-job-title"></strong><p id="backup-job-message"></p></div><button type="button" class="button" id="backup-cancel">Abbrechen</button></div>
    <div id="bp-archives" role="tabpanel" aria-labelledby="bt-archives">
      <article class="card"><div class="card-header"><div><h2>Neue Trakt-Sicherung</h2><p>Wähle einzelne Bereiche oder sichere alle unterstützten Daten.</p></div><button type="button" class="button subtle" id="backup-select-all">Alle auswählen</button></div><div id="backup-create-categories" class="backup-categories"></div><div class="card-footer"><button type="button" class="button primary" id="backup-create">Jetzt sichern ↗</button><label class="check-label"><input type="checkbox" id="backup-create-pinned">Dauerhaft schützen</label><span class="field-help">Sicherungen lesen Trakt-Daten. Sie verändern keine Medien.</span></div></article>
      <article class="card"><div class="card-header"><div><h2>Gespeicherte Archive</h2><p>Ein Archiv enthält Daten und Prüfsummen, keine Zugangsdaten.</p></div><label class="button upload-label" for="backup-upload">ZIP importieren ↥<input type="file" id="backup-upload" accept=".zip,application/zip" hidden></label></div><div class="backup-filter"><input type="search" id="backup-search" aria-label="Archive durchsuchen" placeholder="Archive nach Konto, Datum oder Typ filtern …"><select id="backup-scope-filter" aria-label="Nach Datenbereich filtern"><option value="">Alle Datenbereiche</option></select><label class="check-label"><input type="checkbox" id="backup-protected-filter">Nur geschützt</label></div><div id="backup-archives"></div><p class="field-help">Importiert werden versionierte Archive dieser App, maximal 128 MiB ZIP / 512 MiB entpackte Daten. Trakt-Webexporte haben ein anderes Format.</p></article>
    </div>
    <div id="bp-settings" role="tabpanel" aria-labelledby="bt-settings" hidden>
      <form id="backup-settings-form">
        <article class="card"><div class="card-header"><div><h2>Automatik</h2><p>Unabhängig davon, welche Sync-Richtungen aktiviert sind.</p></div><span class="pill" id="backup-settings-dirty">Gespeichert</span></div><label class="toggle-row"><div><span class="toggle-title">Zeitpläne aktivieren</span><p>Führt aktivierte Zeitpläne auch bei pausierter Synchronisierung aus.</p></div><input class="switch" type="checkbox" role="switch" data-bsetting="enabled" aria-label="Sicherungszeitpläne aktivieren"></label><label class="toggle-row"><div><span class="toggle-title">Vor Sync-Läufen sichern</span><p>Eine fehlgeschlagene Pflichtsicherung blockiert den Sync. Ein Mindestabstand vermeidet unnötige Sicherungen bei Wiedergabeereignissen.</p></div><input class="switch" type="checkbox" role="switch" data-bsetting="before_sync" aria-label="Vor Sync-Läufen sichern"></label><div class="fields-grid"><div class="field"><label for="backup-before-interval">Mindestabstand vor Sync · Minuten</label><input id="backup-before-interval" type="number" min="0" max="43200" required data-bsetting="before_sync_minutes"><p class="field-help">0 = vor jedem Sync-Lauf sichern.</p></div><div class="field"><label for="backup-timezone">Zeitzone für Zeitpläne & Aufbewahrung</label><input id="backup-timezone" type="text" maxlength="100" list="backup-timezones" required data-bsetting="timezone"><datalist id="backup-timezones"><option value="UTC"><option value="Europe/Berlin"><option value="Europe/Vienna"><option value="Europe/Zurich"><option value="America/New_York"></datalist><p class="field-help">IANA-Zeitzone. Kalenderpläne berücksichtigen Sommer-/Winterzeit.</p></div></div><h3>Datenbereiche für Sicherungen vor dem Sync</h3><div id="backup-default-categories" class="backup-categories"></div></article>
        <article class="card"><div class="card-header"><div><h2>Zeitpläne</h2><p>Mehrere tägliche, wöchentliche, monatliche oder Intervall-Sicherungen kombinieren.</p></div><button type="button" class="button" id="backup-add-schedule">+ Zeitplan</button></div><div id="backup-schedules"></div><p class="field-help">Nach einem Ausfall wird ein fälliger Plan einmal nachgeholt, nicht für jeden verpassten Termin. Monatstage 29–31 fallen in kürzeren Monaten auf den letzten Tag.</p></article>
        <article class="card"><h2>Gestaffelte Aufbewahrung</h2><p class="group-description">Die Regeln werden kombiniert: neueste Stände plus Tages-, Wochen-, Monats- und Jahresstände. Pro Zeitraum bleibt der neueste Stand erhalten. Jedes Konto und jede Auswahl von Datenbereichen wird getrennt behandelt.</p><div id="backup-retention-fields" class="fields-grid"></div><label class="toggle-row"><div><span class="toggle-title">Manuelle Sicherungen grundsätzlich behalten</span><p>Zusätzlich zum individuellen Archivschutz. Importierte Archive sind zunächst geschützt.</p></div><input type="checkbox" class="switch" role="switch" data-bsetting="retention.keep_manual" aria-label="Manuelle Sicherungen behalten"></label><p class="inline-warning">Geschützte Archive werden nie automatisch gelöscht. Altersgrenzen gelten nicht für geschützte oder zwingend aufbewahrte neueste Stände. Rückfallsicherungen vor einer Wiederherstellung sind zunächst geschützt.</p></article>
        <article class="card"><h2>Speicher & Fehlerbehandlung</h2><div id="backup-runtime-fields" class="fields-grid"></div><p class="field-help">Speicherlimits überschreiben keinen Archivschutz. Ist das Kontingent belegt, stoppt die nächste Sicherung mit einer Meldung. Nur fehlgeschlagene geplante Sicherungen werden wiederholt; Wiederherstellungen nie automatisch.</p></article>
        <div class="card backup-settings-footer"><div><strong id="backup-settings-note">Speichern löscht keine Archive.</strong><p class="field-help">Aufbewahrung wird nach einer erfolgreichen neuen Sicherung oder durch „Jetzt bereinigen“ angewendet.</p></div><div class="button-row"><button type="button" class="button subtle" id="backup-settings-discard">Verwerfen</button><button type="submit" class="button primary" id="backup-settings-save">Sicherungseinstellungen speichern</button></div></div>
      </form><article class="card"><div class="card-header"><div><h2>Aufbewahrung jetzt anwenden</h2><p id="backup-prune-preview">Keine Archive zur Bereinigung.</p></div><button type="button" class="button" id="backup-prune">Jetzt bereinigen</button></div></article>
    </div>
    <div id="bp-restore" role="tabpanel" aria-labelledby="bt-restore" hidden>
      <article class="card"><h2>Gezielt wiederherstellen</h2><p class="group-description">Wähle ein Archiv und die benötigten Datenbereiche. Vor jedem Schreibzugriff ist eine aktuelle Vorschau und Freigabe erforderlich.</p><div class="field"><label for="backup-restore-archive">Sicherungsarchiv</label><select id="backup-restore-archive"></select></div><div id="backup-restore-categories" class="backup-categories"></div><div class="field"><label for="backup-restore-mode">Wiederherstellungsmodus</label><select id="backup-restore-mode"><option value="merge">Nur Fehlendes ergänzen</option><option value="overwrite">Gesicherte Werte übernehmen, zusätzliche Einträge behalten</option><option value="mirror">Ausgewählte Bereiche auf Sicherungsstand zurücksetzen</option></select><p class="field-help" id="backup-mode-help">Vorhandene Einträge und abweichende Bewertungen bleiben erhalten. Fehlende Wiedergaben werden anhand von Medium und UTC-Zeitpunkt ergänzt.</p></div><label class="check-label"><input type="checkbox" id="backup-cross-account">Wiederherstellung auf ein anderes Trakt-Konto ausdrücklich erlauben</label><p class="inline-warning">Abspielfortschritt wird nur archiviert. Neue interne IDs, ursprüngliche Eintrags-Erstellzeiten und Scrobble-Quellen können nicht identisch zurückgesetzt werden. Kommentare, allgemeine Notizen, soziale Beziehungen und Kontoeinstellungen sind nicht Teil dieses Sicherungsformats.</p><div class="card-footer"><button type="button" class="button primary" id="backup-preview">Vorschau erstellen ↗</button><span class="field-help">Vor der Ausführung wird automatisch eine geschützte Rückfallsicherung angelegt.</span></div></article>
      <article class="card" id="backup-plan" hidden><div class="card-header"><div><h2>Wiederherstellungsvorschau</h2><p id="backup-plan-account"></p></div><span class="pill" id="backup-plan-expires"></span></div><div id="backup-plan-counts"></div><div id="backup-plan-warnings"></div><div id="backup-plan-examples"></div><div class="card-footer"><button type="button" class="button primary" id="backup-restore">Vorschau freigeben & wiederherstellen</button><span class="field-help">Nach der Wiederherstellung bleibt Sync bis zu neuer Analyse/Freigabe pausiert.</span></div></article>
    </div>
    <dialog id="backup-confirm-dialog"><form id="backup-confirm-form" class="dialog-body"><span class="eyebrow">BESTÄTIGUNG</span><h2 id="backup-confirm-title"></h2><p id="backup-confirm-description"></p><div class="field"><label for="backup-confirm-input" id="backup-confirm-label"></label><input type="text" id="backup-confirm-input" autocomplete="off" required></div><div class="button-row"><button type="button" class="button" id="backup-confirm-cancel">Abbrechen</button><button type="submit" class="button primary" id="backup-confirm-submit">Bestätigen</button></div></form></dialog>`;
  $('main').append(root);
  const b = id => document.getElementById(id);
  const qa = selector => [...root.querySelectorAll(selector)];
  let model = null, configSnapshot = null, configDirty = false, requestPending = false;
  let currentTab = 'archives', selectedArchive = '', planInvalidated = false, confirmAction = null, confirmWord = '';
  const prettyDate = stamp => stamp ? new Date(stamp * 1000).toLocaleString('de-DE') : '–';
  const bytes = value => value < 1024 ? value + ' B' : value < 1024 ** 2 ? (value/1024).toFixed(1)+' KiB' : value >= 1024 ** 3 ? (value / 1024 ** 3).toFixed(2) + ' GiB' : (value / 1024 ** 2).toFixed(1) + ' MiB';
  const reasons = {manual:'Manuell',schedule:'Zeitplan','pre-sync':'Vor Sync','pre-restore':'Rückfallsicherung',import:'Import',damaged:'Beschädigt'};
  function tabPage(name) {
    currentTab = name;
    qa('[data-btab]').forEach(button => { button.setAttribute('aria-selected', String(button.dataset.btab === name)); b('bp-' + button.dataset.btab).hidden = button.dataset.btab !== name; });
  }
  qa('[data-btab]').forEach(button => button.addEventListener('click', () => tabPage(button.dataset.btab)));
  function categories(target, selected, {allowed = null, restore = false} = {}) {
    const container = b(target); container.replaceChildren();
    Object.entries(model.categories).forEach(([key, title]) => {
      const label = element('label', 'backup-category');
      const input = element('input'); input.type = 'checkbox'; input.value = key;
      input.checked = selected.includes(key); input.disabled = Boolean(allowed && !allowed.includes(key)) || (restore && !model.restorable.includes(key));
      label.append(input, element('span', '', title)); container.append(label);
    });
  }
  const selected = id => [...b(id).querySelectorAll('input:checked:not(:disabled)')].map(input => input.value).sort();
  const stable = value => JSON.stringify(value, function(key, item) { return item && !Array.isArray(item) && typeof item === 'object' ? Object.fromEntries(Object.keys(item).sort().map(name=>[name,item[name]])) : item; });
  function numericFields(target, definitions) {
    definitions.forEach(([key, name, min, max, hint]) => {
      const field = element('div', 'field'); const label = element('label', '', name); label.htmlFor = 'backup-option-' + key;
      const input = element('input'); input.type = 'number'; input.id = label.htmlFor; input.dataset.bsetting = key;
      input.min = min; input.max = max; input.required = true; input.step = 1; field.append(label, input);
      if (hint) field.append(element('p', 'field-help', hint)); b(target).append(field);
    });
  }
  numericFields('backup-retention-fields', [
    ['retention.latest','Neueste Sicherungen je Auswahl',1,36500,'Mindestens ein neuester Stand bleibt erhalten.'],
    ['retention.daily','Tagesstände',0,36500,'0 deaktiviert diese Stufe.'],['retention.weekly','Wochenstände',0,36500,'ISO-Kalenderwochen.'],
    ['retention.monthly','Monatsstände',0,36500,'Langzeitaufbewahrung nach Kalendermonat.'],['retention.yearly','Jahresstände',0,36500,'Langzeitaufbewahrung nach Kalenderjahr.'],
    ['retention.max_age_days','Altersgrenze in Tagen',0,36500,'0 = keine zusätzliche Altersgrenze; Schutz und neueste Stände haben Vorrang.'],
  ]);
  numericFields('backup-runtime-fields', [
    ['max_total_mb','Archivkontingent · MiB',128,1048576],['min_free_mb','Freier Speicher mindestens · MiB',0,1048576],
    ['job_timeout_minutes','Auftragszeitlimit · Minuten',5,360],['retry_count','Wiederholungen geplanter Sicherungen',0,5],
    ['retry_minutes','Wiederholungsabstand · Minuten',1,1440,'Wird bei jedem weiteren Fehlversuch entsprechend verlängert.'],
  ]);
  const getPath = (object, key) => key.split('.').reduce((value, part) => value[part], object);
  function setPath(object, key, value) { const parts = key.split('.'); const last = parts.pop(); parts.reduce((v, k) => v[k], object)[last] = value; }
  function addSchedule(schedule) {
    const box = element('div', 'backup-schedule'); box.dataset.scheduleId = schedule.id;
    box.innerHTML = `<div class="backup-schedule-heading"><label class="check-label"><input type="checkbox" data-skey="enabled">Aktiv</label><button type="button" class="button subtle" data-remove-schedule>Entfernen ×</button></div><div class="fields-grid"><div class="field"><label>Name<input type="text" maxlength="100" required data-skey="name"></label></div><div class="field"><label>Rhythmus<select data-skey="frequency"><option value="daily">Täglich</option><option value="weekly">Wöchentlich</option><option value="monthly">Monatlich</option><option value="interval">Alle X Stunden</option></select></label></div><div class="field" data-svisible="calendar"><label>Uhrzeit<input type="time" data-skey="time" required></label></div><div class="field" data-svisible="monthly"><label>Tag des Monats<input type="number" min="1" max="31" required data-skey="month_day"></label></div><div class="field" data-svisible="interval"><label>Abstand in Stunden<input type="number" min="1" max="8760" required data-skey="interval_hours"></label></div></div><div class="backup-weekdays" data-svisible="weekly"></div><div class="backup-categories" data-schedule-categories></div><p class="field-help" data-schedule-next></p>`;
    [...box.querySelectorAll('[data-skey]')].forEach(input => {
      if (input.type === 'checkbox') input.checked = schedule[input.dataset.skey]; else input.value = schedule[input.dataset.skey];
      input.setAttribute('aria-label', input.dataset.skey === 'name' ? 'Zeitplanname' : input.closest('label')?.textContent || input.dataset.skey);
    });
    ['Mo','Di','Mi','Do','Fr','Sa','So'].forEach((name, day) => {
      const label = element('label', 'check-label'); const input = element('input'); input.type = 'checkbox'; input.value = day; input.checked = schedule.weekdays.includes(day);
      label.append(input, document.createTextNode(name)); box.querySelector('.backup-weekdays').append(label);
    });
    Object.entries(model.categories).forEach(([key, name]) => {
      const label = element('label', 'backup-category'); const input = element('input'); input.type = 'checkbox'; input.value = key; input.checked = schedule.categories.includes(key);
      label.append(input, element('span', '', name)); box.querySelector('[data-schedule-categories]').append(label);
    });
    function visibility() { const value = box.querySelector('[data-skey=frequency]').value; box.querySelectorAll('[data-svisible]').forEach(el => { el.hidden = el.dataset.svisible === 'calendar' ? value === 'interval' : el.dataset.svisible !== value; }); }
    box.querySelector('[data-skey=frequency]').addEventListener('change', visibility);
    box.querySelector('[data-remove-schedule]').addEventListener('click', () => { box.remove(); dirtyConfig(); });
    b('backup-schedules').append(box); visibility(); updateScheduleTimes();
  }
  function readConfig() {
    const config = structuredClone(configSnapshot.settings);
    qa('[data-bsetting]').forEach(input => setPath(config, input.dataset.bsetting, input.type === 'checkbox' ? input.checked : input.type === 'number' ? Number(input.value) : input.value.trim()));
    config.categories = [...b('backup-default-categories').querySelectorAll('input:checked')].map(input=>input.value).sort();
    config.schedules = qa('.backup-schedule').map(box => {
      const schedule = {id:box.dataset.scheduleId};
      box.querySelectorAll('[data-skey]').forEach(input => { schedule[input.dataset.skey] = input.type === 'checkbox' ? input.checked : input.type === 'number' ? Number(input.value) : input.value; });
      schedule.weekdays = [...box.querySelectorAll('.backup-weekdays input:checked')].map(input => Number(input.value));
      schedule.categories = [...box.querySelectorAll('[data-schedule-categories] input:checked')].map(input => input.value).sort(); return schedule;
    }); return config;
  }
  function dirtyConfig() {
    if (!configSnapshot) return;
    configDirty = stable(readConfig()) !== stable(configSnapshot.settings);
    b('backup-settings-dirty').textContent = configDirty ? 'Ungespeichert' : 'Gespeichert'; controls();
  }
  function fillConfig(settings, revision) {
    configSnapshot = {settings:structuredClone(settings),revision};
    qa('[data-bsetting]').forEach(input => { const value = getPath(settings,input.dataset.bsetting); if (input.type === 'checkbox') input.checked = value; else input.value = value; });
    categories('backup-default-categories',settings.categories); b('backup-schedules').replaceChildren(); settings.schedules.forEach(addSchedule); configDirty = false; dirtyConfig();
  }
  function updateScheduleTimes() {
    qa('.backup-schedule').forEach(box => { const info = model?.state.schedules[box.dataset.scheduleId]; box.querySelector('[data-schedule-next]').textContent = info ? 'Nächster Termin: ' + prettyDate(info.next_run) + (info.last_success ? ' · Letzter Erfolg: ' + prettyDate(info.last_success) : '') : 'Termin wird beim Speichern berechnet.'; });
  }
  async function act(action) {
    if (requestPending) return; requestPending = true; controls();
    try { await action(); b('backup-error').hidden = true; await load(); }
    catch (error) { b('backup-error').textContent = error.message; b('backup-error').hidden = false; toast(error.message,true); }
    finally { requestPending = false; controls(); }
  }
  function controls() {
    const busy = Boolean(model?.state.job?.status === 'running' || status?.busy);
    const locked = requestPending || busy || !model || !online;
    b('backup-create').disabled = locked || !status?.trakt_authorized;
    b('backup-preview').disabled = locked || !status?.trakt_authorized || !selectedArchive;
    b('backup-restore').disabled = locked || planInvalidated || !model?.plan || model.plan.expires_at <= Date.now()/1000;
    b('backup-settings-save').disabled = locked || !configDirty;
    b('backup-add-schedule').disabled = locked || qa('.backup-schedule').length >= 12;
    b('backup-settings-discard').disabled = requestPending || !configDirty;
    b('backup-cancel').hidden = model?.state.job?.status !== 'running';
    b('backup-prune').disabled = locked || configDirty || !model?.prunable.length;
    b('backup-upload').disabled = locked;
    qa('#backup-settings-form input, #backup-settings-form select, [data-remove-schedule]').forEach(el => { el.disabled = requestPending || !model; });
    qa('[data-archive-action]').forEach(button => { button.disabled = locked; });
    b('backup-confirm-submit').disabled = requestPending;
  }
  function restoreSelection(resetCategories = true) {
    selectedArchive = b('backup-restore-archive').value;
    const entry = model.archives.find(item => item.id === selectedArchive);
    if (entry && resetCategories) categories('backup-restore-categories',entry.categories.filter(key => model.restorable.includes(key)),{allowed:entry.categories,restore:true});
    if (!entry) b('backup-restore-categories').replaceChildren();
    planInvalidated = true; b('backup-plan').hidden = true; controls();
  }
  function archiveSelect() {
    const select = b('backup-restore-archive'); const previous = select.value || selectedArchive; select.replaceChildren();
    const placeholder = element('option','','Archiv auswählen …'); placeholder.value = ''; select.append(placeholder);
    model.archives.filter(item => item.valid).forEach(item => { const option = element('option','',prettyDate(item.created_at) + ' · ' + item.account.username + ' · ' + item.categories.map(key => model.categories[key]).join(', ')); option.value = item.id; select.append(option); });
    select.value = model.archives.some(item => item.id === previous) ? previous : ''; selectedArchive = select.value;
  }
  function archiveRows() {
    const target = b('backup-archives'); target.replaceChildren();
    const search = b('backup-search').value.toLocaleLowerCase(); const scope = b('backup-scope-filter').value;
    const entries = model.archives.filter(entry => (!scope || entry.categories.includes(scope)) && (!b('backup-protected-filter').checked || entry.pinned) &&
      (entry.account.username + ' ' + prettyDate(entry.created_at) + ' ' + reasons[entry.reason] + ' ' + entry.categories.map(key => model.categories[key]).join(' ')).toLocaleLowerCase().includes(search));
    if (!entries.length) { const empty=element('div','empty-state'); empty.append(element('h3','','Noch keine passenden Archive'),element('p','','Erstelle eine Sicherung oder importiere ein Archiv dieser App.')); target.append(empty); return; }
    entries.forEach(entry => {
      const row = element('article','backup-archive');
      const copy=element('div'); const title=element('strong','',prettyDate(entry.created_at)); copy.append(title,element('p','field-help',`${entry.account.username || 'Unlesbares Archiv'} · ${reasons[entry.reason]} · ${bytes(entry.bytes)}`));
      const chips=element('div','backup-chips'); entry.categories.forEach(key => chips.append(element('span','pill',model.categories[key] + ' · ' + entry.counts[key]))); copy.append(chips);
      if (entry.pinned) copy.append(element('span','pill teal','Geschützt'));
      if (!entry.valid) copy.append(element('p','inline-warning','Archiv beschädigt oder Format unbekannt. Nicht automatisch bereinigt.'));
      const actions=element('div','button-row backup-archive-actions');
      const download=element('a','button','ZIP ↓'); download.href='api/backups/download/'+entry.id; download.download='trakt-'+entry.id+'.zip'; actions.append(download);
      function button(label, action) { const el=element('button','button subtle',label); el.type='button'; el.dataset.archiveAction=action; actions.append(el); return el; }
      if (entry.valid) {
        button('Prüfen','verify').addEventListener('click',()=>act(async()=>{await api('backup-verify',{id:entry.id});}));
        button('Wiederherstellen','restore').addEventListener('click',()=>{tabPage('restore'); b('backup-restore-archive').value=entry.id; restoreSelection();});
        button(entry.pinned?'Schutz lösen':'Schützen','pin').addEventListener('click',()=>act(async()=>{await api('backup-pin',{id:entry.id,pinned:!entry.pinned});}));
      }
      button('Löschen','delete').addEventListener('click',()=>confirm('Archiv löschen?',`${prettyDate(entry.created_at)} · ${bytes(entry.bytes)}. Diese lokale Sicherung wird endgültig gelöscht. Trakt-Daten bleiben unverändert.`,'LÖSCHEN',()=>api('backup-delete',{id:entry.id,confirmation:'LÖSCHEN'})));
      row.append(copy,actions); target.append(row);
    }); controls();
  }
  function renderPlan() {
    const plan=model.plan; const visible=Boolean(plan && !planInvalidated && selectedArchive===plan.archive_id);
    b('backup-plan').hidden=!visible; if(!visible)return;
    b('backup-plan-account').textContent=`${plan.source_account.username} → ${plan.target_account.username} · ${plan.mode==='merge'?'Nur ergänzen':plan.mode==='mirror'?'Auf Stand zurücksetzen':'Werte übernehmen'}`;
    b('backup-plan-expires').textContent='Gültig bis '+new Date(plan.expires_at*1000).toLocaleTimeString('de-DE');
    const table=element('table','backup-plan-table'); const head=element('tr'); ['Bereich','Übernehmen','Entfernen','Behalten'].forEach(text=>head.append(element('th','',text))); const thead=element('thead'); thead.append(head); table.append(thead); const tbody=element('tbody');
    Object.entries(plan.counts).forEach(([key,value])=>{const row=element('tr'); [model.categories[key],value.add,value.remove,value.skip].forEach(text=>row.append(element('td','',String(text))));tbody.append(row);if(key==='lists') {const extra=element('tr');const cell=element('td','field-help',`${value.create_lists} Listen neu · ${value.update_lists} Listen ändern · ${value.delete_lists} Listen löschen`);cell.colSpan=4;extra.append(cell);tbody.append(extra);}});table.append(tbody);b('backup-plan-counts').replaceChildren(table);
    Object.entries(plan.counts).forEach(([key,value])=>{if(value.reorder)b('backup-plan-counts').append(element('p','field-help',model.categories[key]+': Reihenfolge wird angepasst.'));});
    b('backup-plan-warnings').replaceChildren(); plan.warnings.forEach(text=>b('backup-plan-warnings').append(element('p','inline-warning',text)));
    b('backup-plan-examples').replaceChildren();Object.entries(plan.examples).forEach(([key,groups])=>{const details=element('details','analysis-block');details.append(element('summary','',model.categories[key]+' · Beispiele (max. 30 je Vorgang)'));Object.entries(groups).forEach(([action,values])=>{if(!values.length)return;details.append(element('h3','',({add:'Übernehmen',remove:'Entfernen',lists:'Listen',remove_lists:'Listen entfernen'})[action]));const ul=element('ul');values.forEach(text=>ul.append(element('li','',text)));details.append(ul);});b('backup-plan-examples').append(details);});
  }
  function confirm(title,description,word,action) {
    confirmAction=action;confirmWord=word;b('backup-confirm-title').textContent=title;b('backup-confirm-description').textContent=description;
    b('backup-confirm-label').textContent=`Zur Bestätigung ${word} eingeben`;b('backup-confirm-input').value='';b('backup-confirm-input').setCustomValidity('');b('backup-confirm-dialog').showModal();
  }
  b('backup-confirm-cancel').addEventListener('click',()=>b('backup-confirm-dialog').close());
  b('backup-confirm-input').addEventListener('input',()=>b('backup-confirm-input').setCustomValidity(''));
  b('backup-confirm-form').addEventListener('submit',event=>{event.preventDefault();if(b('backup-confirm-input').value!==confirmWord){b('backup-confirm-input').setCustomValidity('Bitte das angegebene Bestätigungswort exakt eingeben.');b('backup-confirm-input').reportValidity();return;}b('backup-confirm-dialog').close();act(confirmAction);});
  b('backup-create').addEventListener('click',()=>act(async()=>{const cats=selected('backup-create-categories');if(!cats.length)throw new Error('Mindestens einen Datenbereich auswählen.');await api('backup-create',{categories:cats,pinned:b('backup-create-pinned').checked});toast('Sicherung gestartet.');}));
  b('backup-select-all').addEventListener('click',()=>b('backup-create-categories').querySelectorAll('input').forEach(input=>{input.checked=true;}));
  b('backup-cancel').addEventListener('click',()=>act(()=>api('backup-cancel',{})));
  b('backup-upload').addEventListener('change',()=>act(async()=>{const file=b('backup-upload').files[0];if(!file)return;if(file.size>128*1024*1024)throw new Error('ZIP-Datei ist größer als 128 MiB.');const response=await fetch('api/backups/import',{method:'POST',headers:{'Content-Type':'application/zip','X-CSRF-Token':status.csrf},body:file});const result=await response.json();if(!response.ok)throw new Error(result.error||'Import fehlgeschlagen.');b('backup-upload').value='';toast('Archiv importiert und geprüft.');}));
  b('backup-settings-form').addEventListener('input',dirtyConfig);b('backup-settings-form').addEventListener('change',dirtyConfig);
  b('backup-settings-form').addEventListener('submit',event=>{event.preventDefault();if(!configDirty)return;act(async()=>{await api('backup-settings',{settings:readConfig(),revision:configSnapshot.revision});configDirty=false;toast('Sicherungseinstellungen gespeichert.');});});
  b('backup-settings-discard').addEventListener('click',()=>fillConfig(model.settings,model.revision));
  b('backup-add-schedule').addEventListener('click',()=>{addSchedule({id:[...crypto.getRandomValues(new Uint8Array(16))].map(x=>x.toString(16).padStart(2,'0')).join(''),name:'Neue Sicherung',enabled:true,frequency:'daily',time:'03:00',weekdays:[0],month_day:1,interval_hours:24,categories:[...model.restorable]});dirtyConfig();});
  b('backup-prune').addEventListener('click',()=>confirm('Aufbewahrung anwenden?',`${model.prunable.length} nicht mehr benötigte Archive werden anhand der gespeicherten Regeln endgültig gelöscht. Geschützte Archive bleiben erhalten.`,'BEREINIGEN',()=>api('backup-prune',{confirmation:'BEREINIGEN',revision:model.revision})));
  b('backup-restore-archive').addEventListener('change',()=>restoreSelection());
  ['backup-restore-mode','backup-restore-categories','backup-cross-account'].forEach(id=>b(id).addEventListener('change',()=>{planInvalidated=true;b('backup-plan').hidden=true;controls();
    b('backup-mode-help').textContent=b('backup-restore-mode').value==='merge'?'Vorhandene Einträge und abweichende Werte bleiben erhalten. Nur fehlende Einträge werden ergänzt.':b('backup-restore-mode').value==='mirror'?'Zusätzliche Einträge in den ausgewählten Bereichen werden entfernt. Die Vorschau zeigt alle vorgesehenen Änderungen.':'Gesicherte Bewertungen und Metadaten werden übernommen. Zusätzliche Einträge bleiben erhalten; für Metadaten können bestehende Einträge entfernt und neu angelegt werden.';
  }));
  b('backup-preview').addEventListener('click',()=>act(async()=>{const cats=selected('backup-restore-categories');if(!cats.length)throw new Error('Wiederherstellbare Bereiche auswählen.');await api('backup-preview',{id:selectedArchive,categories:cats,mode:b('backup-restore-mode').value,allow_other_account:b('backup-cross-account').checked});planInvalidated=false;toast('Vergleich gestartet. Die Vorschau erscheint nach Abschluss.');}));
  b('backup-restore').addEventListener('click',()=>{const plan=model.plan;if(!plan)return;confirm('Trakt-Daten wiederherstellen?',`Zielkonto: ${plan.target_account.username}. Es gelten ausschließlich die Bereiche und Änderungen dieser Vorschau. Zuerst wird eine geschützte Rückfallsicherung erstellt. Danach bleibt Sync pausiert.`,plan.confirmation,()=>api('backup-restore',{plan_id:plan.id,confirmation:plan.confirmation}));});
  ['backup-search','backup-scope-filter','backup-protected-filter'].forEach(id=>b(id).addEventListener('input',()=>model&&archiveRows()));
  let loading=false;
  async function load() {
    if(loading)return;loading=true;
    try {
      const next=await api('backups');const first=!model;model=next;
      if(first){categories('backup-create-categories',Object.keys(model.categories));Object.entries(model.categories).forEach(([key,title])=>{const option=element('option','',title);option.value=key;b('backup-scope-filter').append(option);});}
      if(!configDirty&&(!configSnapshot||configSnapshot.revision!==model.revision))fillConfig(model.settings,model.revision);
      b('backup-last').textContent=prettyDate(model.state.last_success);b('backup-storage').textContent=bytes(model.storage.used_bytes)+' / '+bytes(model.storage.quota_bytes);
      const due=model.settings.enabled?model.settings.schedules.filter(item=>item.enabled).map(item=>model.state.schedules[item.id]?.next_run).filter(Boolean):[];
      b('backup-next').textContent=due.length?prettyDate(Math.min(...due)):'Automatik aus';
      const job=model.state.job;b('backup-job').hidden=!job;b('backup-job').classList.toggle('danger',Boolean(job&&['failed','cancelled','interrupted'].includes(job.status)));
      if(job){b('backup-job-title').textContent=({create:'Sicherung',preview:'Wiederherstellungsvorschau',restore:'Wiederherstellung',verify:'Archivprüfung'})[job.kind]+' · '+({running:'Läuft',completed:'Abgeschlossen',failed:'Fehlgeschlagen',cancelled:'Abgebrochen',interrupted:'Unterbrochen'})[job.status];b('backup-job-message').textContent=job.message+(job.safety_archive?' · Rückfallsicherung: '+job.safety_archive:'')+(job.result?.message?' '+job.result.message:'');}
      if(model.storage.quota_exceeded){b('backup-error').hidden=false;b('backup-error').textContent='Archivkontingent überschritten. Geschützte und aufbewahrte Stände wurden nicht gelöscht. Speicherlimit oder Aufbewahrung prüfen.';}
      archiveRows();archiveSelect();renderPlan();updateScheduleTimes();b('backup-prune-preview').textContent=model.prunable.length+' Archive würden nach den gespeicherten Regeln entfernt. '+model.archives.filter(item=>!item.valid).length+' beschädigte Archive bleiben ausgenommen.';controls();
    } catch(error){b('backup-error').textContent=error.message;b('backup-error').hidden=false;}
    finally{loading=false;}
  }
  window.addEventListener('beforeunload',event=>{if(configDirty){event.preventDefault();event.returnValue='';}});
  window.addEventListener('hashchange',()=>{if(location.hash==='#backups')load();});
  document.addEventListener('pts-status-updated',controls);
  navigate();load();
  async function poll(){if(!requestPending&&!document.hidden&&(location.hash==='#backups'||model?.state.job?.status==='running'))await load();setTimeout(poll,5000);}
  setTimeout(poll,5000);
})();
