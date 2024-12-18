import sqlite3
from flask import current_app, g

DATABASE = './database.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = make_dicts
    return db

def make_dicts(cursor, row):
    return dict((cursor.description[idx][0], value)
                for idx, value in enumerate(row))

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    result = cur.fetchall()
    cur.close()
    
    if one:
        return result[0] if result else None
    else:
        return result

def close_connection():
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db_sql_file(sql_file='./f1Tracker/schema.sql'):
    db = sqlite3.connect(DATABASE)
    with open(sql_file,'r') as f:
        db.executescript(f.read())
        db.commit()
    db.close()

