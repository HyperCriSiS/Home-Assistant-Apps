"""Backup/restore behavior with disposable in-memory Trakt fixtures only."""
from copy import deepcopy
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch
import zipfile
from zoneinfo import ZoneInfoNotFoundError

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
from backup_store import ArchiveStore, CATEGORIES, DEFAULTS, digest, next_run, normalize_settings, retained, zone
from server import Controller
from storage import read, write
from trakt_backup import (TraktClient, apply_plan, build_plan, differences, media, normalize_capture,
                          payload, record, timestamp)


def stamp(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()


def movie(identifier=1, **extra):
    return {'kind': 'movie', 'ids': {'trakt': identifier}, 'title': 'Film ' + str(identifier), **extra}


def fixture():
    return normalize_capture({
        'history': [movie(watched_at='2024-01-01T12:00:00Z', event_id=1), movie(watched_at='2024-02-01T12:00:00Z', event_id=2)],
        'ratings': [movie(rating=8, rated_at='2024-01-01T12:00:00Z')],
        'watchlist': [movie(3, notes='watch note', rank=1, item_id=33)],
        'favorites': [movie(4, notes='favorite note', rank=1, item_id=44)],
        'collection': [movie(5, collected_at='2023-01-01T00:00:00Z', media_type='digital', resolution='hd_1080p'),
                       {'kind': 'show', 'ids': {'trakt': 8}, 'title': 'Serie', 'season': 1, 'episode': 2,
                        'collected_at': '2023-02-01T00:00:00Z', 'audio': 'aac'}],
        'lists': [{'id': 10, 'name': 'Private List', 'description': 'Fixture', 'privacy': 'private',
                   'items': [movie(6, notes='list note', item_id=66)]}],
        'hidden': [{'kind': 'show', 'ids': {'trakt': 7}, 'title': 'Hidden', 'section': 'progress_watched'}],
        'playback': [movie(8, progress=34.5, paused_at='2024-01-01T00:00:00Z')],
    })


class MemoryTrakt:
    def __init__(self, data=None):
        self.data = deepcopy(data if data is not None else {key: [] for key in CATEGORIES})
        self.owner = {'id': 'fixture-account', 'username': 'Fixture'}
        self.calls = []
        self.progress = lambda _: None
        self.counter = 1000

    def snapshot(self, categories):
        return deepcopy(self.owner), deepcopy({key: self.data[key] for key in categories})

    def pages(self, path):
        identifier = int(path.split('/')[4])
        target = next(item for item in self.data['lists'] if item['id'] == identifier)
        return [{'id': item['item_id'], 'type': item['kind'], item['kind']: {'ids': item['ids'], 'title': item['title']},
                 'notes': item.get('notes')} for item in target['items']]

    def capture(self, categories):
        return deepcopy({key: self.data[key] for key in categories})

    def request(self, method, path, body=None, params=None):
        self.calls.append((method, path, deepcopy(body)))
        if path.startswith('/users/me/lists'):
            if path == '/users/me/lists':
                self.counter += 1
                self.data['lists'].append({'id': self.counter, 'key': 'list:' + str(self.counter), **body, 'items': []})
                return {'ids': {'trakt': self.counter}}, {}
            identifier = int(path.split('/')[4])
            target = next(item for item in self.data['lists'] if item['id'] == identifier)
            if path.endswith('/items/reorder'):
                order = body['rank']
                target['items'].sort(key=lambda row: order.index(row['item_id']))
                return {}, {}
            if '/items' not in path:
                if method == 'DELETE':
                    self.data['lists'].remove(target)
                else:
                    target.update(body)
                return {}, {}
            category, rows = 'list-items', target['items']
        elif path.startswith('/users/hidden/'):
            category, rows = 'hidden', self.data['hidden']
        else:
            category = path.split('/')[2]
            rows = self.data[category]
            if path.endswith('/reorder'):
                rows.sort(key=lambda row: body['rank'].index(row['item_id']))
                return {}, {}
        if category == 'history' and path.endswith('/remove'):
            self.data[category] = [row for row in rows if row['event_id'] not in body['ids']]
            return {}, {}
        incoming = []
        singular = {'movies': 'movie', 'shows': 'show', 'seasons': 'season', 'episodes': 'episode', 'people': 'person'}
        for plural, objects in body.items():
            for obj in objects:
                kind = singular[plural]
                row = {'kind': kind, 'ids': obj['ids'], 'title': 'Film ' + str(obj['ids']['trakt']), **obj}
                if category == 'collection' and kind == 'show':
                    for season in obj['seasons']:
                        for episode in season['episodes']:
                            incoming.append(record(category, {**row, 'season': season['number'], 'episode': episode['number'], **episode}))
                else:
                    if category == 'hidden':
                        row['section'] = path.split('/')[3]
                    incoming.append(record(category, row))
        if path.endswith('/remove'):
            keys = {row['key'] for row in incoming}
            rows[:] = [row for row in rows if row['key'] not in keys]
        else:
            for row in incoming:
                existing = next((item for item in rows if item['key'] == row['key']), None)
                if category == 'history' or existing is None:
                    self.counter += 1
                    if category == 'history':
                        row['event_id'] = self.counter
                    elif category in ('watchlist', 'favorites', 'list-items'):
                        row['item_id'] = self.counter
                    rows.append(row)
                elif category == 'ratings':
                    existing.update(row)
        return {}, {}


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.store = ArchiveStore(self.directory)
        self.settings = normalize_settings({})
        self.account = {'id': 'fixture-account', 'username': 'Fixture'}

    def tearDown(self):
        self.temp.cleanup()

    def save(self, data=None, reason='manual', pinned=False):
        return self.store.save(self.account, data or fixture(), reason, time.time(), self.settings, pinned=pinned)

    def test_full_archive_checksums_round_trip_and_no_credentials(self):
        manifest = self.save(pinned=True)
        actual, data = self.store.inspect(self.store.path(manifest['id']))
        self.assertEqual(data, fixture())
        self.assertEqual(actual, manifest)
        self.assertTrue(self.store.entries()[0]['pinned'])
        with zipfile.ZipFile(self.store.path(manifest['id'])) as archive:
            self.assertEqual(set(archive.namelist()), {'manifest.json'} | {'data/' + key + '.json' for key in CATEGORIES})
            self.assertNotIn('OAUTH_TOKEN', archive.read('manifest.json').decode())

    def test_single_category_import_is_validated_and_pinned(self):
        entry = self.save({'history': fixture()['history']})
        result = self.store.import_archive(self.store.path(entry['id']).read_bytes(), self.settings, time.time())
        self.assertNotEqual(result['id'], entry['id'])
        self.assertEqual(result['categories'], ['history'])
        self.assertTrue(self.store.entries()[0]['pinned'])

    def rewrite(self, entry, replace):
        with zipfile.ZipFile(self.store.path(entry['id'])) as source:
            contents = {name: source.read(name) for name in source.namelist()}
        replace(contents)
        raw = io.BytesIO()
        with zipfile.ZipFile(raw, 'w') as target:
            for name, value in contents.items():
                target.writestr(name, value)
        return raw.getvalue()

    def test_zip_slip_unknown_members_corrupt_json_and_checksums_rejected(self):
        entry = self.save()
        for change in (lambda values: values.update({'../credentials.json': b'{}'}),
                       lambda values: values.update({'data/history.json': b'[]'}),
                       lambda values: values.update({'manifest.json': b'{"version":1,"version":2}'}),
                       lambda values: values.update({'manifest.json': b'{}'})):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.store.inspect(self.rewrite(entry, change))
        self.assertFalse((self.directory / 'credentials.json').exists())

    def test_incomplete_and_future_archives_rejected(self):
        entry = self.save()
        with self.assertRaises(ValueError):
            self.store.inspect(b'not-a-zip')
        def future(values):
            manifest = json.loads(values['manifest.json']); manifest['version'] = 999
            values['manifest.json'] = json.dumps(manifest).encode()
        with self.assertRaises(ValueError):
            self.store.inspect(self.rewrite(entry, future))

    def test_path_traversal_and_arbitrary_file_deletion_refused(self):
        for identifier in ('../credentials', '/data/options', 'a' * 33, 'A' * 32, None):
            with self.subTest(identifier=identifier), self.assertRaises(ValueError):
                self.store.path(identifier)

    def test_failed_write_does_not_publish_partial_archive(self):
        with patch('backup_store.os.replace', side_effect=OSError('fixture full')):
            with self.assertRaises(OSError):
                self.save()
        self.assertEqual(list(self.store.root.glob('*.zip')), [])
        self.assertEqual(list(self.store.root.glob('*.partial')), [])

    def test_low_disk_space_refuses_creation(self):
        with patch('backup_store.shutil.disk_usage', return_value=Mock(free=0)), self.assertRaises(ValueError):
            self.save()
        self.assertEqual(self.store.entries(), [])

    def test_corrupt_archive_stays_visible_and_is_not_pruned(self):
        entry = self.save(reason='schedule')
        self.store.path(entry['id']).write_bytes(b'broken')
        self.assertFalse(self.store.entries()[0]['valid'])
        self.assertEqual(self.store.prune(self.settings, time.time()), [])
        self.assertTrue(self.store.path(entry['id']).exists())

    def test_prune_deletes_only_expired_unprotected_archives(self):
        self.settings['retention'].update(latest=1,daily=0,weekly=0,monthly=0,yearly=0,keep_manual=False)
        older=self.store.save(self.account,{'ratings':[]},'schedule',time.time()-100,self.settings)
        pinned=self.store.save(self.account,{'ratings':[]},'schedule',time.time()-200,self.settings,pinned=True)
        newest=self.store.save(self.account,{'ratings':[]},'schedule',time.time(),self.settings)
        self.assertEqual(self.store.prune(self.settings,time.time()),[older['id']])
        self.assertTrue(self.store.path(pinned['id']).exists())
        self.assertTrue(self.store.path(newest['id']).exists())


class ScheduleRetentionTests(unittest.TestCase):
    def schedule(self, **changes):
        return {'id': 'daily', 'name': 'Fixture', 'enabled': True, 'frequency': 'daily', 'time': '03:00',
                'weekdays': [0], 'month_day': 31, 'interval_hours': 4, 'categories': ['history'], **changes}

    def test_daily_weekly_month_end_and_interval(self):
        start = stamp('2026-02-01T12:00:00Z')
        self.assertEqual(next_run(self.schedule(), start, 'UTC'), stamp('2026-02-02T03:00:00Z'))
        self.assertEqual(next_run(self.schedule(frequency='weekly'), start, 'UTC'), stamp('2026-02-02T03:00:00Z'))
        self.assertEqual(next_run(self.schedule(frequency='monthly'), start, 'UTC'), stamp('2026-02-28T03:00:00Z'))
        self.assertEqual(next_run(self.schedule(frequency='interval'), start, 'UTC'), start + 4 * 3600)

    def test_dst_gap_and_repeated_hour_run_once(self):
        try:
            zone('Europe/Berlin')
        except ValueError:
            if sys.platform != 'win32':
                raise
            self.skipTest('Windows fixture runtime has no IANA data; mandatory Linux CI provides tzdata')
        schedule = self.schedule(time='02:30')
        spring = next_run(schedule, stamp('2026-03-28T23:00:00Z'), 'Europe/Berlin')
        self.assertEqual(spring, stamp('2026-03-29T01:30:00Z'))
        autumn = next_run(schedule, stamp('2026-10-24T23:00:00Z'), 'Europe/Berlin')
        self.assertEqual(autumn, stamp('2026-10-25T00:30:00Z'))
        self.assertEqual(next_run(schedule, autumn, 'Europe/Berlin'), stamp('2026-10-26T01:30:00Z'))

    def test_invalid_settings_rejected(self):
        for changes in ({'enabled': 1}, {'timezone': '../bad'}, {'categories': ['credentials']},
                        {'schedules': [self.schedule(time='29:00')]}, {'schedules': [self.schedule(), self.schedule()]},
                        {'schedules': [self.schedule(weekdays=[7])]}, {'max_total_mb': -1}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                normalize_settings(changes)

    def entry(self, identifier, at, **changes):
        return {'id': identifier, 'created_at': at, 'account': {'id': 'A'}, 'categories': ['history'],
                'reason': 'schedule', 'pinned': False, **changes}

    def test_retention_union_pins_manual_age_and_scope_isolation(self):
        settings = normalize_settings({})
        settings['retention'].update(latest=1, daily=2, weekly=0, monthly=0, yearly=0, max_age_days=10)
        now = stamp('2026-10-26T12:00:00Z')
        entries = [self.entry('new', now), self.entry('same-day', now - 60), self.entry('yesterday', now - 86400),
                   self.entry('old', now - 30 * 86400), self.entry('pin', now - 40 * 86400, pinned=True),
                   self.entry('manual', now - 40 * 86400, reason='manual'),
                   self.entry('scope', now - 50 * 86400, categories=['ratings']),
                   self.entry('account', now - 60 * 86400, account={'id': 'B'})]
        self.assertEqual(retained(entries, settings, now), {'new', 'yesterday', 'pin', 'manual', 'scope', 'account'})

    def test_grandfather_month_and_year_representatives(self):
        settings = normalize_settings({})
        settings['retention'].update(latest=1, daily=0, weekly=0, monthly=2, yearly=2, keep_manual=False)
        entries = [self.entry('oct', stamp('2026-10-01T00:00:00Z')), self.entry('sep', stamp('2026-09-01T00:00:00Z')),
                   self.entry('aug', stamp('2026-08-01T00:00:00Z')), self.entry('2025', stamp('2025-01-01T00:00:00Z'))]
        self.assertEqual(retained(entries, settings, time.time()), {'oct', 'sep', '2025'})


class RestorePlanTests(unittest.TestCase):
    def test_merge_preserves_rating_conflicts_and_history_multiplicity(self):
        source = fixture()
        current = fixture()
        current['history'] = current['history'][:1]
        current['ratings'][0]['rating'] = 4
        plan = build_plan(source, current, ['history', 'ratings'], 'merge')
        self.assertEqual(plan['counts']['history']['add'], 1)
        self.assertEqual(plan['counts']['ratings']['add'], 0)
        self.assertFalse(plan['destructive'])

    def test_identical_timestamp_rewatches_are_multisets(self):
        rows = fixture()['history'][:1]
        change = differences('history', rows * 2, rows, 'merge')
        self.assertEqual(len(change['add']), 1)
        extra = differences('history', rows, [{**rows[0], 'event_id': 1}, {**rows[0], 'event_id': 2}], 'mirror')
        self.assertEqual(extra['remove'][0]['event_id'], 2)

    def test_changed_catalogue_metadata_does_not_trigger_restore_writes(self):
        source,current=fixture(),fixture()
        source['ratings'][0]['ids']['imdb']='tt123'
        current['ratings'][0]['ids']['imdb']='tt456'
        current['ratings'][0]['title']='Renamed catalogue title'
        plan=build_plan(source,current,['ratings'],'overwrite')
        self.assertEqual(plan['counts']['ratings']['add'],0)
        self.assertEqual(payload(source['ratings'],'ratings')['movies'][0]['ids'],{'trakt':1})

    def test_utc_equivalent_timestamps_do_not_duplicate(self):
        self.assertEqual(timestamp('2024-01-01T14:00:00+02:00'), timestamp('2024-01-01T12:00:00Z'))
        for value in ('2024-01-01', '../bad', ''):
            with self.assertRaises(ValueError):
                timestamp(value)

    def test_mirror_deletes_only_selected_scope(self):
        source, current = fixture(), fixture()
        current['ratings'].append(record('ratings', movie(99, rating=1)))
        current['history'].append(record('history', movie(100, watched_at='2024-01-01T00:00:00Z', event_id=90)))
        plan = build_plan(source, current, ['ratings'], 'mirror')
        self.assertTrue(plan['destructive'])
        self.assertEqual(set(plan['changes']), {'ratings'})
        self.assertEqual(plan['counts']['ratings']['remove'], 1)

    def test_collection_episode_payload_never_collects_an_entire_show(self):
        row = fixture()['collection'][1]
        body = payload([row, {**row, 'episode': 3}], 'collection')
        self.assertEqual(body['shows'][0]['seasons'][0]['episodes'][0]['number'], 2)
        self.assertEqual(body['shows'][0]['seasons'][0]['number'], 1)
        self.assertEqual(len(body['shows']), 1)
        self.assertEqual(len(body['shows'][0]['seasons'][0]['episodes']), 2)

    def test_full_restore_and_second_merge_are_idempotent(self):
        source = fixture()
        client = MemoryTrakt()
        categories = list(set(CATEGORIES) - {'playback'})
        plan = build_plan(source, client.snapshot(categories)[1], categories, 'mirror')
        apply_plan(client, plan, source, lambda event: None)
        after = build_plan(source, client.snapshot(categories)[1], categories, 'merge')
        self.assertTrue(all(row['add'] == 0 and row['remove'] == 0 for row in after['counts'].values()))
        self.assertEqual(len(client.data['history']), 2)
        self.assertEqual(client.data['lists'][0]['items'][0]['notes'], 'list note')

    def test_existing_list_metadata_contents_and_order_restore(self):
        source = fixture(); current = fixture()
        source['lists'][0]['items'].append(record('list-items', movie(9, notes='second', item_id=90)))
        source['lists'][0]['items'].reverse()
        current['lists'][0]['description'] = 'old'
        client = MemoryTrakt(current)
        plan = build_plan(source, current, ['lists'], 'overwrite')
        apply_plan(client, plan, source, lambda event: None)
        self.assertEqual(client.data['lists'][0]['description'], 'Fixture')
        self.assertEqual([row['ids']['trakt'] for row in client.data['lists'][0]['items']], [9, 6])

    def test_unknown_playback_and_duplicate_records_rejected(self):
        for categories in (['playback'], ['tokens'], []):
            with self.assertRaises(ValueError):
                build_plan(fixture(), fixture(), categories, 'merge')
        invalid = fixture(); invalid['ratings'] *= 2
        with self.assertRaises(ValueError):
            normalize_capture(invalid)

    def test_partial_success_and_unsafe_endpoint_fail_closed(self):
        client = Mock()
        client.request.return_value = ({'not_found': {'movies': [1]}}, {})
        source = fixture()
        plan = build_plan(source, {key: [] for key in source}, ['history'], 'merge')
        with self.assertRaises(ValueError):
            apply_plan(client, plan, source, lambda event: None)


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.directory = Path(self.temp.name)
        write(self.directory / '.pytrakt.json', {'CLIENT_ID': 'fixture-client', 'OAUTH_TOKEN': 'fixture-private-token',
                                               'OAUTH_REFRESH': 'fixture-refresh', 'OAUTH_EXPIRES_AT': time.time() + 86400})
        self.client = TraktClient(self.directory)

    def tearDown(self):
        self.temp.cleanup()

    def response(self, data, status=200, headers=None):
        return Mock(status_code=status, headers=headers or {}, json=Mock(return_value=data))

    def test_pagination_reads_every_page_even_when_server_clamps_limit(self):
        with patch.object(self.client, 'request', side_effect=[([1], {'X-Pagination-Page-Count':'2'}), ([2], {'X-Pagination-Page-Count':'2'})]) as call:
            self.assertEqual(self.client.pages('/sync/history'), [1, 2])
            self.assertEqual(call.call_args_list[1].kwargs['params']['page'], 2)
            self.assertEqual(call.call_args_list[0].kwargs['params']['limit'], 250)

    def test_rate_limit_get_retries_but_ambiguous_writes_never_retry(self):
        with patch.object(self.client.session, 'request', side_effect=[self.response({},429,{'Retry-After':'4'}),self.response([])]), patch.object(self.client,'wait') as wait:
            self.assertEqual(self.client.get('/sync/history'), [])
            wait.assert_called_once_with(4)
        with patch.object(self.client.session,'request',side_effect=requests.Timeout('fixture-private-token')) as call, patch.object(self.client,'wait'):
            with self.assertRaises(ValueError) as error:
                self.client.request('POST','/sync/history',{})
            self.assertNotIn('fixture-private-token', str(error.exception))
            call.assert_called_once()

    def test_redirects_are_not_followed_and_only_trakt_routes_allowed(self):
        with patch.object(self.client.session,'request',return_value=self.response({},302)) as call:
            with self.assertRaises(ValueError):
                self.client.get('/sync/history')
            self.assertFalse(call.call_args.kwargs['allow_redirects'])
        for path in ('https://evil.invalid/steal','/sync/history/../../oauth/token','/scrobble/stop'):
            with self.assertRaises(ValueError):
                self.client.request('POST',path,{})

    def test_refresh_persists_rotated_token(self):
        self.client.token['OAUTH_EXPIRES_AT'] = 0
        response = self.response({'access_token':'rotated','refresh_token':'rotated-refresh','created_at':time.time(),'expires_in':86400})
        with patch.object(self.client.session,'post',return_value=response):
            self.client.refresh()
        self.assertEqual(read(self.directory / '.pytrakt.json')['OAUTH_TOKEN'],'rotated')

    def test_cancellation_and_deadline_stop_before_network(self):
        self.client.stop = threading.Event(); self.client.stop.set()
        with patch.object(self.client.session,'request') as call, self.assertRaises(ValueError):
            self.client.get('/sync/history')
        call.assert_not_called()
        self.client.stop.clear(); self.client.deadline = 0
        with self.assertRaises(ValueError):
            self.client.get('/sync/history')

    def test_changing_account_activity_never_publishes_inconsistent_snapshot(self):
        with patch.object(self.client,'get',side_effect=[{'all':1},{'all':2}]*3), patch.object(self.client,'account',return_value={}), patch.object(self.client,'capture',return_value={}):
            with self.assertRaises(ValueError):
                self.client.snapshot(['history'])

    def test_wire_capture_all_supported_categories(self):
        routes = {
            '/sync/history': [{'id':1,'type':'movie','movie':{'ids':{'trakt':1},'title':'Film'},'watched_at':'2024-01-01T00:00:00Z'}],
            '/sync/ratings/movies': [{'type':'movie','movie':{'ids':{'trakt':1}},'rating':7,'rated_at':'2024-01-01T00:00:00Z'}],
            '/sync/watchlist': [{'id':3,'rank':1,'type':'movie','movie':{'ids':{'trakt':2}},'notes':'Note'}],
            '/sync/favorites': [{'id':4,'rank':1,'type':'show','show':{'ids':{'trakt':3}},'notes':'Favorite'}],
            '/sync/collection/movies': [{'movie':{'ids':{'trakt':1}},'collected_at':'2024-01-01T00:00:00Z','metadata':{'media_type':'digital'}}],
            '/sync/collection/shows': [{'show':{'ids':{'trakt':5}},'seasons':[{'number':0,'episodes':[{'number':1,'collected_at':'2024-01-01T00:00:00Z','metadata':{'audio':'aac'}}]}]}],
            '/users/me/lists': [{'ids':{'trakt':12},'name':'List','privacy':'private','description':'Text'}],
            '/users/me/lists/12/items': [{'id':8,'type':'person','person':{'ids':{'trakt':9},'name':'Actor'},'notes':'Person note'}],
            '/users/hidden/progress_watched': [{'type':'show','show':{'ids':{'trakt':10}}}],
            '/sync/playback': [{'type':'movie','movie':{'ids':{'trakt':2}},'progress':25,'paused_at':'2024-01-01T00:00:00Z'}],
        }
        with patch.object(self.client,'pages',side_effect=lambda path,**kwargs:deepcopy(routes.get(path,[]))) as pages:
            result=self.client.capture(list(CATEGORIES))
        self.assertEqual(set(result),set(CATEGORIES))
        self.assertEqual(result['collection'][1]['season'],0)
        self.assertEqual(result['lists'][0]['items'][0]['kind'],'person')
        self.assertEqual(result['history'][0]['event_id'],1)
        self.assertEqual(result['ratings'][0]['rating'],7)
        self.assertEqual(result['watchlist'][0]['notes'],'Note')
        self.assertIn(unittest.mock.call('/users/me/lists/12/items',sort_by='rank',sort_how='asc'),pages.call_args_list)

    def test_incomplete_collection_and_repeated_pages_refused(self):
        with patch.object(self.client,'pages',side_effect=lambda path,**kw:[{'show':{'ids':{'trakt':5}}}] if path.endswith('/shows') else []):
            with self.assertRaises(ValueError):
                self.client.capture(['collection'])
        with patch.object(self.client,'request',return_value=([1]*250,{})) as request:
            with self.assertRaises(ValueError):
                self.client.pages('/sync/history')
            self.assertEqual(request.call_count,2)


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.directory = Path(self.temp.name)
        write(self.directory / 'options.json', {})
        self.owner = Controller(self.directory); self.service = self.owner.backups
        self.client = MemoryTrakt()
        self.source = fixture()
        self.archive = self.service.store.save(self.client.owner,self.source,'manual',time.time(),self.service.settings)

    def tearDown(self):
        self.owner.shutdown(); self.temp.cleanup()

    def run_job(self, action, data):
        with patch.object(self.service,'client',return_value=self.client):
            result = self.owner.action(action,data)
            self.service.thread.join(timeout=10)
            self.assertFalse(self.service.thread.is_alive())
        return deepcopy(self.service.state['job'])

    def preview(self, **extra):
        return self.run_job('backup-preview',{'id':self.archive['id'],'categories':['history'],'mode':'merge',**extra})

    def test_full_job_writes_rollback_before_restore_and_revokes_sync(self):
        self.assertEqual(self.preview()['status'],'completed')
        plan = self.service.public_plan()
        write(self.directory / 'analysis.json', {'fingerprint':self.owner.identity()})
        self.owner.action('approve',{})
        job = self.run_job('backup-restore',{'plan_id':plan['id'],'confirmation':plan['confirmation']})
        self.assertEqual(job['status'],'completed',job)
        self.assertTrue(job['result']['verified'])
        self.assertTrue(self.owner.state['paused'])
        self.assertFalse(self.owner.approved())
        self.assertTrue(self.service.store.path(job['safety_archive']).exists())
        self.assertEqual(read(self.directory / 'restore-journal.json')['requests'],1)
        self.assertEqual(self.service.store.entries()[0]['reason'],'pre-restore')
        self.assertTrue(self.service.store.entries()[0]['pinned'])

    def test_stale_account_data_preview_cannot_write(self):
        self.preview(); plan = self.service.public_plan()
        self.client.data['history'] = fixture()['history'][:1]
        job = self.run_job('backup-restore',{'plan_id':plan['id'],'confirmation':plan['confirmation']})
        self.assertEqual(job['status'],'failed')
        self.assertEqual(self.client.calls,[])

    def test_credentials_change_expiry_wrong_confirmation_and_cross_account_block(self):
        self.preview(); plan = self.service.public_plan()
        with self.assertRaises(ValueError):
            self.owner.action('backup-restore',{'plan_id':plan['id'],'confirmation':'wrong'})
        self.owner.options['ratings'] = True
        with self.assertRaises(ValueError):
            self.owner.action('backup-restore',{'plan_id':plan['id'],'confirmation':plan['confirmation']})
        self.client.owner['id'] = 'other'
        self.assertEqual(self.preview()['status'],'failed')
        self.assertIsNone(self.service.public_plan())
        self.assertEqual(self.preview(allow_other_account=True)['status'],'completed')

    def test_busy_job_rejects_backup_restore_settings_and_delete(self):
        self.owner.lock.acquire()
        try:
            for action,data in [('backup-create',{'categories':['history']}),('backup-delete',{'id':self.archive['id'],'confirmation':'LÖSCHEN'}),
                                ('backup-settings',{'settings':self.service.settings,'revision':digest(self.service.settings)})]:
                with self.subTest(action=action),self.assertRaises(ValueError):
                    self.owner.action(action,data)
        finally:
            self.owner.lock.release()

    def test_safety_archive_failure_blocks_every_remote_write(self):
        self.preview(); plan = self.service.public_plan()
        with patch.object(self.service.store,'save',side_effect=OSError('fixture full')):
            job=self.run_job('backup-restore',{'plan_id':plan['id'],'confirmation':plan['confirmation']})
        self.assertEqual(job['status'],'failed')
        self.assertEqual(self.client.calls,[])

    def test_pre_sync_backup_failure_blocks_worker_and_success_respects_minimum(self):
        self.service.settings['before_sync'] = True
        self.service.settings['categories'] = ['history']
        with patch.object(self.service,'client',return_value=self.client):
            self.service.before_sync()
            count = len(self.service.store.entries())
            self.service.before_sync()
            self.assertEqual(len(self.service.store.entries()),count)
        self.service.state.pop('pre_sync')
        write(self.directory / 'analysis.json',{'fingerprint':self.owner.identity()});self.owner.action('approve',{})
        with patch.object(self.service,'client',side_effect=ValueError('fixture backup failed')),patch('server.subprocess.Popen') as worker:
            self.assertFalse(self.owner.run('sync'))
            worker.assert_not_called()

    def test_schedule_catchup_retry_and_restart_persistence(self):
        schedule=ScheduleRetentionTests().schedule()
        settings={**self.service.settings,'enabled':True,'schedules':[schedule]}
        self.owner.action('backup-settings',{'settings':settings,'revision':digest(self.service.settings)})
        self.service.state['schedules']['daily']['next_run']=0
        with patch.object(self.service,'client',side_effect=ValueError('fixture temporarily unavailable')):
            self.assertTrue(self.service.tick());self.service.thread.join(timeout=10)
        saved=self.service.state['schedules']['daily']
        self.assertEqual(saved['attempts'],1)
        self.assertGreater(saved['next_run'],time.time())
        restarted=Controller(self.directory)
        self.assertEqual(restarted.backups.state['schedules']['daily'],saved)
        self.assertTrue(restarted.backups.settings['enabled'])
        restarted.shutdown()

    def test_verify_works_without_trakt_credentials(self):
        job=self.run_job('backup-verify',{'id':self.archive['id']})
        self.assertEqual(job['status'],'completed')
        self.assertTrue(job['result']['verified'])

    def test_interrupted_restore_requires_new_preview_and_does_not_resume(self):
        state={'version':1,'schedules':{},'job':{'id':'fixture','kind':'restore','status':'running'}}
        write(self.directory / 'backup-state.json',state)
        restarted=Controller(self.directory)
        self.assertEqual(restarted.backups.state['job']['status'],'interrupted')
        restarted.shutdown()

    def test_complete_mirror_restore_and_post_verification(self):
        self.client.data=fixture()
        self.client.data['ratings'][0]['rating']=3
        self.client.data['history'].append(record('history',movie(99,watched_at='2024-01-01T00:00:00Z',event_id=90)))
        self.client.data['lists'].append({'id':99,'key':'list:99','name':'Surplus','description':'','privacy':'private','items':[]})
        job=self.preview(categories=sorted(set(CATEGORIES)-{'playback'}),mode='mirror')
        self.assertEqual(job['status'],'completed',job)
        plan=self.service.public_plan()
        self.assertTrue(plan['destructive'])
        self.assertEqual(plan['confirmation'],'ZURÜCKSETZEN')
        restored=self.run_job('backup-restore',{'plan_id':plan['id'],'confirmation':plan['confirmation']})
        self.assertEqual(restored['status'],'completed',restored)
        self.assertEqual(self.client.data['ratings'][0]['rating'],8)
        self.assertEqual(len(self.client.data['history']),2)
        self.assertEqual(len(self.client.data['lists']),1)

    def test_pause_during_required_backup_prevents_sync_worker_launch(self):
        write(self.directory/'analysis.json',{'fingerprint':self.owner.identity()});self.owner.action('approve',{})
        def pause_during_backup():
            self.owner.state['paused']=True
        with patch.object(self.service,'before_sync',side_effect=pause_during_backup),patch('server.subprocess.Popen') as worker:
            self.assertFalse(self.owner.run('sync'))
            worker.assert_not_called()

    def test_read_only_analysis_can_complete_while_sync_is_paused(self):
        self.owner.state['paused']=True
        process=Mock();process.wait.return_value=0
        with patch('server.subprocess.Popen',return_value=process):
            self.assertTrue(self.owner.run('analyze'))


if __name__ == '__main__':
    unittest.main()
