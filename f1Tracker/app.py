from flask import Flask, render_template, send_from_directory, session, request, redirect, url_for, flash
from f1Tracker import db
from f1Tracker import f1data


app = Flask(__name__)

# App secret key - set using python -c 'import secrets; print(secrets.token_hex())'
app.secret_key = b'9417b2d7beab235eae274c28716b73e3c06fcb9a898bd4a930301cc4c3a2df9d'

# @app.teardown_appcontext
# def teardown_app():
#     db.close_connection()

signedIn = False

def test_request_example(client):
    response = client.get("/posts")
    assert b"<h2>Hello, World!</h2>" in response.data

@app.route("/helloworld")
def hello_world():
    return "<p>Hello, World!</p>"

@app.route("/db_init")
def db_init():
    db.init_db_sql_file()
    return 'OK'

"""
LOGIN / LOGOUT
reference : https://flask.palletsprojects.com/en/3.0.x/quickstart/#sessions
refactor : https://flask.palletsprojects.com/en/3.0.x/tutorial/views/#the-first-view-register

"""
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # check datbase username and password
        users = db.query_db('select * from users where username = ?', [request.form['username']])
        if len(users) == 0:
            values = (request.form['username'], request.form['password'])
            app.logger.info(f'New user {request.form['username']} with password {request.form['password']}')
            db.get_db().execute('INSERT INTO users (username, password) VALUES (?, ?)', values)
            db.get_db().commit()
        else:
            user = users[0]
            if user['password'] != request.form['password']:
                app.logger.warning(f'user {request.form['username']} used incorrect password {request.form['password']}')
                flash('Incorrect password')
                return redirect(url_for('login'))
        session['username'] = request.form['username']
        app.logger.info(f'user {user['username']} logged in')
        return redirect(url_for('home'))
    
    if request.method == 'GET':
        return '''
            <form method="post">
                <p><input type=text name=username>
                <p><input type=text name=password>
                <p><input type=submit value=Login>
            </form>
        '''


        # return render_template('login.html')
    
    

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


def personalisedData():
    return [
        {
            "dataTitle": 'Tyre Wear',
            "driver" : "See how Charles Leclerc performed"
         
         },
         {
             "dataTitle": 'Race Pace',
             "driver" : "See how Lewis Hamilton performed"
         },
         {
             "dataTitle": "Braking Performance",
             "driver": "See how Lando Norris performed"
         }   
    ]

def driverRankingsQuali():
    return [
        {
        'driver': 'Lec',
        'predictioncertainty': '0%',
        'rank': '1'
    },
    {
        'driver': 'Ver',
        'predictioncertainty': '0%',
        'rank': '2'
        }
        ]

def driverRankingsRace():
    return [
        {
        'driver': 'Lec',
        'predictioncertainty': '0%',
        'rank': '1',
    }]

def dropDowns():
    return [
        {
            'title' : "Driver",
            'contents' : ["Lec", 'Norris']
        },
        {
            'title' : "Year",
            'contents' : ["2024","2023","2022"]
        }
    ]

def practiseResults():
    return [
        "Top Speed: Charles Leclerc - 295 km/h",
        "Fastest Lap: Charles Leclerc - 1m 24.075s",
        "Fastest Sector 1: Charles Leclerc - 26.042",
        "Fastest Sector 2: Charles Leclerc - 27.010",
        "Fastest Sector 3: Charles Leclerc - 26.080"
    ]
def predictionAccuracy():
    return "0%"
@app.route('/')
def home():
    payload = {
        'highlights' : personalisedData(), # db
        'driverrankingsquali': driverRankingsQuali(), # db / ML
        'driverrankingsrace': driverRankingsRace(), # db / ML
        'upcominggrandprixlist': upcomingGrandPrixList(), # api
        'dropdowns' : dropDowns(), # api 
        'practiseresults' : practiseResults(), # api
        'predictionaccuracy' : predictionAccuracy(), # api
        'signedin' : signedIn
        }
    return render_template('index.html', data=payload)

@app.route('/static/<path:path>')
def serve_static_files(path):
    return send_from_directory('static', path)
