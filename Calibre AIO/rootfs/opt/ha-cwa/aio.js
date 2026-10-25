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
    setupHelp: 'Übernimm Deinen angemeldeten Home-Assistant-Administrator für Calibre AIO. Andere Benutzer erhalten normale Rechte.',
    adopt: 'Angemeldeten Administrator übernehmen und neu starten',
    manual: 'Alternativ: In der HA-App-Konfiguration unter SSO → Administrator Deinen HA-Anmeldenamen eintragen und die App neu starten.',
    unavailable: 'Bitte diese Seite innerhalb von Home Assistant mit einem HA-Administratorkonto öffnen.',
    saving: 'Home Assistant prüft Deine Berechtigung und speichert die Konfiguration …',
    restarting: 'Gespeichert. Die App startet neu. Bitte anschließend die Oberfläche erneut öffnen.',
    error: 'Einrichtung fehlgeschlagen. Bitte erneut versuchen oder die HA-App-Konfiguration verwenden.',
    restartError: 'Gespeichert. Der Neustart konnte nicht bestätigt werden. Bitte die App in Home Assistant neu starten und die Oberfläche erneut öffnen.'
  } : {
    library: 'Library', discover: 'Discover', navigation: 'Choose section',
    hint: 'Find books. Enjoy your library.', frame: 'Discover books and manage your library',
    setupTitle: 'Set up administrator',
    setupHelp: 'Use your signed-in Home Assistant administrator for Calibre AIO. Other users receive standard permissions.',
    adopt: 'Use signed-in administrator and restart',
    manual: 'Alternatively: Enter your HA login name under SSO → Administrator in the HA app configuration and restart the app.',
    unavailable: 'Open this page inside Home Assistant using an HA administrator account.',
    saving: 'Home Assistant is checking your permission and saving the configuration …',
    restarting: 'Saved. The app is restarting. Please reopen its interface afterwards.',
    error: 'Setup failed. Please try again or use the HA app configuration.',
    restartError: 'Saved. Restart could not be confirmed. Please restart the app in Home Assistant and reopen its interface.'
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
    try { select(frame.contentWindow.location.pathname.includes('/library/') ? 'library' : 'discover'); }
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
  button.disabled = false;
  button.addEventListener('click', async () => {
    button.disabled = true;
    status.textContent = text.saving;
    let saved = false;
    try {
      // Both calls are authorized by HA itself. No app-held HA token or
      // client-supplied role flag grants permission to change app options.
      const users = await hass.callWS({type: 'config/auth/list'});
      const user = users.find(u => u.id === hass.user.id && u.is_active && u.username);
      if (!user) throw new Error('HA login unavailable');
      const endpoint = 'hassio/addons/' + slug;
      const info = await hass.callApi('GET', endpoint + '/info');
      if (info?.result !== 'ok' || !info.data?.options) throw new Error('App options unavailable');
      const options = {...info.data.options, sso: {...info.data.options.sso, admin_username: user.username}};
      const result = await hass.callApi('POST', endpoint + '/options', {options});
      if (result?.result !== 'ok') throw new Error('Options rejected');
      saved = true;
      const restart = await hass.callApi('POST', endpoint + '/restart');
      if (restart?.result !== 'ok') throw new Error('Restart rejected');
      status.textContent = text.restarting;
    } catch {
      status.textContent = saved ? text.restartError : text.error;
      button.disabled = saved;
    }
  });
})();
