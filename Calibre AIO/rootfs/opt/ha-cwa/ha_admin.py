"""Bind a configured, Supervisor-authenticated HA login name to its stable ID."""
from pathlib import Path
from contextlib import closing
import re
import sqlite3

ADMIN_BINDINGS = Path('/data/config/ha_admin_bindings.db')


class AdminBindingUnavailable(Exception):
    pass


def is_configured_admin(uid, username, configured, path=None):
    if not configured or username != configured or not re.fullmatch(r'[0-9a-f]{32}', uid):
        return False
    try:
        with closing(sqlite3.connect(str(path or ADMIN_BINDINGS), timeout=5)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS bindings '
                       '(username TEXT PRIMARY KEY, ha_id TEXT NOT NULL)')
            db.execute('INSERT OR IGNORE INTO bindings (username, ha_id) VALUES (?, ?)',
                       (configured, uid))
            bound_id = db.execute('SELECT ha_id FROM bindings WHERE username = ?',
                                  (configured,)).fetchone()[0]
        return bound_id == uid
    except sqlite3.Error as error:
        raise AdminBindingUnavailable() from error
