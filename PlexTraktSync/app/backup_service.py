"""Backup job orchestration shares the Controller's single-writer lock."""
from copy import deepcopy
import hmac
import shutil
import threading
import time
import uuid

from backup_store import ArchiveStore, CATEGORIES, RESTORABLE, digest, next_run, normalize_settings, retained, selection
from storage import read, write
from trakt_backup import TraktClient, apply_plan, build_plan, normalize_capture


class StopEvents:
    def __init__(self, *events):
        self.events = events

    def is_set(self):
        return any(event.is_set() for event in self.events)


class BackupService:
    def __init__(self, owner):
        self.owner = owner
        self.directory = owner.directory
        self.store = ArchiveStore(self.directory)
        self.mutex = threading.RLock()
        self.cancel = threading.Event()
        self.thread = None
        self.settings = normalize_settings(read(self.directory / 'backup-settings.json', {}))
        self.state = read(self.directory / 'backup-state.json', {'version': 1, 'schedules': {}, 'job': None})
        if self.state.get('version') != 1:
            raise ValueError('Unbekannte Version des Sicherungsstatus.')
        if isinstance(self.state.get('job'), dict) and self.state['job'].get('status') == 'running':
            self.state['job'].update(status='interrupted', message='Durch App-Neustart unterbrochen. Schreibzugriffe nicht automatisch wiederholen; neuen Vergleich starten.')
            self.persist()
        self.reconcile(time.time())

    def persist(self):
        write(self.directory / 'backup-state.json', self.state)

    def reconcile(self, now):
        result = {}
        for schedule in self.settings['schedules']:
            key = schedule['id']
            identity = digest([schedule, self.settings['timezone']])
            old = self.state['schedules'].get(key)
            result[key] = old if old and old.get('identity') == identity else {
                'identity': identity, 'next_run': next_run(schedule, now, self.settings['timezone']), 'attempts': 0}
        self.state['schedules'] = result

    def public_plan(self):
        plan = read(self.directory / 'restore-plan.json')
        if not plan or plan['expires_at'] < time.time():
            return None
        result = {key: plan[key] for key in ('id', 'expires_at', 'archive_id', 'mode', 'categories', 'counts', 'warnings', 'destructive', 'confirmation', 'source_account', 'target_account')}
        result['examples'] = {}
        for category, change in plan['changes'].items():
            result['examples'][category] = ({'lists': [item['source']['name'] for item in change['lists']][:30],
                                              'remove_lists': [item['name'] for item in change['remove_lists']][:30]}
                if category == 'lists' else {key: [item['title'] for item in change[key]][:30] for key in ('add', 'remove')})
        return result

    def status(self):
        with self.mutex:
            entries = self.store.entries()
            keep = retained(entries, self.settings, time.time())
            used = self.store.used_bytes()
            return {'settings': deepcopy(self.settings), 'revision': digest(self.settings), 'categories': CATEGORIES,
                    'restorable': sorted(RESTORABLE), 'archives': entries, 'state': deepcopy(self.state),
                    'storage': {'used_bytes': used, 'free_bytes': shutil.disk_usage(self.store.root).free,
                                'quota_bytes': self.settings['max_total_mb'] * 1024 * 1024,
                                'quota_exceeded': used > self.settings['max_total_mb'] * 1024 * 1024},
                    'prunable': [entry['id'] for entry in entries if entry['id'] not in keep],
                    'plan': self.public_plan()}

    def progress(self, message):
        with self.mutex:
            if self.state.get('job'):
                self.state['job']['message'] = message
                self.persist()

    def client(self):
        return TraktClient(self.directory, self.owner.options['request_timeout'],
                           stop=StopEvents(self.cancel, self.owner.stop), progress=self.progress,
                           deadline=time.monotonic() + self.settings['job_timeout_minutes'] * 60)

    def create(self, client, categories, reason='manual', *, pinned=False):
        self.check_quota()
        account, data = client.snapshot(selection(categories))
        with self.mutex:
            saved = self.store.save(account, data, reason, time.time(), self.settings, pinned=pinned)
            self.store.prune(self.settings, time.time())
        return saved

    def check_quota(self):
        if self.store.used_bytes() >= self.settings['max_total_mb'] * 1024 * 1024:
            raise ValueError('Speicherlimit erreicht. Aufbewahrung prüfen oder nicht mehr benötigte Sicherungen entfernen.')

    def start(self, kind, data, *, reason='manual', schedule_id=None):
        if not self.owner.lock.acquire(blocking=False):
            raise ValueError('Wait until the current job finishes')
        try:
            if kind == 'create':
                if type(data.get('pinned', False)) is not bool:
                    raise ValueError('Ungültiger Archivschutz.')
                data = {**data, 'categories': selection(data.get('categories'))}
            elif kind == 'preview':
                self.store.path(data.get('id'))
                selection(data.get('categories'), restore=True)
                if data.get('mode') not in ('merge', 'overwrite', 'mirror') or type(data.get('allow_other_account', False)) is not bool:
                    raise ValueError('Ungültige Wiederherstellungsoptionen.')
            elif kind == 'verify':
                self.store.path(data.get('id'))
            elif kind == 'restore':
                plan = read(self.directory / 'restore-plan.json')
                if (not plan or plan['expires_at'] < time.time() or data.get('plan_id') != plan['id']
                        or not isinstance(data.get('confirmation'), str)
                        or not hmac.compare_digest(data['confirmation'].encode('utf-8'), plan['confirmation'].encode('utf-8'))
                        or plan['identity'] != self.owner.identity()):
                    raise ValueError('Neue Vorschau und passende Bestätigung erforderlich.')
            else:
                raise ValueError('Unbekannter Sicherungsauftrag.')
            self.cancel.clear()
            with self.mutex:
                job_id = uuid.uuid4().hex
                self.state['job'] = {'id': job_id, 'kind': kind, 'status': 'running', 'started_at': time.time(), 'message': 'Auftrag startet …'}
                self.persist()
            self.thread = threading.Thread(target=self.run, args=(kind, deepcopy(data), reason, schedule_id), daemon=True)
            self.thread.start()
            return {'accepted': True, 'job_id': job_id}
        except Exception:
            self.owner.lock.release()
            raise

    def run(self, kind, data, reason, schedule_id):
        success = False
        client = None
        try:
            if kind != 'verify':
                client = self.client()
            if kind == 'verify':
                manifest, payload = self.store.inspect(self.store.path(data['id']))
                normalize_capture(payload)
                result = {'archive_id': manifest['id'], 'verified': True, 'counts': manifest['counts']}
            elif kind == 'create':
                archive = self.create(client, data['categories'], reason, pinned=bool(data.get('pinned', False)))
                result = {'archive_id': archive['id'], 'counts': archive['counts']}
            elif kind == 'preview':
                result = self.preview(client, data)
            else:
                result = self.restore(client, data)
            with self.mutex:
                self.state['job'].update(status='completed', finished_at=time.time(), message='Erfolgreich abgeschlossen.', result=result)
                if kind == 'create':
                    self.state['last_success'] = time.time()
            success = True
        except Exception as error:
            message = str(error) if isinstance(error, ValueError) else 'Auftrag fehlgeschlagen (' + type(error).__name__ + ').'
            with self.mutex:
                self.state['job'].update(status='cancelled' if self.cancel.is_set() else 'failed',
                                         finished_at=time.time(), message=message)
            self.owner.log('backup_job_failed', level='error', kind=kind, error_type=type(error).__name__)
        finally:
            try:
                if client is not None and hasattr(client, 'close'):
                    client.close()
                with self.mutex:
                    if schedule_id and schedule_id in self.state['schedules']:
                        saved = self.state['schedules'][schedule_id]
                        schedule = next(item for item in self.settings['schedules'] if item['id'] == schedule_id)
                        saved['last_attempt'] = time.time()
                        if success:
                            saved['last_success'] = time.time()
                            saved['attempts'] = 0
                            saved['next_run'] = next_run(schedule, time.time(), self.settings['timezone'])
                        elif saved['attempts'] < self.settings['retry_count']:
                            saved['attempts'] += 1
                            saved['next_run'] = time.time() + self.settings['retry_minutes'] * 60 * saved['attempts']
                        else:
                            saved['attempts'] = 0
                            saved['next_run'] = next_run(schedule, time.time(), self.settings['timezone'])
                    self.persist()
            finally:
                self.owner.lock.release()

    def preview(self, client, data):
        # A failed new preview must never leave an older approval available.
        (self.directory / 'restore-plan.json').unlink(missing_ok=True)
        manifest, source = self.store.inspect(self.store.path(data['id']))
        source = normalize_capture(source)
        categories = selection(data['categories'], restore=True)
        account, current = client.snapshot(categories)
        if account['id'] != manifest['account']['id'] and not data.get('allow_other_account'):
            raise ValueError('Sicherung stammt von einem anderen Trakt-Konto. Kontowechsel ausdrücklich erlauben.')
        plan = build_plan(source, current, categories, data['mode'])
        plan.update(id=uuid.uuid4().hex, expires_at=time.time() + 900, archive_id=data['id'],
                    archive_digest=digest([manifest, source]), current_digest=digest(current),
                    identity=self.owner.identity(), source_account=manifest['account'], target_account=account,
                    confirmation='ZURÜCKSETZEN' if plan['destructive'] else 'WIEDERHERSTELLEN')
        write(self.directory / 'restore-plan.json', plan)
        return self.public_plan()

    def journal(self, event):
        value = read(self.directory / 'restore-journal.json', {'events': [], 'requests': 0, 'confirmed': 0})
        value['events'] = (value['events'] + [{**event, 'at': time.time()}])[-250:]
        value['requests' if event['phase'] == 'request' else 'confirmed'] += 1
        write(self.directory / 'restore-journal.json', value)

    def restore(self, client, data):
        plan = read(self.directory / 'restore-plan.json')
        if not plan or plan['id'] != data['plan_id'] or plan['expires_at'] < time.time() or plan['identity'] != self.owner.identity():
            raise ValueError('Wiederherstellungsvorschau ist abgelaufen oder ungültig.')
        manifest, source = self.store.inspect(self.store.path(plan['archive_id']))
        source = normalize_capture(source)
        if digest([manifest, source]) != plan['archive_digest']:
            raise ValueError('Sicherung wurde seit der Vorschau geändert.')
        self.owner.stop_watch()
        account, current = client.snapshot(plan['categories'])
        if account['id'] != plan['target_account']['id'] or digest(current) != plan['current_digest']:
            raise ValueError('Trakt wurde seit der Vorschau verändert. Neuen Vergleich starten.')
        # This capture is exactly the state compared above. No API write before a
        # fully verified, pinned rollback archive has been durably published.
        with self.mutex:
            safety = self.store.save(account, current, 'pre-restore', time.time(), self.settings, pinned=True)
        with self.mutex:
            self.state['job']['safety_archive'] = safety['id']
            self.persist()
        self.owner.state['paused'] = True
        self.owner.save()
        for name in ('approval.json', 'analysis.json', 'restore-plan.json'):
            (self.directory / name).unlink(missing_ok=True)
        write(self.directory / 'restore-journal.json', {'events': [], 'requests': 0, 'confirmed': 0,
                                                       'safety_archive': safety['id'], 'started_at': time.time()})
        apply_plan(client, plan, source, self.journal)
        verified_account, actual = client.snapshot(plan['categories'])
        if verified_account['id'] != account['id']:
            raise ValueError('Kontowechsel während der Wiederherstellung.')
        remaining = build_plan(source, actual, plan['categories'], plan['mode'])
        if any(row['add'] or row['remove'] or row.get('create_lists') or row.get('delete_lists') or row.get('update_lists') or row.get('reorder')
               for row in remaining['counts'].values()):
            raise ValueError('Nachprüfung weicht vom gewünschten Stand ab. Rückfallsicherung bleibt erhalten; neuen Vergleich starten.')
        return {'verified': True, 'safety_archive': safety['id'], 'counts': plan['counts'],
                'message': 'Trakt-Inhalte nachgeprüft. Sync bleibt bis zu neuer Analyse/Freigabe pausiert.'}

    def handle(self, action, data):
        if not isinstance(data, dict):
            raise ValueError('Ungültige Sicherungsanfrage.')
        if action in ('backup-create', 'backup-preview', 'backup-restore', 'backup-verify'):
            return self.start(action.removeprefix('backup-'), data)
        if action == 'backup-cancel':
            self.cancel.set()
            return {'ok': True}
        if not self.owner.lock.acquire(blocking=False):
            raise ValueError('Wait until the current job finishes')
        try:
            with self.mutex:
                if action == 'backup-settings':
                    if data.get('revision') != digest(self.settings):
                        raise ValueError('Sicherungseinstellungen wurden in einer anderen Sitzung geändert. Neu laden.')
                    settings = normalize_settings(data.get('settings'))
                    write(self.directory / 'backup-settings.json', settings)
                    self.settings = settings
                    self.reconcile(time.time())
                    self.persist()
                elif action == 'backup-pin':
                    self.store.pin(data.get('id'), data.get('pinned'))
                elif action == 'backup-delete':
                    if data.get('confirmation') != 'LÖSCHEN':
                        raise ValueError('Löschung ausdrücklich bestätigen.')
                    self.store.delete(data.get('id'))
                    (self.directory / 'restore-plan.json').unlink(missing_ok=True)
                elif action == 'backup-prune':
                    if data.get('confirmation') != 'BEREINIGEN' or data.get('revision') != digest(self.settings):
                        raise ValueError('Aufbewahrungsbereinigung bestätigen.')
                    self.store.prune(self.settings, time.time())
                else:
                    raise ValueError('Unbekannte Sicherungsaktion.')
                return {'ok': True}
        finally:
            self.owner.lock.release()

    def import_archive(self, raw):
        if not self.owner.lock.acquire(blocking=False):
            raise ValueError('Wait until the current job finishes')
        try:
            with self.mutex:
                self.check_quota()
                saved = self.store.import_archive(raw, self.settings, time.time())
            return {'ok': True, 'archive_id': saved['id']}
        finally:
            self.owner.lock.release()

    def tick(self):
        if not self.settings['enabled'] or self.owner.stop.is_set() or self.owner.lock.locked():
            return False
        with self.mutex:
            due = next((item for item in self.settings['schedules'] if item['enabled']
                        and self.state['schedules'][item['id']]['next_run'] <= time.time()), None)
        if due:
            try:
                self.start('create', {'categories': due['categories']}, reason='schedule', schedule_id=due['id'])
                return True
            except ValueError:
                return False
        return False

    def before_sync(self):
        if not self.settings['before_sync']:
            return
        identity = digest([self.owner.identity(), read(self.directory / '.pytrakt.json', {}).get('OAUTH_TOKEN')])
        old = self.state.get('pre_sync', {})
        if old.get('identity') == identity and old.get('at', 0) > time.time() - self.settings['before_sync_minutes'] * 60:
            return
        self.cancel.clear()
        client = self.client()
        try:
            saved = self.create(client, self.settings['categories'], 'pre-sync')
        finally:
            if hasattr(client, 'close'):
                client.close()
        with self.mutex:
            self.state['pre_sync'] = {'at': time.time(), 'archive_id': saved['id'],
                'identity': digest([self.owner.identity(), read(self.directory / '.pytrakt.json', {}).get('OAUTH_TOKEN')])}
            self.persist()
