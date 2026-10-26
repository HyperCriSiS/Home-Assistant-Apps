"""Versioned ZIP archives, independent schedules and grandfather/father/son retention."""
from calendar import monthrange
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import uuid
import zipfile
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from storage import read, write

UTC = timezone.utc
CATEGORIES = {
    'history': 'Wiedergabeverlauf', 'ratings': 'Bewertungen', 'watchlist': 'Watchlist',
    'favorites': 'Trakt-Favoriten', 'collection': 'Trakt-Sammlung', 'lists': 'Eigene Listen',
    'hidden': 'Ausgeblendete Medien', 'playback': 'Abspielfortschritt (nur Archiv)',
}
RESTORABLE = set(CATEGORIES) - {'playback'}
MAX_ZIP = 128 * 1024 * 1024
MAX_DATA = 512 * 1024 * 1024
DEFAULTS = {
    'enabled': False, 'before_sync': False, 'before_sync_minutes': 1440,
    'categories': list(CATEGORIES), 'schedules': [], 'timezone': 'UTC',
    'retention': {'latest': 10, 'daily': 14, 'weekly': 8, 'monthly': 12, 'yearly': 3,
                  'max_age_days': 0, 'keep_manual': True},
    'max_total_mb': 2048, 'min_free_mb': 256, 'retry_count': 3, 'retry_minutes': 15,
    'job_timeout_minutes': 120,
}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def selection(value, *, restore=False):
    allowed = RESTORABLE if restore else set(CATEGORIES)
    if (not isinstance(value, list) or not value
            or any(not isinstance(key, str) or key not in allowed for key in value)
            or len(value) != len(set(value))):
        raise ValueError('Bitte gültige Sicherungsbereiche auswählen.')
    return sorted(value)


def number(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'Zahl außerhalb des Bereichs {low}–{high}.')
    return value


def zone(name):
    if not isinstance(name, str) or len(name) > 100:
        raise ValueError('Ungültige Zeitzone.')
    try:
        return UTC if name == 'UTC' else ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError('Unbekannte IANA-Zeitzone, zum Beispiel Europe/Berlin.') from None


def normalize_settings(raw):
    if not isinstance(raw, dict) or set(raw) - set(DEFAULTS):
        raise ValueError('Ungültige Sicherungseinstellungen.')
    result = {**deepcopy(DEFAULTS), **deepcopy(raw)}
    for key in ('enabled', 'before_sync'):
        if type(result[key]) is not bool:
            raise ValueError('Ungültiger Schalter.')
    result['categories'] = selection(result['categories'])
    zone(result['timezone'])
    for key, low, high in (('before_sync_minutes', 0, 43200), ('max_total_mb', 128, 1048576),
                           ('min_free_mb', 0, 1048576), ('retry_count', 0, 5),
                           ('retry_minutes', 1, 1440), ('job_timeout_minutes', 5, 360)):
        number(result[key], low, high)
    retention = result['retention']
    if not isinstance(retention, dict) or set(retention) != set(DEFAULTS['retention']):
        raise ValueError('Ungültige Aufbewahrung.')
    for key in ('latest', 'daily', 'weekly', 'monthly', 'yearly', 'max_age_days'):
        number(retention[key], 1 if key == 'latest' else 0, 36500)
    if type(retention['keep_manual']) is not bool:
        raise ValueError('Ungültige Aufbewahrung manueller Sicherungen.')
    schedules = result['schedules']
    if not isinstance(schedules, list) or len(schedules) > 12:
        raise ValueError('Maximal 12 Zeitpläne sind möglich.')
    seen = set()
    for item in schedules:
        if not isinstance(item, dict) or set(item) != {'id', 'name', 'enabled', 'frequency', 'time', 'weekdays', 'month_day', 'interval_hours', 'categories'}:
            raise ValueError('Ungültiger Zeitplan.')
        if not isinstance(item['id'], str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', item['id']) or item['id'] in seen:
            raise ValueError('Zeitpläne benötigen eindeutige IDs.')
        seen.add(item['id'])
        if not isinstance(item['name'], str) or not item['name'].strip() or len(item['name']) > 100:
            raise ValueError('Zeitplan benötigt einen Namen.')
        if type(item['enabled']) is not bool or item['frequency'] not in ('daily', 'weekly', 'monthly', 'interval'):
            raise ValueError('Ungültiger Zeitplanmodus.')
        if not isinstance(item['time'], str) or not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]', item['time']):
            raise ValueError('Zeit als HH:MM angeben.')
        if not isinstance(item['weekdays'], list) or not item['weekdays']:
            raise ValueError('Wochentage auswählen.')
        for day in item['weekdays']:
            number(day, 0, 6)
        if len(set(item['weekdays'])) != len(item['weekdays']):
            raise ValueError('Wochentage dürfen nicht doppelt vorkommen.')
        item['weekdays'].sort()
        number(item['month_day'], 1, 31)
        number(item['interval_hours'], 1, 8760)
        item['categories'] = selection(item['categories'])
    return result


