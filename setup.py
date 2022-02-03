import psycopg2
from psycopg2.extras import DictCursor
from contextlib import closing
from psycopg2 import sql

from settings import dbname, user, password, host


def create_db() -> None:
    # Connect just to PostgreSQL with the user loaded from the .ini file
    psql_connection_string = f"user={user} password={password}"
    conn = psycopg2.connect(psql_connection_string)
    cur = conn.cursor()

    # "CREATE DATABASE" requires automatic commits
    conn.autocommit = True
    sql_query = f"CREATE DATABASE {dbname}"

    try:
        cur.execute(sql_query)
    except Exception as e:
        print(f"{type(e).__name__}: {e}")
        print(f"Query: {cur.query}")
        cur.close()
    else:
        # Revert autocommit settings
        conn.autocommit = False


def create_table_pins():
    try:
        with closing(psycopg2.connect(dbname=dbname, user=user, password=password, host=host)) as conn:
            
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                text_sql = ("-- auto-generated definition\n"
                            "create table pins\n"
                            "(\n"
                            "    id                serial    not null\n"
                            "        constraint pins_pk\n"
                            "            primary key,\n"
                            "    own               text      not null,\n"
                            "    datetime          timestamp not null,\n"
                            "    active            boolean   not null,\n"
                            "    mon               boolean   not null,\n"
                            "    tue               boolean   not null,\n"
                            "    wed               boolean   not null,\n"
                            "    tru               boolean   not null,\n"
                            "    fri               boolean   not null,\n"
                            "    sat               boolean   not null,\n"
                            "    sun               boolean   not null,\n"
                            "    time              time      not null,\n"
                            "    title             text      not null,\n"
                            "    len               time      not null,\n"
                            "    next_time_to_kick timestamp not null,\n"
                            "    current_stage     integer   not null,\n"
                            "    reset_counter     integer   not null,\n"
                            "    cancel_counter    integer   not null"
                            ");\n"
                            "\n"
                            "alter table pins\n"
                            "    owner to postgres;\n"
                            "\n"
                            "create unique index pins_id_uindex\n"
                            "    on pins (id);")
                cursor.execute(text_sql)
                conn.commit()
        return True

    except Exception as e:
        print(e)
        return False


if __name__ == "__main__":
    input(f'The database will be overwritten... Press enter')
    create_db()
    print("create_db OK")
    create_table_pins()
    print("create_table_pins OK")
    print("All OK")
    
