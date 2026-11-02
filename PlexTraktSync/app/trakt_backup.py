"""Authenticated, bounded Trakt snapshots and explicit restore plans.

This client is separate from the sync worker. Restore writes never inherit sync
permissions: the service requires a current, account-bound preview and approval.
"""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import re
import time

import requests

from backup_store import CATEGORIES, RESTORABLE, digest, number, selection
from storage import read, write

SECTIONS = ('calendar', 'progress_watched', 'progress_collected', 'recommendations')
PLURAL = {'movie': 'movies', 'show': 'shows', 'season': 'seasons', 'episode': 'episodes', 'person': 'people'}
META = ('media_type', 'resolution', 'hdr', 'audio', 'audio_channels', '3d')


def text(value, maximum=10000):
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError('Ungültiger Text in Sicherungsdaten.')
    return value


def timestamp(value):
    if value in (None, 'unknown'):
        return 'unknown'
    try:
        parsed = datetime.fromisoformat(text(value, 64).replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError()
        return parsed.astimezone(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')
    except ValueError:
        raise ValueError('Ungültiger UTC-Zeitpunkt in Sicherungsdaten.') from None


def identifiers(value):
    if not isinstance(value, dict) or type(value.get('trakt')) is not int or not 0 < value['trakt'] <= 2**63 - 1:
        raise ValueError('Medien benötigen eine eindeutige Trakt-ID.')
    result = {'trakt': value['trakt']}
    for key in ('tmdb', 'tvdb'):
        if value.get(key) is not None:
            result[key] = number(value[key], 1, 2**63 - 1)
    if value.get('imdb'):
        if not isinstance(value['imdb'], str) or not re.fullmatch(r'(?:tt|nm)[0-9]{1,16}', value['imdb']):
            raise ValueError('Ungültige IMDb-ID.')
        result['imdb'] = value['imdb']
    return result


def media(kind, obj):
    if kind not in PLURAL or not isinstance(obj, dict):
        raise ValueError('Nicht unterstützter Medientyp im Archiv.')
    ids = identifiers(obj.get('ids'))
    return {'kind': kind, 'ids': ids, 'key': kind + ':' + str(ids['trakt']),
            'title': text(obj.get('title') or obj.get('name') or str(ids['trakt']), 1000)}


def record(category, row):
    """Normalize our portable record format; derive keys instead of trusting uploads."""
    if not isinstance(row, dict):
        raise ValueError('Ungültiger Datensatz im Archiv.')
    r = media(row.get('kind'), row)
    if category == 'history':
        if r['kind'] not in ('movie', 'episode'):
            raise ValueError('Verlauf muss einzelne Filme oder Episoden enthalten.')
        r['watched_at'] = timestamp(row.get('watched_at'))
        r['key'] += '@' + r['watched_at']
        if row.get('event_id') is not None:
            r['event_id'] = number(row['event_id'], 1, 2**63 - 1)
    elif category == 'ratings':
        if r['kind'] == 'person':
            raise ValueError('Personenbewertungen werden nicht unterstützt.')
        r['rating'] = number(row.get('rating'), 1, 10)
        r['rated_at'] = timestamp(row.get('rated_at'))
    elif category in ('watchlist', 'favorites'):
        if r['kind'] == 'person' or (category == 'favorites' and r['kind'] not in ('movie', 'show')):
            raise ValueError('Nicht unterstützter Listentyp.')
        r['notes'] = text(row.get('notes') or '', 5000)
        r['rank'] = number(row.get('rank', 0), 0, 2**63 - 1)
        if row.get('item_id') is not None:
            r['item_id'] = number(row['item_id'], 1, 2**63 - 1)
    elif category == 'collection':
        if r['kind'] not in ('movie', 'show'):
            raise ValueError('Ungültiger Sammlungstyp.')
        if r['kind'] == 'show':
            r['season'] = number(row.get('season'), 0, 100000)
            r['episode'] = number(row.get('episode'), 0, 100000)
            r['key'] += ':' + str(r['season']) + ':' + str(r['episode'])
        r['collected_at'] = timestamp(row.get('collected_at'))
        for key in META:
            value = row.get(key)
            if value is not None:
                if key == '3d':
                    if type(value) is not bool:
                        raise ValueError('Ungültige Sammlungsmetadaten.')
                else:
                    text(value, 100)
            r[key] = value
    elif category == 'hidden':
        if row.get('section') not in SECTIONS:
            raise ValueError('Ungültiger Ausblendungsbereich.')
        allowed = ('show', 'season') if row['section'].startswith('progress_') else ('movie', 'show')
        if r['kind'] not in allowed:
            raise ValueError('Nicht unterstützter Medientyp für diesen Ausblendungsbereich.')
        r['section'] = row['section']
        r['key'] = r['section'] + ':' + r['key']
    elif category == 'playback':
        if r['kind'] not in ('movie', 'episode'):
            raise ValueError('Abspielfortschritt muss einen Film oder eine Episode betreffen.')
        value = row.get('progress')
        if type(value) not in (int, float) or not 0 <= value <= 100:
            raise ValueError('Ungültiger Abspielfortschritt.')
        r['progress'] = value
        r['paused_at'] = timestamp(row.get('paused_at'))
    elif category == 'list-items':
        r['notes'] = text(row.get('notes') or '', 5000)
        if row.get('item_id') is not None:
            r['item_id'] = number(row['item_id'], 1, 2**63 - 1)
    return r


def normalize_capture(data):
    if not isinstance(data, dict):
        raise ValueError('Ungültige Sicherungsdaten.')
    selection(list(data))
    result = {}
    for category, rows in data.items():
        if not isinstance(rows, list) or len(rows) > 2000000:
            raise ValueError('Ungültiger Sicherungsumfang.')
        if category == 'lists':
            result[category] = []
            for row in rows:
                if not isinstance(row, dict):
                    raise ValueError('Ungültige Liste.')
                identifier = number(row.get('id'), 1, 2**63 - 1)
                if not text(row.get('name'), 255).strip():
                    raise ValueError('Listen benötigen einen nicht leeren Namen.')
                if row.get('privacy') not in ('private', 'link', 'friends', 'public'):
                    raise ValueError('Ungültige Listensichtbarkeit.')
                items = row.get('items')
                if not isinstance(items, list) or len(items) > 2000000:
                    raise ValueError('Ungültige Listeninhalte.')
                normalized = [record('list-items', item) for item in items]
                if len({item['key'] for item in normalized}) != len(normalized):
                    raise ValueError('Doppelte Einträge in einer Liste.')
                result[category].append({'id': identifier, 'key': 'list:' + str(identifier),
                    'name': text(row.get('name'), 255), 'description': text(row.get('description') or '', 10000),
                    'privacy': row['privacy'], 'items': normalized})
        else:
            result[category] = [record(category, row) for row in rows]
        if category != 'history' and len({row['key'] for row in result[category]}) != len(result[category]):
            raise ValueError('Doppelte Datensätze in Sicherungsdaten.')
    return result


class TraktClient:
    def __init__(self, directory, timeout=30, *, stop=None, deadline=None, progress=None):
        self.directory = directory
        self.timeout = min(timeout, 30)
        self.stop = stop
        self.deadline = deadline or time.monotonic() + 7200
        self.progress = progress or (lambda message: None)
        self.session = requests.Session()
        self.last_write = 0
        self.token = read(directory / '.pytrakt.json', {})
        if not self.token.get('OAUTH_TOKEN') or not self.token.get('CLIENT_ID'):
            raise ValueError('Bitte zuerst Trakt autorisieren.')

    def check(self):
        if (self.stop and self.stop.is_set()) or time.monotonic() >= self.deadline:
            raise ValueError('Sicherungsauftrag abgebrochen oder Zeitlimit erreicht.')

    def close(self):
        self.session.close()

    def wait(self, seconds):
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            self.check()
            time.sleep(min(.25, max(0, until - time.monotonic())))

    def refresh(self):
        if self.token.get('OAUTH_EXPIRES_AT', 0) > time.time() + 120:
            return
        payload = {'refresh_token': self.token.get('OAUTH_REFRESH'), 'client_id': self.token['CLIENT_ID'],
                   'grant_type': 'refresh_token', 'redirect_uri': 'urn:ietf:wg:oauth:2.0:oob'}
        if self.token.get('CLIENT_SECRET'):
            payload['client_secret'] = self.token['CLIENT_SECRET']
        self.check()
        try:
            response = self.session.post('https://api.trakt.tv/oauth/token', json=payload,
                                         timeout=self.timeout, allow_redirects=False)
            if response.status_code != 200:
                raise ValueError('Trakt-Autorisierung konnte nicht erneuert werden.')
            data = response.json()
            self.token.update(OAUTH_TOKEN=data['access_token'], OAUTH_REFRESH=data['refresh_token'],
                              OAUTH_EXPIRES_AT=data['created_at'] + data['expires_in'])
            write(self.directory / '.pytrakt.json', self.token)
        except (requests.RequestException, KeyError):
            raise ValueError('Trakt-Autorisierung konnte nicht erneuert werden. Erneut verbinden.') from None

    def request(self, method, path, payload=None, params=None):
        if not re.fullmatch(r'/(?:sync/(?:last_activities|history(?:/remove)?|ratings(?:/(?:movies|shows|seasons|episodes|remove))?|watchlist(?:/(?:remove|reorder))?|favorites(?:/(?:remove|reorder))?|collection/(?:movies|shows)|collection(?:/remove)?|playback)|users/settings|users/me/lists(?:/[0-9]+(?:/items(?:/(?:remove|reorder))?)?)?|users/hidden/(?:calendar|progress_watched|progress_collected|recommendations)(?:/remove)?)', path):
            raise ValueError('Nicht erlaubter Trakt-Endpunkt.')
        if method not in ('GET', 'POST', 'PUT', 'DELETE'):
            raise ValueError('Nicht erlaubte API-Methode.')
        self.check()
        self.refresh()
        for attempt in range(4 if method == 'GET' else 1):
            self.check()
            if method != 'GET':
                self.wait(max(0, self.last_write + 1.1 - time.monotonic()))
                self.last_write = time.monotonic()
            try:
                response = self.session.request(method, 'https://api.trakt.tv' + path, json=payload, params=params,
                    headers={'Authorization': 'Bearer ' + self.token['OAUTH_TOKEN'], 'trakt-api-version': '2',
                             'trakt-api-key': self.token['CLIENT_ID'], 'Content-Type': 'application/json'},
                    timeout=min(self.timeout, max(1, self.deadline - time.monotonic())), allow_redirects=False)
            except requests.RequestException:
                if method == 'GET' and attempt < 3:
                    self.wait(2 ** attempt)
                    continue
                raise ValueError('Trakt-Verbindung fehlgeschlagen. Schreibanfragen werden nicht automatisch wiederholt; zuerst neu vergleichen.') from None
            if method == 'GET' and (response.status_code == 429 or response.status_code >= 500) and attempt < 3:
                delay = response.headers.get('Retry-After', '')
                self.wait(max(2 ** attempt, int(delay) if delay.isdecimal() else 2 ** attempt))
                continue
            if not 200 <= response.status_code < 300:
                raise ValueError(f'Trakt antwortet mit HTTP {response.status_code}. Auftrag gestoppt; keine automatische Schreibwiederholung.')
            self.check()
            if response.status_code == 204:
                return {}, response.headers
            try:
                return response.json(), response.headers
            except ValueError:
                raise ValueError('Trakt lieferte ungültige Daten.') from None
        raise ValueError('Trakt ist vorübergehend nicht erreichbar.')

    def get(self, path):
        return self.request('GET', path)[0]

    def pages(self, path, **params):
        result = []
        previous = None
        for page in range(1, 10001):
            values, headers = self.request('GET', path, params={**params, 'page': page, 'limit': 250})
            if not isinstance(values, list):
                raise ValueError('Unerwartetes Trakt-Listenformat.')
            page_digest = digest(values)
            if values and previous == page_digest:
                raise ValueError('Trakt wiederholt eine Ergebnisseite. Sicherung nicht als vollständig gespeichert.')
            previous = page_digest
            result.extend(values)
            if len(result) > 2000000:
                raise ValueError('Sicherungsumfang überschreitet zwei Millionen Einträge pro Bereich.')
            count = headers.get('X-Pagination-Page-Count')
            if count is not None:
                if not str(count).isdecimal() or int(count) > 10000:
                    raise ValueError('Ungültige Trakt-Seitenzahl.')
                if page >= int(count):
                    return result
                if not values:
                    raise ValueError('Unvollständige Trakt-Paginierung.')
            elif len(values) < 250:
                return result
        raise ValueError('Zu viele Trakt-Ergebnisseiten.')

    def account(self):
        data = self.get('/users/settings')['user']
        identifier = data.get('ids', {}).get('uuid') or data.get('ids', {}).get('slug') or data.get('username')
        if not isinstance(identifier, str) or not identifier:
            raise ValueError('Trakt-Konto konnte nicht eindeutig bestimmt werden.')
        return {'id': identifier, 'username': text(data['username'], 128)}

    def capture(self, categories):
        result = {}
        for category in selection(categories):
            self.progress('Lese ' + CATEGORIES[category] + ' …')
            rows = []
            if category in ('history', 'watchlist', 'favorites', 'playback'):
                sorting = {'sort_by': 'rank', 'sort_how': 'asc'} if category in ('watchlist', 'favorites') else {}
                for source in self.pages('/sync/' + category, **sorting):
                    kind = source['type']
                    row = media(kind, source[kind])
                    if category == 'history':
                        row.update(watched_at=source.get('watched_at'), event_id=source['id'])
                    elif category == 'playback':
                        row.update(progress=source['progress'], paused_at=source.get('paused_at'))
                    else:
                        row.update(notes=source.get('notes'), rank=source.get('rank', 0), item_id=source.get('id'))
                    rows.append(row)
            elif category == 'ratings':
                for plural in ('movies', 'shows', 'seasons', 'episodes'):
                    for source in self.pages('/sync/ratings/' + plural):
                        kind = source['type']
                        rows.append({**media(kind, source[kind]), 'rating': source['rating'], 'rated_at': source.get('rated_at')})
            elif category == 'collection':
                for source in self.pages('/sync/collection/movies', extended='metadata'):
                    rows.append({**media('movie', source['movie']), 'collected_at': source.get('collected_at'),
                                 **{key: (source.get('metadata') or {}).get(key) for key in META}})
                for source in self.pages('/sync/collection/shows', extended='metadata'):
                    if not isinstance(source.get('seasons'), list) or not source['seasons']:
                        raise ValueError('Trakt lieferte eine Sammlung ohne vollständige Staffeldaten.')
                    for season in source['seasons']:
                        if not isinstance(season.get('episodes'), list) or not season['episodes']:
                            raise ValueError('Trakt lieferte eine Sammlung ohne vollständige Episodendaten.')
                        for episode in season['episodes']:
                            rows.append({**media('show', source['show']), 'season': season['number'], 'episode': episode['number'],
                                'collected_at': episode.get('collected_at'), **{key: (episode.get('metadata') or {}).get(key) for key in META}})
            elif category == 'hidden':
                for section in SECTIONS:
                    for source in self.pages('/users/hidden/' + section):
                        kind = source['type']
                        rows.append({**media(kind, source[kind]), 'section': section})
            elif category == 'lists':
                for source in self.pages('/users/me/lists'):
                    identifier = source['ids']['trakt']
                    items = []
                    for item in self.pages('/users/me/lists/' + str(identifier) + '/items', sort_by='rank', sort_how='asc'):
                        kind = item['type']
                        items.append({**media(kind, item[kind]), 'notes': item.get('notes'), 'item_id': item.get('id')})
                    rows.append({'id': identifier, 'name': source['name'], 'description': source.get('description'),
                                 'privacy': source['privacy'], 'items': items})
            result[category] = rows
        return normalize_capture(result)

    def snapshot(self, categories):
        for attempt in range(3):
            before = self.get('/sync/last_activities')
            account = self.account()
            data = self.capture(categories)
            after = self.get('/sync/last_activities')
            if before == after:
                return account, data
            self.progress('Trakt wurde während der Sicherung verändert. Lese erneut …')
        raise ValueError('Trakt ändert sich während des Lesens. Kein vollständiger Stand gespeichert; später erneut versuchen.')


def content(row):
    # Catalogue IDs/titles can change independently of the user's data. Trakt ID
    # in the derived key determines identity; a restore cannot edit the catalogue.
    return {key: value for key, value in row.items() if key not in ('event_id', 'item_id', 'title', 'rank', 'ids')}


def order_changed(source, current):
    wanted = [row['key'] for row in source]
    existing = [row['key'] for row in current]
    target = [key for key in wanted if key in set(existing)] + [key for key in existing if key not in set(wanted)]
    return target != existing


def equivalent(source, current):
    a, b = content(source), content(current)
    for key in ('rated_at', 'collected_at'):
        if a.get(key) == 'unknown':
            a.pop(key, None)
            b.pop(key, None)
    return a == b


def differences(category, source, current, mode):
    add, remove, skip = [], [], 0
    if category == 'history':
        available = Counter(row['key'] for row in current)
        wanted = Counter(row['key'] for row in source)
        for row in source:
            if available[row['key']]:
                available[row['key']] -= 1
                skip += 1
            else:
                add.append(row)
        if mode == 'mirror':
            for row in current:
                if wanted[row['key']]:
                    wanted[row['key']] -= 1
                else:
                    if not row.get('event_id'):
                        raise ValueError('Trakt-Verlauf ohne Ereignis-ID kann nicht gezielt entfernt werden.')
                    remove.append(row)
    else:
        existing = {row['key']: row for row in current}
        wanted = {row['key'] for row in source}
        for row in source:
            old = existing.get(row['key'])
            if old is None:
                add.append(row)
            elif mode != 'merge' and not equivalent(row, old):
                # Ratings support updating. Other metadata is reset by remove/add.
                if category != 'ratings':
                    remove.append(old)
                add.append(row)
            else:
                skip += 1
        if mode == 'mirror':
            remove.extend(row for row in current if row['key'] not in wanted)
    return {'add': add, 'remove': remove, 'skip': skip}


def build_plan(source, current, categories, mode):
    if mode not in ('merge', 'overwrite', 'mirror'):
        raise ValueError('Ungültiger Wiederherstellungsmodus.')
    categories = selection(categories, restore=True)
    if not set(categories) <= set(source):
        raise ValueError('Ausgewählte Bereiche fehlen im Archiv.')
    plan = {'mode': mode, 'categories': categories, 'changes': {}, 'counts': {}, 'warnings': [
        'Trakt-Ereignis-IDs und Eintrags-Erstellzeiten werden neu vergeben. Der ursprüngliche Scrobble-Ursprung ist nicht wiederherstellbar.',
        'Die Wiederherstellung ist kein serverseitiger atomarer Vorgang. Bei Fehlern können bereits bestätigte Teilschritte erfolgt sein.',
    ]}
    for category in categories:
        if category != 'lists':
            change = differences(category, source[category], current[category], mode)
        else:
            change = {'lists': [], 'remove_lists': [], 'skip': 0}
            remaining = {row['id']: row for row in current[category]}
            for row in source[category]:
                old = remaining.get(row['id'])
                if old is None:
                    matches = [item for item in remaining.values() if item['name'] == row['name']]
                    if len(matches) > 1:
                        raise ValueError('Mehrdeutiger Listenname. Listen zuerst in Trakt eindeutig benennen.')
                    old = matches[0] if matches else None
                if old:
                    remaining.pop(old['id'])
                entry = {'source': row, 'target_id': old['id'] if old else None,
                         **differences('list-items', row['items'], old['items'] if old else [], mode),
                         'reorder': bool(old and mode != 'merge' and order_changed(row['items'], old['items'])),
                         'update_metadata': bool(old and mode != 'merge' and any(old[k] != row[k] for k in ('name', 'description', 'privacy')))}
                change['lists'].append(entry)
            if mode == 'mirror':
                change['remove_lists'] = list(remaining.values())
        plan['changes'][category] = change
        if category == 'lists':
            plan['counts'][category] = {
                'add': sum(len(item['add']) for item in change['lists']),
                'remove': sum(len(item['remove']) for item in change['lists']) + sum(len(item['items']) for item in change['remove_lists']),
                'create_lists': sum(item['target_id'] is None for item in change['lists']),
                'delete_lists': len(change['remove_lists']),
                'update_lists': sum(item['update_metadata'] for item in change['lists']),
                'reorder': sum(item['reorder'] for item in change['lists']),
                'skip': sum(item['skip'] for item in change['lists']),
            }
            if any(item['source']['privacy'] != 'private' and (item['target_id'] is None or item['update_metadata']) for item in change['lists']):
                plan['warnings'].append('Listen werden mit der Sichtbarkeit aus der Sicherung angelegt/aktualisiert; darunter sind nicht private Listen.')
        else:
            plan['counts'][category] = {'add': len(change['add']), 'remove': len(change['remove']), 'skip': change['skip']}
            if category in ('watchlist', 'favorites'):
                plan['counts'][category]['reorder'] = int(mode != 'merge' and order_changed(source[category], current[category]))
    plan['destructive'] = any(row['remove'] or row.get('delete_lists', 0) for row in plan['counts'].values())
    if 'watchlist' in categories:
        plan['warnings'].append('Trakt kann Watchlist-Einträge automatisch entfernen, wenn Medien als gesehen eingetragen werden.')
    if mode != 'merge':
        plan['warnings'].append('Die Reihenfolge unterstützter Listen wird an die Sicherung angepasst. Neue interne IDs und Erstellzeiten bleiben unvermeidbar.')
    if any(row.get('rated_at') == 'unknown' or row.get('collected_at') == 'unknown'
           for category in categories if category != 'lists' for row in source[category]):
        plan['warnings'].append('Einzelne Bewertungs-/Sammlungszeitpunkte fehlen im Archiv. Trakt kann dafür neue Standardzeitpunkte vergeben; bekannte Werte werden erhalten.')
    return plan


def payload(rows, category):
    body = {}
    if category == 'history-remove':
        return {'ids': [row['event_id'] for row in rows]}
    for row in rows:
        item = {'ids': {'trakt': row['ids']['trakt']}}
        if category == 'history':
            item['watched_at'] = row['watched_at']
        elif category == 'ratings':
            item.update(rating=row['rating'])
            if row['rated_at'] != 'unknown':
                item['rated_at'] = row['rated_at']
        elif category in ('watchlist', 'favorites', 'list-items'):
            item['notes'] = row['notes']
        elif category == 'collection':
            extra = {key: row[key] for key in META if row.get(key) is not None}
            if row['collected_at'] != 'unknown':
                extra['collected_at'] = row['collected_at']
            if row['kind'] == 'show':
                shows = body.setdefault('shows', [])
                show = next((entry for entry in shows if entry['ids']['trakt'] == row['ids']['trakt']), None)
                if show is None:
                    show = {'ids': {'trakt': row['ids']['trakt']}, 'seasons': []}
                    shows.append(show)
                season = next((entry for entry in show['seasons'] if entry['number'] == row['season']), None)
                if season is None:
                    season = {'number': row['season'], 'episodes': []}
                    show['seasons'].append(season)
                season['episodes'].append({'number': row['episode'], **extra})
                continue
            else:
                item.update(extra)
        body.setdefault(PLURAL[row['kind']], []).append(item)
    return body


def checked_write(client, method, path, body, journal):
    journal({'phase': 'request', 'method': method, 'path': path})
    response, _ = client.request(method, path, body)
    # Some endpoints report partial failures with HTTP 200.
    if isinstance(response, dict):
        missing = response.get('not_found', {})
        if (isinstance(missing, dict) and any(missing.values())) or response.get('errors'):
            raise ValueError('Trakt konnte einzelne Einträge nicht übernehmen. Auftrag ist teilweise ausgeführt; zuerst neu vergleichen.')
    journal({'phase': 'confirmed', 'method': method, 'path': path})
    return response


def chunks(rows):
    for offset in range(0, len(rows), 100):
        yield rows[offset:offset + 100]


def reorder(client, path, source, current, journal):
    wanted = [row['key'] for row in source]
    mapping = {row['key']: row.get('item_id') for row in current}
    order = [mapping[key] for key in wanted if key in mapping]
    order.extend(row.get('item_id') for row in current if row['key'] not in set(wanted))
    if any(type(value) is not int for value in order):
        raise ValueError('Trakt lieferte keine gültigen IDs für die Reihenfolge.')
    if order and order != [row.get('item_id') for row in current]:
        checked_write(client, 'POST', path, {'rank': order}, journal)


def apply_plan(client, plan, source, journal):
    # History precedes watchlist restoration because Trakt auto-removes watched items.
    for category in ('history', 'ratings', 'collection', 'favorites', 'hidden', 'lists', 'watchlist'):
        if category not in plan['categories']:
            continue
        client.progress('Stelle ' + CATEGORIES[category] + ' wieder her …')
        change = plan['changes'][category]
        if category == 'lists':
            for row in change['remove_lists']:
                checked_write(client, 'DELETE', '/users/me/lists/' + str(row['id']), None, journal)
            for item in change['lists']:
                original = item['source']
                metadata = {key: original[key] for key in ('name', 'description', 'privacy')}
                target_id = item['target_id']
                if target_id is None:
                    created = checked_write(client, 'POST', '/users/me/lists', metadata, journal)
                    target_id = number(created['ids']['trakt'], 1, 2**63 - 1)
                elif item['update_metadata']:
                    checked_write(client, 'PUT', '/users/me/lists/' + str(target_id), metadata, journal)
                base = '/users/me/lists/' + str(target_id) + '/items'
                for rows in chunks(item['remove']):
                    checked_write(client, 'POST', base + '/remove', payload(rows, 'list-items'), journal)
                for rows in chunks(item['add']):
                    checked_write(client, 'POST', base, payload(rows, 'list-items'), journal)
                if plan['mode'] != 'merge' or item['target_id'] is None:
                    current = []
                    for row in client.pages(base):
                        current.append(record('list-items', {**media(row['type'], row[row['type']]), 'item_id': row.get('id'), 'notes': row.get('notes')}))
                    reorder(client, base + '/reorder', original['items'], current, journal)
            continue
        if category == 'hidden':
            for section in SECTIONS:
                for action in ('remove', 'add'):
                    for rows in chunks([row for row in change[action] if row['section'] == section]):
                        checked_write(client, 'POST', '/users/hidden/' + section + ('/remove' if action == 'remove' else ''), payload(rows, 'hidden'), journal)
            continue
        for action in ('remove', 'add'):
            for rows in chunks(change[action]):
                body = payload(rows, 'history-remove' if category == 'history' and action == 'remove' else category)
                checked_write(client, 'POST', '/sync/' + category + ('/remove' if action == 'remove' else ''), body, journal)
        if category in ('watchlist', 'favorites') and plan['mode'] != 'merge':
            current = client.capture([category])[category]
            reorder(client, '/sync/' + category + '/reorder', source[category], current, journal)