def next_run(schedule, after, timezone_name):
    """Calendar wall times; one occurrence per day, gap times advance through DST."""
    if schedule['frequency'] == 'interval':
        return after + schedule['interval_hours'] * 3600
    tz = zone(timezone_name)
    now = datetime.fromtimestamp(after, tz)
    hour, minute = map(int, schedule['time'].split(':'))
    for offset in range(370):
        day = now.date() + timedelta(days=offset)
        if schedule['frequency'] == 'weekly' and day.weekday() not in schedule['weekdays']:
            continue
        if schedule['frequency'] == 'monthly' and day.day != min(schedule['month_day'], monthrange(day.year, day.month)[1]):
            continue
        candidate = datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz, fold=0).timestamp()
        if candidate > after:
            return candidate
    raise ValueError('Kein nächster Ausführungstermin gefunden.')


def retained(entries, settings, now):
    """Protect each account/category set independently. Never thin a different scope away."""
    keep = {entry['id'] for entry in entries if entry.get('pinned')
            or (settings['retention']['keep_manual'] and entry['reason'] in ('manual', 'import'))}
    groups = {}
    for entry in entries:
        if not entry.get('valid', True):
            continue
        key = (entry['account']['id'], tuple(sorted(entry['categories'])))
        groups.setdefault(key, []).append(entry)
    retention = settings['retention']
    tz = zone(settings['timezone'])
    for group in groups.values():
        group.sort(key=lambda entry: entry['created_at'], reverse=True)
        keep.update(entry['id'] for entry in group[:retention['latest']])
        pools = {key: {} for key in ('daily', 'weekly', 'monthly', 'yearly')}
        for entry in group:
            if retention['max_age_days'] and entry['created_at'] < now - retention['max_age_days'] * 86400:
                continue
            stamp = datetime.fromtimestamp(entry['created_at'], tz)
            keys = {'daily': stamp.date().isoformat(), 'weekly': stamp.isocalendar()[:2],
                    'monthly': (stamp.year, stamp.month), 'yearly': stamp.year}
            for kind, period in keys.items():
                pools[kind].setdefault(period, entry['id'])
        for kind, pool in pools.items():
            keep.update(list(pool.values())[:retention[kind]])
    return keep


def unique_json(raw):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError('Doppelte JSON-Schlüssel im Archiv.')
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Ungültige JSON-Zahl.')))
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise ValueError('Ungültiges JSON im Archiv.') from None


