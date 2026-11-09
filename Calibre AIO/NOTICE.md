# Third-party components

This Home Assistant wrapper includes third-party software. The MIT license in
this directory (`LICENSE`) applies to the wrapper code maintained here;
third-party components retain their own licenses and copyright notices.
Packaged versions are pinned in `upstream.json`.

## Calibre-Web Automated

- Project: https://github.com/crocodilestick/Calibre-Web-Automated
- Version currently packaged: v4.0.8
- License: GPL-3.0-or-later, see `LICENSE-CWA`

## Shelfmark

- Project: https://github.com/calibrain/shelfmark
- Version currently packaged: v1.6.1
- License: MIT, see `LICENSE-SHELFMARK`

## Calibre

- Project: https://calibre-ebook.com
- Version currently packaged: 9.1.0
- License: GPL-3.0, retained inside the packaged distribution

## kepubify

- Project: https://github.com/pgaskin/kepubify
- Version currently packaged: v4.0.4
- License: MIT, retained inside the packaged distribution

## Original add-on packaging

Calibre AIO starts from Conall O'Brien's Home Assistant Calibre-Web Automated
packaging, with the HA SSO work from `HyperCriSiS/hassio-addons-by-conallob`
commit `44bd206`.

- License: BSD 3-Clause, see `LICENSE-BASE-ADDON`

The build fetches upstream source distributions and does not replace their
licenses or imply endorsement by their maintainers.
