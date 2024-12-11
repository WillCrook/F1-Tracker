from flask import Flask, render_template, send_from_directory, session, request, redirect, url_for, flash, send_file
from f1Tracker import db
from f1Tracker import f1data
from werkzeug.security import generate_password_hash, check_password_hash
from f1Tracker import ml
from flask_caching import Cache
from flask_mail import Mail, Message
import os
import secrets
from dotenv import load_dotenv

app = Flask(__name__)

#Load hidden variables from env file
load_dotenv("/Users/willcrook/repo/f1-tracker/f1Tracker/environmentVariables.env")

#Setup App Email 
app.config['MAIL_SERVER'] = 'smtp.gmail.com'  #Set Gmail
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('GMAIL_USERNAME')  # Stored in environment file
app.config['MAIL_PASSWORD'] = os.getenv('GMAIL_PASSWORD')  # Stored in environment file
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('GMAIL_USERNAME') # Stored in environment file
mail = Mail(app)


cache = Cache(app, config={'CACHE_TYPE': 'SimpleCache'})  # Use SimpleCache for in-memory caching

# App secret key - set using python -c 'import secrets; print(secrets.token_hex())'
app.secret_key = b'9417b2d7beab235eae274c28716b73e3c06fcb9a898bd4a930301cc4c3a2df9d'

# @app.teardown_appcontext
# def teardown_app():
#     db.close_connection()

signedIn = False
f1_data = f1data.F1Data()

def send_verification_email(email, token):
    emailMessage = Message('Your Verification Code', recipients=[email])
    emailMessage.body = f'Your verification code is: {token}'
    mail.send(emailMessage)

def generate_token():
    return secrets.token_hex(3)

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
            invalidEmail = True
            return render_template('login.html', invalidemail = invalidEmail)
        
        user = users[0]
        if not check_password_hash(user['password'], request.form['password']):
            app.logger.warning(f"user {request.form['email']} used incorrect password {request.form['password']}")
            incorrectPass = True
            return render_template('login.html', incorrectpass=incorrectPass)
        
        session['email'] = request.form['email']
        app.logger.info(f"user {session['email']} logged in")

        #Generate a verification token and send it via email
        token = generate_token()
        session['verification_token'] = token
        session['email'] = request.form['email']  #Store email in session for verification
        send_verification_email(request.form['email'], token)

        return render_template('twoFA.html')  #Render a page to input verification code
        
    if request.method == 'GET':
        return render_template('login.html', incorrectpass=incorrectPass)


