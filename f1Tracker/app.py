from flask import Flask, render_template, send_from_directory, session, request, redirect, url_for
from f1Tracker import db

app = Flask(__name__)

# App secret key - set using python -c 'import secrets; print(secrets.token_hex())'
app.secret_key = b'9417b2d7beab235eae274c28716b73e3c06fcb9a898bd4a930301cc4c3a2df9d'

# @app.teardown_appcontext
# def teardown_app():
#     db.close_connection()

@app.route("/helloworld")
def hello_world():
    return "<p>Hello, World!</p>"

def DriverRankingsQuali():
    return [{
        'first': 'Will',
        'last': 'Crook',
        'rank': '1'
    }]

"""
LOGIN / LOGOUT
reference : https://flask.palletsprojects.com/en/3.0.x/quickstart/#sessions
"""
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # check datbase username and password
        user = db.query_db('select * from users where username = ?', [request.form['username']])
        if user is None:
            app.logger.info(f'New user {request.form['username']}')
            #  db.query_db('insert ')
        else:
            if user['password'] != request.form['password']:
                app.logger.info(f'user {request.form['username']} used incorrect password {request.form['password']}')
                return redirect(url_for('login'))
        session['username'] = request.form['username']
        return redirect(url_for('home'))
    
    if request.method == 'GET':
        return '''
            <form method="post">
                <p><input type=text name=username>
                <p><input type=text name=password>
                <p><input type=submit value=Login>
            </form>
        '''

@app.route('/logout')
def logout():
    # remove the username from the session if it's there
    session.pop('username', None)
    return redirect(url_for('home'))
 
def upcomingGrandPrixList():
    return [
        "Track Length: 5.9km",
        "Lap Record: 1m 15.082",
        "Most Pole Postions: Charles Leclerc(16)",
        "Most Wins: Charles Leclerc(16)",
        "Safety Car Probabillity: 50%",
        "Pit Stop Loss Time: 20 Seconds"
    ]

@app.route('/')
def home():
    payload = {
        'name':'Will', 
        'age': 17, 
        'driverrankingsquali': DriverRankingsQuali(),
        'upcominggrandprixlist': upcomingGrandPrixList()
        }
    return render_template('index.html', data=payload)

@app.route('/static/<path:path>')
def serve_static_files(path):
    return send_from_directory('static', path)
