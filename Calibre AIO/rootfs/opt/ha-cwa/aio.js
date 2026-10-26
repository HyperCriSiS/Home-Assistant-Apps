/* Deployment shell only; native applications keep their own language settings. */
(() => {
  function homeAssistant() {
    let parent = window;
    for (let depth = 0; depth < 5; depth++) {
      try {
        const hass = parent.document.querySelector('home-assistant')?.hass;
        if (hass) return hass;
        if (parent === parent.parent) break;
        parent = parent.parent;
      } catch { break; }
    }
    return null;
  }
  const hass = homeAssistant();
  const language = hass?.locale?.language || hass?.language || navigator.language || 'en';
  const de = language.toLowerCase().startsWith('de');
  document.documentElement.lang = de ? 'de' : 'en';
  const text = de ? {
    library: 'Bibliothek', discover: 'Entdecken', navigation: 'Bereich auswählen',
    hint: 'Bücher finden. Bibliothek genießen.', frame: 'Bücher entdecken und Bibliothek verwalten',
    setupTitle: 'Administrator einrichten',
    setupHelp: 'Dein angemeldetes HA-Administratorkonto wird automatisch für Calibre AIO eingerichtet. Andere HA-Benutzer erhalten eigene Konten ohne Administratorrechte für die gemeinsame Bibliothek.',
    adopt: 'Einrichtung erneut versuchen',
    manual: 'Alternativ: In der HA-App-Konfiguration unter SSO → Administrator Deinen HA-Anmeldenamen eintragen und die App neu starten.',
    unavailable: 'Bitte diese Seite innerhalb von Home Assistant mit einem HA-Administratorkonto öffnen.',
    saving: 'Home Assistant prüft Deine Berechtigung und speichert die Konfiguration …',
    restarting: 'Gespeichert. Die App startet neu. Die Oberfläche öffnet sich automatisch, sobald sie bereit ist.',
    waitError: 'Gespeichert. Die Oberfläche ist noch nicht wieder erreichbar. Bitte später neu laden oder die App-Logs prüfen.',
    error: 'Einrichtung fehlgeschlagen. Bitte erneut versuchen oder die HA-App-Konfiguration verwenden.',
    restartError: 'Gespeichert. Der Neustart konnte nicht bestätigt werden. Bitte die App in Home Assistant neu starten und die Oberfläche erneut öffnen.',
    stages: {identity: 'HA-Anmeldenamen abfragen', info: 'App-Konfiguration lesen', save: 'Administrator speichern', restart: 'App neu starten'},
    failed: 'Dieser Schritt ist fehlgeschlagen: ',
    noLogin: 'Für Dein HA-Konto wurde kein unterstützter Anmeldename gefunden. Bitte die manuelle Konfiguration verwenden.',
    configured: 'Ein Administrator ist bereits konfiguriert. Die vorhandene Zuordnung bleibt erhalten. Bitte die App neu starten und die Oberfläche erneut öffnen.'
  } : {
    library: 'Library', discover: 'Discover', navigation: 'Choose section',
    hint: 'Find books. Enjoy your library.', frame: 'Discover books and manage your library',
    setupTitle: 'Set up administrator',
    setupHelp: 'Your signed-in HA administrator is being configured automatically for Calibre AIO. Other HA users receive their own accounts without administrator permissions for the shared library.',
    adopt: 'Retry setup',
    manual: 'Alternatively: Enter your HA login name under SSO → Administrator in the HA app configuration and restart the app.',
    unavailable: 'Open this page inside Home Assistant using an HA administrator account.',
    saving: 'Home Assistant is checking your permission and saving the configuration …',
    restarting: 'Saved. The app is restarting. The interface will reopen automatically when ready.',
    waitError: 'Saved. The interface is not reachable yet. Please reload later or check the app logs.',
    error: 'Setup failed. Please try again or use the HA app configuration.',
    restartError: 'Saved. Restart could not be confirmed. Please restart the app in Home Assistant and reopen its interface.',
    stages: {identity: 'Read HA login name', info: 'Read app configuration', save: 'Save administrator', restart: 'Restart app'},
    failed: 'This step failed: ',
    noLogin: 'No supported login name was found for your HA account. Please use manual configuration.',
    configured: 'An administrator is already configured. The existing assignment is preserved. Please restart the app and reopen its interface.'
  };
  document.querySelectorAll('[data-text]').forEach(el => { el.textContent = text[el.dataset.text]; });
  const frame = document.querySelector('iframe');
  const nav = document.querySelector('nav');
  const links = [...nav.querySelectorAll('a')];
  nav.setAttribute('aria-label', text.navigation);
  frame.title = text.frame;
  document.querySelector('.hint').textContent = text.hint;
  links.forEach(a => { a.textContent = text[a.dataset.view]; });
  function select(view) {
    links.forEach(a => {
      if (a.dataset.view === view) a.setAttribute('aria-current', 'page');
      else a.removeAttribute('aria-current');
    });
  }
  links.forEach(a => a.addEventListener('click', () => select(a.dataset.view)));
  frame.addEventListener('load', () => {
    try {
      select(frame.contentWindow.location.pathname.includes('/library/') ? 'library' : 'discover');
      // Shelfmark's native library link opens a new tab. Keep only links to
      // our own CWA deployment inside the shared workspace instead.
      if (frame.contentWindow.location.pathname.includes('/shelfmark/')) {
        frame.contentDocument.addEventListener('click', event => {
          const anchor = event.target.closest?.('a[href]');
          if (!anchor || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
          const target = new URL(anchor.href);
          const library = new URL('library/', document.baseURI);
          if (target.origin !== library.origin || !target.pathname.startsWith(library.pathname)) return;
          event.preventDefault();
          frame.src = target.href;
          select('library');
        }, true);
      }
    }
    catch { /* Native application may still be loading. */ }
  });
  if (document.body.dataset.setupRequired !== 'true') return;
  frame.hidden = nav.hidden = true;
  document.querySelector('.hint').hidden = true;
  document.querySelector('.setup').hidden = false;
  const button = document.querySelector('#adopt');
  const status = document.querySelector('#status');
  const slug = document.body.dataset.appSlug;
  if (!hass?.user?.is_admin || !/^[A-Za-z0-9_-]+$/.test(slug)) {
    status.textContent = text.unavailable;
    return;
  }
  button.hidden = true;
  async function reopenWhenReady() {
    // Root may already respond while a backend is still starting. Require a
    // freshly rendered configured shell and both backends before reloading.
    for (let attempt = 0; attempt < 90; attempt++) {
      try {
        const root = await fetch(document.baseURI, {cache: 'no-store', signal: AbortSignal.timeout(5000)});
        if (root.ok) {
          const page = new DOMParser().parseFromString(await root.text(), 'text/html');
          if (page.body.dataset.setupRequired === 'false' && page.body.dataset.appSlug === slug) {
            const backends = await Promise.all(['library/', 'shelfmark/'].map(path =>
              fetch(new URL(path, document.baseURI), {cache: 'no-store', signal: AbortSignal.timeout(5000)})));
            if (backends.every(response => response.ok)) {
              window.location.reload();
              return;
            }
          }
        }
      } catch { /* Connection failures are expected while the app restarts. */ }
      await new Promise(resolve => setTimeout(resolve, 2000));
    }
    status.textContent = text.waitError;
  }
  async function configureAdministrator() {
    button.disabled = true;
    button.hidden = true;
    status.textContent = text.saving;
    let saved = false;
    let stage = 'identity';
    try {
      // Both calls are authorized by HA itself. No app-held HA token or
      // client-supplied role flag grants permission to change app options.
      const users = await hass.callWS({type: 'config/auth/list'});
      const user = users.find(u => u.id === hass.user.id && u.is_active && u.username);
      if (!user) {
        status.textContent = text.noLogin;
        return;
      }
      const endpoint = '/addons/' + slug;
      // Match HA's own frontend: supervisor/api unwraps data and rejects on
      // errors. Successful writes may resolve to an empty object or null.
      const supervisor = (suffix, method, data) => hass.callWS({
        type: 'supervisor/api', endpoint: endpoint + suffix, method,
        ...(data === undefined ? {} : {data}),
        ...(suffix === '/restart' ? {timeout: null} : {})
      });
      stage = 'info';
      const info = await supervisor('/info', 'get');
      if (!info?.options || typeof info.options !== 'object') throw new Error('App options unavailable');
      if (info.options.sso?.admin_username?.trim()) {
        status.textContent = text.configured;
        return;
      }
      const options = {...info.options, sso: {...info.options.sso, admin_username: user.username}};
      stage = 'save';
      await supervisor('/options', 'post', {options});
      saved = true;
      stage = 'restart';
      await supervisor('/restart', 'post');
      status.textContent = text.restarting;
      await reopenWhenReady();
    } catch {
      status.textContent = saved ? text.restartError : text.failed + text.stages[stage] + '. ' + text.error;
      button.disabled = saved;
      button.hidden = saved;
    }
  }
  button.addEventListener('click', configureAdministrator);
  // HA authorizes both identity lookup and configuration writes server-side.
  // Only an unconfigured installation and a signed-in HA admin reach this path.
  configureAdministrator();
})();