@app.route('/verify_login', methods=['POST'])
def twoFA():
    if request.method == 'POST':
        token = request.form['token']
        if token == session.get('verification_token'):
            session.pop('verification_token', None)  # Clear the token
            session['email'] = session.get('email')
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid verification code. Please try again.', 'error')

    return render_template('twoFA.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    try:
        if request.method == "POST":
            email = request.form['email']
            first_name = request.form['firstName']
            password = generate_password_hash(request.form['password'])
            driver = request.form['driver']
            team = request.form['team']
            newsletter = request.form.get('newsletter', 0)

            #Check if the email is already in use
            existing_user = db.query_db('SELECT * FROM users WHERE email = ?', [email])
            if existing_user:
                flash('This email is already in use!', 'danger')
                return render_template('register.html')  # Render the registration template again

            values = (email, first_name, password, driver, team, newsletter)
            app.logger.info(f'New user with values: {values}')

            db.get_db().execute(
                'INSERT INTO users (email, firstname, password, driverID, teamID, newsletter, verified) VALUES (?, ?, ?, ?, ?, ?, 0)', values)
            db.get_db().commit()
            session['email'] = request.form['email']
            # Generate a verification token and send it via email
            token = generate_token()
            session['verification_token'] = token
            session['email'] = email  # Store email in session for verification
            send_verification_email(email, token)

            return render_template('verify.html')
    except:
        return render_template('register.html')
    
    if request.method == 'GET':
        return render_template('register.html')

@app.route('/verify', methods=['POST'])
def verify():
    if request.method == 'POST':
        token = request.form['token']
        if token == session.get('verification_token'):
            # Update user's verified status in the database
            email = session.pop('email', None)
            db.get_db().execute(
                'UPDATE users SET verified = 1 WHERE email = ?', [email])
            db.get_db().commit()
            flash('Registration successful! You can now log in.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Invalid verification code. Please try again.')

    return render_template('verify.html')

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        # Fetch updated user details from the form
        email = session.get('email')
        first_name = request.form['firstName']
        
        # Get password
        password = request.form.get('password')
        
        driver = request.form['driver']
        team = request.form['team']
        newsletter = request.form.get('newsletter', 0)  # Default to 0 if not selected

        # Check if the password is there if it is not then dont execute
        if password:
            # Update password only if it's provided
            db.get_db().execute(
                '''UPDATE users SET firstName = ?, password = ?, driverID = ?, teamID = ?, newsletter = ?
                   WHERE email = ?''',
                (first_name, password, driver, team, newsletter, email)
            )
        else:
            #No password so dont update
            db.get_db().execute(
                '''UPDATE users SET firstName = ?, driverID = ?, teamID = ?, newsletter = ?
                   WHERE email = ?''',
                (first_name, driver, team, newsletter, email)
            )

        db.get_db().commit()
        flash('Your settings have been updated!', 'success')
        return redirect(url_for('settings'))

    if request.method == 'GET':
        email = session.get('email')
        # Fetch user details from the database
        user = db.query_db('SELECT * FROM users WHERE email = ?', [email])
        if user:
            user = user[0]  # Get the first (and ideally only) user
            # Fetch all drivers and teams to display on the settings page
            teams = db.query_db('SELECT * FROM teams')
            drivers = db.query_db('SELECT * FROM drivers')
            

            return render_template('settings.html', user=user, teams=teams, drivers=drivers)

    return redirect(url_for('login'))  # Redirect to login if user not found


@app.route('/logout')
def logout():
    # remove the email from the session if it's there
    session.pop('email', None)
    flash("Succesfully logged out!", 'success')
    return redirect(url_for('home'))

@app.route('/delete_account', methods=['POST'])
def delete_account():
    try:
        email = session.get('email')

        # Delete user from the database
        db.get_db().execute('DELETE FROM users WHERE email = ?', [email])
        db.get_db().commit()

        # Log the user out
        session.pop('email', None)

        flash('Your account has been successfully deleted.', 'info')
        return redirect(url_for('home'))
    except Exception as e:
        app.logger.error(f"Error deleting account: {e}")
        flash('An error occurred while deleting your account. Please try again.', 'danger')
        return redirect(url_for('settings'))
 

#Cache used to enhance perfomance of the website
@cache.cached(timeout=3600, key_prefix='upcoming_grand_prix')
def getUpcomingGrandPrixInfo():
    return f1_data.get_upcoming_grand_prix_info()

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

#Cache again used otherwise the processing would be through the roof

@cache.cached(timeout=3600, key_prefix='driver_rankings_quali')
def driverRankingsRace():
    rankings, accuracy = ml.getRacePredictions()
    # return [{"rank": 1,
    #        "driver":"Charles Leclerc"},100]
    return [rankings, accuracy]
        

def qualiResults():
    return [
        "Top Speed: Charles Leclerc"
    ]
@cache.cached(timeout=3600, key_prefix='generate_graph')
@app.route('/generate-graph', methods=['GET'])
def generate_graph():
    graph_type = request.args.get('graphType')
    grand_prix = request.args.get('grandPrix')

    #flash messages now in the html so that they display without refreshing the page and hitting the route
    


    # Based on the selected graph type and Grand Prix, generate the appropriate graph
    if graph_type == "Position Changed during a Race":
        image_data = f1_data.get_positions_change_during_a_race(grand_prix)
    
    elif graph_type == "Qualifying Results Overview":
        image_data = f1_data.get_quali_results_overview(grand_prix)

    elif graph_type == "Gear Shifts on Track":
        image_data = f1_data.get_gear_shifts(grand_prix)
    
    elif graph_type == "Team Pace Comparison":
        image_data = f1_data.get_team_pace_comparison(grand_prix)

    elif graph_type == "Driver Laptime Comparison":
        image_data = f1_data.get_driver_laptime_comparison(grand_prix)
    
    elif graph_type == "Tyre Strategies During a Race":
        image_data = f1_data.get_tyre_strategies(grand_prix)

    # Add more conditions for other graph types
    else:
        return "Graph type not supported", 400

    # Serve the image data (this should be returned as a file object)
    return send_file(image_data, mimetype='image/png')

def getGraphTypes():
    return [
        "Position Changed during a Race", 
            "Qualifying Results Overview" , 
            "Team Pace Comparison", 
            "Driver Laptime Comparison",
            "Gear Shifts on Track",  
            "Tyre Strategies During a Race"
            ]

def practiseResults():
    return [
        "Top Speed: Charles Leclerc - 295 km/h",
        "Fastest Lap: Charles Leclerc - 1m 24.075s",
        "Fastest Sector 1: Charles Leclerc - 26.042",
        "Fastest Sector 2: Charles Leclerc - 27.010",
        "Fastest Sector 3: Charles Leclerc - 26.080"
    ]

def getSignedIn():
    try:
        userloggedin = session['email']
        return True
    except:
        return False
    
def getRecommendations(user_id):
    
    # Recommendation 1: Most viewed graphs
    most_viewed_query = '''
    SELECT displayTypeID, COUNT(*) AS views 
    FROM displayData 
    GROUP BY displayTypeID 
    ORDER BY views DESC 
    LIMIT 1;  -- Adjust the LIMIT as needed
    '''
    most_viewed = db.get_db().execute(most_viewed_query).fetchone()

    # Recommendation 2: Graph based on user's favorite driver
    # Assuming `driverID` is stored in the users table and the user has a favorite driver
    user_favorite_driver_query = '''
    SELECT displayTypeID 
    FROM displayData 
    WHERE driverID = (SELECT driverID FROM users WHERE userID = ?)
    LIMIT 1;  -- Adjust the LIMIT as needed
    '''
    user_favorite_driver = db.get_db().execute(user_favorite_driver_query, (user_id,)).fetchone()

    # Recommendation 3: Example additional recommendation
    additional_recommendation_query = '''
    SELECT displayTypeID 
    FROM displayData 
    ORDER BY RANDOM() 
    LIMIT 1;  -- Randomly select another recommendation
    '''
    additional_recommendation = db.get_db().execute(additional_recommendation_query).fetchone()

    # Collect recommendations
    recommendations = {
        'most_viewed': most_viewed,
        'user_favorite_driver': user_favorite_driver,
        'additional': additional_recommendation
    }

    return recommendations

@app.route('/')
def home():

    user_id = session.get('user_id')  # Assuming user ID is stored in session after login
    recommendations = None
    if user_id:
        recommendations = getRecommendations(user_id)

    payload = {
        'highlights' : personalisedData(), # db
        'qualiresults': qualiResults(), # db / ML
        'driverrankingsrace': driverRankingsRace()[0], # db / ML
        'upcominggrandprixlist': getUpcomingGrandPrixInfo(), # api 
        'practiseresults' : practiseResults(), # api
        'predictionaccuracy' : str(driverRankingsRace()[1]) + "%", # ML note that prediction accuracy is dRR[1] 
        'signedin' : getSignedIn(),
        'graphtypes': getGraphTypes(),
        'grandprixlist': f1_data.get_events(),  # Grand Prix events from f1data.py
        'graphtypes': getGraphTypes(),
        'recommendations': recommendations
    }

    print(driverRankingsRace()[1])
    return render_template('index.html', data=payload)

@app.route('/static/<path:path>')
def serve_static_files(path):
    return send_from_directory('static', path)
