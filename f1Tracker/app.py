from flask import Flask, render_template, send_from_directory, session, request, redirect, url_for, flash
from f1Tracker import db
from f1Tracker import f1data
# from werkzeug.security import generate_password_hash, check_password_hash

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
    incorrectPass = False
    if request.method == 'POST':
        users = db.query_db('select * from users where email = ?', [request.form['email']])
        if len(users) == 0:
            return redirect(url_for('register'))
        # check datbase username and password
        # users = db.query_db('select * from users where email = ?', [request.form['email']])
        # if len(users) == 0:
        #     values = (request.form['email'], request.form['password'])
        #     app.logger.info(f'New user {request.form['email']} with password {request.form['password']}')
        #     db.get_db().execute('INSERT INTO users (email, password) VALUES (?, ?)', values)
        #     db.get_db().commit()

        user = users[0]
        if user['password'] != request.form['password']:
            app.logger.warning(f'user {request.form['email']} used incorrect password {request.form['password']}')
            flash('Incorrect password')
            incorrectPass = True
            return render_template('login.html', incorrectpass=incorrectPass )
        
        session['email'] = request.form['email']
        app.logger.info(f'user {session['email']} logged in')
        return redirect(url_for('home'))
        
    if request.method == 'GET':
        
        return render_template('login.html', incorrectpass=incorrectPass )
        
    # '''
    #         <form method="post">
    #             <p><input type=text name=email>
    #             <p><input type=text name=password>
    #             <p><input type=submit value=Login>
    #         </form>
    #     '''


        # return render_template('login.html')
    
@app.route('/register', methods=['GET', 'POST'])
def register():
    try:
        if request.method == "POST":
            email = request.form['email']
            first_name = request.form['firstName']
            password = request.form['password']
            driver = request.form['driver']
            team = request.form['team']
            newsletter = request.form.get('newsletter', 0)

            values = (email, first_name, password, driver, team, newsletter)
            app.logger.info(f'New user with values: {values}')

            db.get_db().execute(
                'INSERT INTO users (email, firstname, password, driverID, teamID, newsletter, verified) VALUES (?, ?, ?, ?, ?, ?, 0)', values)
            db.get_db().commit()
            session['email'] = request.form['email']
            return redirect(url_for('home'))
    except:
        return render_template('register.html')
    
    if request.method == 'GET':
        return render_template('register.html')

@app.route("/settings")
def settings():
    return render_template("settings.html")

@app.route('/logout')
def logout():
    # remove the email from the session if it's there
    session.pop('email', None)
    return redirect(url_for('home'))
 

# def upcomingGrandPrixList():

#     return f1data.getUpcomingGrandPrixInfo

# [
#         "Track Length: 5.9km",
#         "Lap Record: 1m 15.082",
#         "Most Pole Postions: Charles Leclerc(16)",
#         "Most Wins: Charles Leclerc(16)",
#         "Safety Car Probabillity: 50%",
#         "Pit Stop Loss Time: 20 Seconds"
#     ]


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

def getSignedIn():
    try:
        userloggedin = session['email']
        return True
    except:
        return False

@app.route('/')
def home():
    payload = {
        'highlights' : personalisedData(), # db
        'driverrankingsquali': driverRankingsQuali(), # db / ML
        'driverrankingsrace': driverRankingsRace(), # db / ML
        'upcominggrandprixlist': f1data.getUpcomingGrandPrixInfo(), # api
        'dropdowns' : dropDowns(), # api 
        'practiseresults' : practiseResults(), # api
        'predictionaccuracy' : predictionAccuracy(), # api
        'signedin' : getSignedIn()
        }
    return render_template('index.html', data=payload)

@app.route('/static/<path:path>')
def serve_static_files(path):
    return send_from_directory('static', path)