class ArchiveStore:
    def __init__(self, directory):
        self.root = Path(directory) / 'backups'
        self.root.mkdir(parents=True, exist_ok=True)
        # Only our abandoned mkstemp outputs; never remove published ZIPs here.
        for path in self.root.glob('tmp*.partial'):
            if re.fullmatch(r'tmp[a-z0-9_]{8}\.partial', path.name) and path.is_file() and not path.is_symlink():
                path.unlink()

    def path(self, identifier):
        if not isinstance(identifier, str) or not re.fullmatch(r'[0-9a-f]{32}', identifier):
            raise ValueError('Ungültige Sicherungs-ID.')
        path = self.root / (identifier + '.zip')
        if path.is_symlink():
            raise ValueError('Ungültiger Archivpfad.')
        return path

    def inspect(self, source, *, full=True):
        if isinstance(source, (bytes, bytearray)):
            if len(source) > MAX_ZIP:
                raise ValueError('Archiv überschreitet 128 MiB.')
            source = io.BytesIO(source)
        elif Path(source).stat().st_size > MAX_ZIP:
            raise ValueError('Archiv überschreitet 128 MiB.')
        try:
            with zipfile.ZipFile(source) as archive:
                infos = archive.infolist()
                names = [item.filename for item in infos]
                allowed = {'manifest.json'} | {'data/' + key + '.json' for key in CATEGORIES}
                if (len(names) != len(set(names)) or not set(names) <= allowed or 'manifest.json' not in names
                        or sum(item.file_size for item in infos) > MAX_DATA
                        or any(item.flag_bits & 1 or item.is_dir() or item.file_size > MAX_DATA for item in infos)):
                    raise ValueError('Ungültige oder zu große Archivstruktur.')
                manifest_info = archive.getinfo('manifest.json')
                if manifest_info.file_size > 65536:
                    raise ValueError('Manifest ist zu groß.')
                manifest = unique_json(archive.read('manifest.json'))
                required = {'format', 'version', 'id', 'created_at', 'reason', 'account', 'categories', 'checksums', 'counts'}
                if (not isinstance(manifest, dict) or set(manifest) != required or manifest['format'] != 'pts-trakt-backup'
                        or type(manifest['version']) is not int or manifest['version'] != 1):
                    raise ValueError('Nicht unterstütztes Sicherungsformat. Nur App-Archive werden importiert.')
                self.path(manifest['id'])
                categories = selection(manifest['categories'])
                if set(names) != {'manifest.json'} | {'data/' + key + '.json' for key in categories}:
                    raise ValueError('Archiv enthält fehlende oder unerwartete Dateien.')
                account = manifest['account']
                if (not isinstance(account, dict) or set(account) != {'id', 'username'}
                        or not isinstance(account['id'], str) or not account['id'] or len(account['id']) > 128
                        or not isinstance(account['username'], str) or len(account['username']) > 128):
                    raise ValueError('Ungültige Kontoidentität im Archiv.')
                if type(manifest['created_at']) not in (int, float) or not 0 < manifest['created_at'] < 4102444800:
                    raise ValueError('Ungültiges Sicherungsdatum.')
                if manifest['reason'] not in ('manual', 'schedule', 'pre-sync', 'pre-restore', 'import'):
                    raise ValueError('Ungültiger Sicherungstyp.')
                if (not isinstance(manifest['checksums'], dict) or set(manifest['checksums']) != set(categories)
                        or not isinstance(manifest['counts'], dict) or set(manifest['counts']) != set(categories)):
                    raise ValueError('Ungültiges Inhaltsverzeichnis.')
                data = {}
                for key in categories:
                    if not isinstance(manifest['checksums'][key], str) or not re.fullmatch('[0-9a-f]{64}', manifest['checksums'][key]):
                        raise ValueError('Ungültige Prüfsumme.')
                    number(manifest['counts'][key], 0, 10000000)
                    if full:
                        payload = archive.read('data/' + key + '.json')
                        if hashlib.sha256(payload).hexdigest() != manifest['checksums'][key]:
                            raise ValueError('Prüfsumme stimmt nicht. Archiv beschädigt.')
                        data[key] = unique_json(payload)
                return manifest, data
        except (zipfile.BadZipFile, KeyError, TypeError, RuntimeError, OverflowError):
            raise ValueError('Archiv ist beschädigt oder unvollständig.') from None

    def entries(self):
        entries = []
        for path in self.root.glob('*.zip'):
            if path.is_symlink():
                continue
            try:
                manifest, _ = self.inspect(path, full=False)
                if path != self.path(manifest['id']):
                    continue
                manifest['bytes'] = path.stat().st_size
                metadata = read(path.with_suffix('.meta.json'), {})
                if not isinstance(metadata, dict):
                    raise ValueError('Ungültige Archivmetadaten.')
                manifest['pinned'] = bool(metadata.get('pinned'))
                manifest['valid'] = True
                entries.append(manifest)
            except (ValueError, OSError):
                # Corrupt files stay on disk; never silently prune unreadable evidence.
                if re.fullmatch('[0-9a-f]{32}', path.stem):
                    entries.append({'id': path.stem, 'valid': False, 'pinned': True, 'created_at': path.stat().st_mtime,
                        'bytes': path.stat().st_size, 'reason': 'damaged', 'account': {'id': '', 'username': ''},
                        'categories': [], 'counts': {}})
        return sorted(entries, key=lambda entry: entry['created_at'], reverse=True)

    def save(self, account, data, reason, now, settings, *, pinned=False):
        if shutil.disk_usage(self.root).free < settings['min_free_mb'] * 1024 * 1024:
            raise ValueError('Zu wenig freier Speicher für eine neue Sicherung.')
        identifier = uuid.uuid4().hex
        payloads = {key: json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode() for key, value in data.items()}
        if sum(map(len, payloads.values())) > MAX_DATA:
            raise ValueError('Sicherungsdaten überschreiten 512 MiB.')
        manifest = {'format': 'pts-trakt-backup', 'version': 1, 'id': identifier, 'created_at': now,
                    'reason': reason, 'account': account, 'categories': selection(list(data)),
                    'checksums': {key: hashlib.sha256(value).hexdigest() for key, value in payloads.items()},
                    'counts': {key: len(value) for key, value in data.items()}}
        fd, temporary = tempfile.mkstemp(dir=self.root, suffix='.partial')
        try:
            os.chmod(temporary, 0o600)
            with os.fdopen(fd, 'wb') as stream:
                with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                    archive.writestr('manifest.json', json.dumps(manifest))
                    for key, value in payloads.items():
                        archive.writestr('data/' + key + '.json', value)
                stream.flush()
                os.fsync(stream.fileno())
            if Path(temporary).stat().st_size > MAX_ZIP:
                raise ValueError('Komprimiertes Archiv überschreitet 128 MiB.')
            self.inspect(temporary)
            if pinned:
                write(self.path(identifier).with_suffix('.meta.json'), {'pinned': True})
            os.replace(temporary, self.path(identifier))
            return manifest
        finally:
            Path(temporary).unlink(missing_ok=True)

    def import_archive(self, payload, settings, now):
        manifest, data = self.inspect(payload)
        # Validate semantic data too, before publishing the uploaded archive.
        from trakt_backup import normalize_capture
        normalized = normalize_capture(data)
        return self.save(manifest['account'], normalized, 'import', now, settings, pinned=True)

    def delete(self, identifier):
        path = self.path(identifier)
        path.unlink()
        path.with_suffix('.meta.json').unlink(missing_ok=True)

    def pin(self, identifier, value):
        if type(value) is not bool or not self.path(identifier).exists():
            raise ValueError('Ungültiger Archivschutz.')
        write(self.path(identifier).with_suffix('.meta.json'), {'pinned': value})

    def prune(self, settings, now):
        entries = self.entries()
        keep = retained(entries, settings, now)
        removed = []
        for entry in entries:
            if entry['id'] not in keep:
                self.delete(entry['id'])
                removed.append(entry['id'])
        return removed
