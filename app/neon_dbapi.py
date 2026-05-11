"""
Minimal psycopg2-compatible DBAPI that routes queries to Neon via HTTPS.
Looks like psycopg2 to SQLAlchemy's psycopg2 dialect.
"""
import json
import re
import urllib.request
import urllib.error
from decimal import Decimal
from datetime import datetime, date

# --- psycopg2 surface that SQLAlchemy dialect inspects ---

__version__ = "2.9.0"
paramstyle = "pyformat"
threadsafety = 2
apilevel = "2.0"


class Error(Exception):
    pass


class DatabaseError(Error):
    pass


class OperationalError(DatabaseError):
    pass


class InterfaceError(Error):
    pass


class ProgrammingError(DatabaseError):
    pass


class IntegrityError(DatabaseError):
    pass


class extensions:
    ISOLATION_LEVEL_DEFAULT = 0
    ISOLATION_LEVEL_AUTOCOMMIT = 0
    ISOLATION_LEVEL_READ_UNCOMMITTED = 4
    ISOLATION_LEVEL_READ_COMMITTED = 1
    ISOLATION_LEVEL_REPEATABLE_READ = 2
    ISOLATION_LEVEL_SERIALIZABLE = 3
    STATUS_READY = 1
    STATUS_BEGIN = 2

    class UUID:
        pass

    @staticmethod
    def register_type(typecaster, obj=None):
        pass

    @staticmethod
    def new_type(*args, **kwargs):
        return None


class extras:
    @staticmethod
    def register_uuid(oids=None, conn_or_curs=None):
        pass

    @staticmethod
    def register_hstore(*args, **kwargs):
        pass

    class HstoreAdapter:
        @staticmethod
        def get_oids(conn_or_curs):
            return None


# --- Connection / Cursor ---

class Connection:
    def __init__(self, database_url):
        host = database_url.split("@")[1].split("/")[0].split("?")[0]
        self._sql_url = f"https://{host}/sql"
        self._headers = {
            "Content-Type": "application/json",
            "Neon-Connection-String": database_url,
        }
        self.autocommit = False
        self.server_version = 140000
        self.encoding = "UTF8"
        self.notices = []
        self.isolation_level = 0

    def cursor(self, cursor_factory=None, **kwargs):
        return Cursor(self)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass

    def set_isolation_level(self, level):
        self.isolation_level = level

    def set_session(self, *args, **kwargs):
        pass

    def get_transaction_status(self):
        return 0


class Cursor:
    arraysize = 1

    def __init__(self, conn):
        self.connection = conn
        self.description = None
        self.rowcount = -1
        self._rows = []
        self._pos = 0
        self.statusmessage = None
        self.query = None
        self.typecaster = None
        self.pgresult_ptr = None

    def execute(self, query, params=None):
        if params:
            if isinstance(params, dict):
                param_values = []
                counter = [0]

                def replace_named(m):
                    counter[0] += 1
                    param_values.append(params[m.group(1)])
                    return f"${counter[0]}"

                query = re.sub(r"%\((\w+)\)s", replace_named, query)
                params = param_values
            else:
                params = list(params)
                counter = [0]

                def replace_pos(m):
                    counter[0] += 1
                    return f"${counter[0]}"

                query = re.sub(r"%s", replace_pos, query)

        serialized = []
        for p in params or []:
            if p is None:
                serialized.append(None)
            elif isinstance(p, bool):
                serialized.append(p)
            elif isinstance(p, (int, float)):
                serialized.append(p)
            elif isinstance(p, Decimal):
                serialized.append(str(p))
            elif isinstance(p, datetime):
                serialized.append(p.isoformat())
            elif isinstance(p, date):
                serialized.append(p.isoformat())
            else:
                serialized.append(str(p))

        body = json.dumps({"query": query, "params": serialized}).encode()
        req = urllib.request.Request(
            self.connection._sql_url,
            data=body,
            headers=self.connection._headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as r:
                result = json.loads(r.read())
        except urllib.error.HTTPError as e:
            raise OperationalError(e.read().decode())
        except urllib.error.URLError as e:
            raise OperationalError(str(e.reason))

        fields = result.get("fields", [])
        self.description = (
            [(f["name"], f.get("dataTypeID"), None, None, None, None, None) for f in fields]
            if fields
            else None
        )
        self.rowcount = result.get("rowCount", -1)
        col_names = [f["name"] for f in fields]
        rows = result.get("rows", [])
        if rows and isinstance(rows[0], dict):
            self._rows = [tuple(row.get(c) for c in col_names) for row in rows]
        else:
            self._rows = [tuple(r) if isinstance(r, list) else (r,) for r in rows]
        self._pos = 0

    def executemany(self, query, seq_params):
        for p in seq_params:
            self.execute(query, p)

    def fetchall(self):
        return self._rows[self._pos:]

    def fetchone(self):
        if self._pos < len(self._rows):
            row = self._rows[self._pos]
            self._pos += 1
            return row
        return None

    def fetchmany(self, size=None):
        size = size or self.arraysize
        rows = self._rows[self._pos: self._pos + size]
        self._pos += size
        return rows

    def close(self):
        pass

    def __iter__(self):
        return iter(self._rows[self._pos:])

    def mogrify(self, query, args=None):
        return query.encode()

    def callproc(self, procname, parameters=None):
        raise NotImplementedError


def connect(database_url=None, **kwargs):
    return Connection(database_url or kwargs.get("dsn", ""))
