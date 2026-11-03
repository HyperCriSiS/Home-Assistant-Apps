/* Native CWA links keep their URLs, tooltips and server-side sorting. */
(() => {
  'use strict';
  const svg = paths => {
    const node = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    for (const [key, value] of Object.entries({viewBox:'0 0 24 24', fill:'none',
      stroke:'currentColor', 'stroke-width':'1.65', 'stroke-linecap':'round',
      'stroke-linejoin':'round', 'aria-hidden':'true', focusable:'false'})) node.setAttribute(key, value);
    for (const d of paths) {
      const path = document.createElementNS(node.namespaceURI, 'path');
      path.setAttribute('d', d); node.append(path);
    }
    return node;
  };
  const icons = {
    author: ['M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0', 'M4 21v-2a8 8 0 0 1 16 0v2'],
    added: ['M4 4h6a3 3 0 0 1 3 3v14a4 4 0 0 0-4-2H4z', 'M13 8h7v11h-3', 'M17 2v6M14 5h6'],
    published: ['M5 5h14v16H5z', 'M8 2v6M16 2v6M5 10h14', 'M9 14h2v3H9z'],
    series: ['M4 5h12M4 12h12M4 19h12', 'M20 4v2M20 11v2M20 18v2'],
    downloads: ['M12 3v12M7 10l5 5 5-5', 'M4 17v4h16v-4']
  };
  const sorts = {new:['added','down'], old:['added','up'], asc:['title','up'],
    desc:['title','down'], auth_az:['author','up'], auth_za:['author','down'],
    pub_new:['published','down'], pub_old:['published','up'],
    series_asc:['series','up'], series_desc:['series','down'],
    hot_asc:['downloads','up'], hot_desc:['downloads','down']};
  document.documentElement.classList.add('aio-modern');
  const german = document.documentElement.lang.startsWith('de');
  for (const link of document.querySelectorAll('.filterheader a[id], .filterheader div#asc, .filterheader div#desc')) {
    const sort = sorts[link.id];
    if (!sort) continue;
    const isList = link.hasAttribute('data-id');
    if (!isList && !link.getAttribute('href')) continue;
    const [kind, direction] = sort;
    const label = link.getAttribute('title') || link.getAttribute('data-original-title') ||
      (direction === 'up' ? (german ? 'Aufsteigend sortieren' : 'Sort ascending') : (german ? 'Absteigend sortieren' : 'Sort descending'));
    if (label) link.setAttribute('aria-label', label);
    const symbol = kind === 'title' ? document.createElement('span') : svg(icons[kind]);
    if (kind === 'title') { symbol.textContent = 'A–Z'; symbol.setAttribute('aria-hidden', 'true'); }
    const arrow = svg(direction === 'up' ? ['M12 20V4M6 10l6-6 6 6'] : ['M12 4v16M6 14l6 6 6-6']);
    arrow.classList.add('aio-sort-arrow');
    link.replaceChildren(symbol, arrow);
    link.classList.add('aio-sort');
    link.dataset.sortKind = kind; link.dataset.sortDirection = direction;
    if (link.classList.contains('active')) link.setAttribute('aria-current', 'true');
  }
  const listSort = document.querySelector('.filterheader #asc[data-id]');
  if (listSort) {
    const toolbar = listSort.parentElement;
    toolbar.parentElement.classList.add('aio-list-page');
    const name = toolbar.querySelector('#sort_name');
    if (name) {
      name.replaceChildren(svg(icons.author), svg(['M4 8h16l-4-4M20 16H4l4 4']));
      name.classList.add('aio-sort');
      name.setAttribute('aria-label', german ? 'Namensdarstellung wechseln' : 'Switch name display');
    }
    for (const control of toolbar.querySelectorAll('div.btn')) {
      control.setAttribute('role', 'button');
      control.tabIndex = 0;
      control.title = control.getAttribute('aria-label') || control.textContent.trim();
      const sync = () => {
        control.setAttribute('aria-pressed', String(control.classList.contains('active')));
        control.removeAttribute('aria-current');
      };
      sync();
      new MutationObserver(sync).observe(control, {attributes:true, attributeFilter:['class']});
      control.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); control.click(); }
      });
    }
  }
  const search = document.querySelector('form[role="search"]');
  if (search) {
    const icon = svg(['M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0', 'm15 15 6 6']);
    icon.classList.add('aio-search-icon');
    search.querySelector('.input-group').prepend(icon);
    const submit = search.querySelector('#query_submit');
    submit.setAttribute('aria-label', submit.textContent.trim());
    submit.title = submit.textContent.trim();
    submit.replaceChildren(svg(['M4 12h16M14 6l6 6-6 6']));
  }
})();
