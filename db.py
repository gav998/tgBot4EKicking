import psycopg2
from psycopg2.extras import DictCursor
from contextlib import closing

import datetime
from settings import dbname, user, password, host


pin_template = {
    "own": "",
    "datetime": datetime.datetime(1970, 1, 1, 0, 0, 1),
    "active": True,
    "mon": False,
    "tue": False,
    "wed": False,
    "tru": False,
    "fri": False,
    "sat": False,
    "sun": False,
    "time": datetime.time(0, 0),
    "title": "",
    "len": datetime.time(0, 5),
    "next_time_to_kick": datetime.datetime(1970, 1, 1, 0, 0, 1),
    "current_stage": 0,
    "reset_counter": 0,
    "cancel_counter": 0,
}


def pin_insert(pin: dict):
    try:
        with closing(psycopg2.connect(dbname=dbname, user=user, password=password, host=host)) as conn:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(
                    'INSERT INTO pins(own, datetime, active, '
                    'mon, tue, wed, tru, fri, sat, sun, '
                    'time, title, len, next_time_to_kick, current_stage,'
                    'reset_counter, cancel_counter)\n'
                    'VALUES (%(own)s, %(datetime)s, %(active)s, '
                    '%(mon)s, %(tue)s, %(wed)s, %(tru)s, %(fri)s, %(sat)s, %(sun)s, '
                    '%(time)s, %(title)s, %(len)s, %(next_time_to_kick)s, %(current_stage)s,'
                    '%(reset_counter)s, %(cancel_counter)s)\n'
                    'RETURNING id;',
                    pin)
                _id = cursor.fetchone()[0]
                conn.commit()
        return _id

    except Exception as e:
        print(e)
        return False


def pin_delete(own, title):
    try:
        with closing(psycopg2.connect(dbname=dbname, user=user, password=password, host=host)) as conn:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(
                    'DELETE FROM pins\n'
                    'WHERE own = %(own)s '
                    'AND title = %(title)s'
                    'RETURNING *;',
                    {'own': str(own),
                     'title': str(title)})
                pins = cursor.fetchall()
                conn.commit()
        if len(pins) > 0:
            return True
        return False

    except Exception as e:
        print(e)
        return False


def pin_get_all(own):
    try:
        with closing(psycopg2.connect(dbname=dbname, user=user, password=password, host=host)) as conn:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(
                    'SELECT * FROM pins\n'
                    'WHERE own = %(own)s;',
                    {'own': str(own)})
                pins = cursor.fetchall()
                conn.commit()
        return pins

    except Exception as e:
        print(e)
        return False


def pin_get_all_titles(own):
    try:
        with closing(psycopg2.connect(dbname=dbname, user=user, password=password, host=host)) as conn:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(
                    'SELECT title FROM pins\n'
                    'WHERE own = %(own)s;',
                    {'own': str(own)})
                pins = cursor.fetchall()
                conn.commit()
        return pins

    except Exception as e:
        print(e)
        return False


def pin_get_nearest():
    try:
        with closing(psycopg2.connect(dbname=dbname, user=user, password=password, host=host)) as conn:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(
                    "SELECT * FROM pins\n"
                    "WHERE next_time_to_kick < now()\n"
                    "ORDER BY next_time_to_kick;")
                column_names = [desc[0] for desc in cursor.description]
                pins = cursor.fetchall()
                conn.commit()
        return map(lambda x: dict(zip(column_names, x)), pins)

    except Exception as e:
        print(e)
        return False


def pin_get_expired(own):
    try:
        with closing(psycopg2.connect(dbname=dbname, user=user, password=password, host=host)) as conn:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(
                    "SELECT * FROM pins\n"
                    "WHERE own = %(own)s AND current_stage > 0\n"
                    "ORDER BY current_stage DESC;",
                    {'own': str(own)})
                column_names = [desc[0] for desc in cursor.description]
                pins = cursor.fetchall()
                conn.commit()
        return map(lambda x: dict(zip(column_names, x)), pins)

    except Exception as e:
        print(e)
        return False


def pin_update(pin):
    try:
        with closing(psycopg2.connect(dbname=dbname, user=user, password=password, host=host)) as conn:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(
                    "UPDATE pins\n"
                    "SET "
                    "(own, datetime, active, "
                    "mon, tue, wed, tru, fri, sat, sun, "
                    "time, title, len, next_time_to_kick, current_stage, "
                    "reset_counter, cancel_counter)"
                    " = "
                    "(%(own)s, %(datetime)s, %(active)s,"
                    "%(mon)s, %(tue)s, %(wed)s, %(tru)s, %(fri)s, %(sat)s, %(sun)s, "
                    "%(time)s, %(title)s, %(len)s, %(next_time_to_kick)s, %(current_stage)s,"
                    "%(reset_counter)s, %(cancel_counter)s)\n"
                    "WHERE id = %(id)s"
                    "RETURNING *;",
                    pin)

                cursor.fetchone()[0]
                conn.commit()
        return True

    except Exception as e:
        print(e)
        return False
