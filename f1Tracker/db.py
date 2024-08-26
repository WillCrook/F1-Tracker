"""

user = query_db('select * from users where username = ?',
                [the_username], one=True)
Reference : https://flask.palletsprojects.com/en/3.0.x/patterns/sqlite3/


>>> from f1tracker import db
>>> db.init_db()
"""

import sqlite3
from flask import g

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

def query_db(query, args=()):
    cur = get_db().execute(query, args)
    result = cur.fetchall()
    cur.close()
    return result

def close_connection():
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    db = sqlite3.connect(DATABASE)
    db.cursor().execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, user TEXT, password TEXT)")
    values = ('WillCrook', 'wishstream')
    db.cursor().execute("INSERT INTO users VALUES(null, ?, ?)", values)
    db.close()