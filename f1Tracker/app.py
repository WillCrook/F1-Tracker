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
from io import BytesIO
from datetime import datetime, timedelta, timezone

app = Flask(__name__)

#load hidden variables from env file
load_dotenv("/Users/willcrook/Documents/repo/f1-tracker/environmentVariables.env")

#setup App Email 
app.config['MAIL_SERVER'] = 'smtp.gmail.com'  #using gmail api
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('GMAIL_USERNAME')  #stored in environment file
app.config['MAIL_PASSWORD'] = os.getenv('GMAIL_PASSWORD')  #stored in environment file
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('GMAIL_USERNAME') #stored in environment file
mail = Mail(app)

cache = Cache(app, config={'CACHE_TYPE': 'SimpleCache'}) 

#app secret key - set using python -c 'import secrets; print(secrets.token_hex())'
app.secret_key = b'9417b2d7beab235eae274c28716b73e3c06fcb9a898bd4a930301cc4c3a2df9d'

signedIn = False
f1_data = f1data.F1Data()

def send_verification_email(email, token):
    emailMessage = Message('Your Verification Code', recipients=[email])
    emailMessage.body = f'Your verification code is: {token}'
    mail.send(emailMessage)

def generate_token():
    return secrets.token_hex(3)

@app.route("/db_init")
def db_init():
    db.init_db_sql_file()
    app.logger.info("Database Initalised")
    return 'OK Database Initalised'

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

        #generate a verification token and send it via email
        token = generate_token()
        session['verification_token'] = token
        session['email'] = request.form['email']  #store email in session for verification
        send_verification_email(request.form['email'], token)
        flash("2FA Code Sent to Email!", 'success')
        return render_template('twoFA.html') 
        
    if request.method == 'GET':
        return render_template('login.html', incorrectpass=incorrectPass)

@app.route('/twoFA', methods=['POST'])
def twoFA():
    if request.method == 'POST':
        token = request.form['token']
        if token == session.get('verification_token'):
            session.pop('verification_token', None)  #once user has entered token clear it
            session['email'] = session.get('email')
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid login code. Please try again.', 'error')

    return render_template('twoFA.html')

def generate_reset_token(user_email):
    token = secrets.token_urlsafe(32)  #generate secure token
    expiry = datetime.now(timezone.utc) + timedelta(hours=1)  #token valid for 1 hour
    
    query = '''
        UPDATE users
        SET reset_token = ?, reset_token_expiry = ?
        WHERE email = ?
    '''
    db.query_db(query, (token, expiry, user_email))
    db.get_db().commit()
    return token

def send_reset_email(user_email):

    token = generate_reset_token(user_email)
    reset_url = url_for('reset_password', token=token, _external=True)

    subject = "Password Reset Request"
    body = f"""
    Hi, 

    You requested a password reset. Click the link below to reset your password:
    
    {reset_url}
    
    If you did not request this, ignore this email.

    F1 Tracker
    """
    msg = Message(subject=subject, recipients=[user_email], body=body)
    mail.send(msg)

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    query = '''
        SELECT email, reset_token_expiry 
        FROM users 
        WHERE reset_token = ?
    '''
    result = db.query_db(query, (token,))
    
    if not result:
        flash("Invalid or expired token.", "danger")
        return redirect(url_for('home'))

    #convert reset_token_expiry to a datetime object so that is can be compared
    try:
        reset_token_expiry = datetime.fromisoformat(result[0]['reset_token_expiry'])
    except (KeyError, ValueError):
        flash("Invalid token expiry format.", "danger")
        return redirect(url_for('home'))
    
    #check if the token has expired
    if datetime.now(timezone.utc) > reset_token_expiry:
        flash("Token has expired.", "danger")
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        new_password = request.form['new_password']
        hashed_password = generate_password_hash(new_password)
        
        update_query = '''
            UPDATE users
            SET password = ?, reset_token = NULL, reset_token_expiry = NULL
            WHERE reset_token = ?
        '''
        db.get_db().execute(update_query, (hashed_password, token))
        db.get_db().commit()
        flash("Password reset successfully!", "success")
        return redirect(url_for('login'))
    
    return render_template('reset_password.html', token=token)
    
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        user_email = request.form['email']
        
        query = 'SELECT email FROM users WHERE email = ?'
        result = db.query_db(query, (user_email,))
        
        if result:
            send_reset_email(user_email)
            flash("Password reset email sent!", "info")
        else:
            flash("Email not found.", "danger")
        
        return redirect(url_for('forgot_password'))
    
    return render_template('forgot_password.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    try:
        if request.method == "POST":
            #take data from form
            email = request.form['email']
            first_name = request.form['firstName']
            password = generate_password_hash(request.form['password'])
            driver = request.form['driver']
            team = request.form['team']
            newsletter = request.form.get('newsletter', 0)

            #check if the email is already in use
            existing_user = db.query_db('SELECT * FROM users WHERE email = ?', [email])
            if existing_user:
                flash('This email is already in use!', 'danger')
                return render_template('register.html')  #render again so the user can retype the details

            values = (email, first_name, password, driver, team, newsletter)
            app.logger.info(f'New user with values: {values}')

            db.get_db().execute(
                'INSERT INTO users (email, firstname, password, driverID, teamID, newsletter, verified) VALUES (?, ?, ?, ?, ?, ?, 0)', values)
            db.get_db().commit()
            session['email'] = request.form['email']
            #generate a verification token and send it via email
            token = generate_token()
            session['verification_token'] = token
            session['email'] = email #store email in session for verification
            send_verification_email(email, token)

            return render_template('verify.html')
    except Exception as e:
        flash("Something went wrong sending email", "error")
        app.logger.warning(f"Something went wrong: {e}")
        return render_template('register.html')
    
    if request.method == 'GET':
        return render_template('register.html')

@app.route('/verify', methods=['POST'])
def verify():
    if request.method == 'POST':
        token = request.form['token']
        if token == session.get('verification_token'):
            #update in the database to show that the user is verified
            email = session['email']
            db.get_db().execute(
                'UPDATE users SET verified = 1 WHERE email = ?', [email])
            db.get_db().commit()
            flash('Registration successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid verification code. Please try again.')

    return render_template('verify.html')

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        #fetch updated user details from the form
        email = session.get('email')
        first_name = request.form['firstName']
        password = request.form.get('password')
        
        driver = request.form['driver']
        team = request.form['team']
        newsletter = request.form.get('newsletter', 0) #default is that they are not registered for the newsletter

        if password:
            password = generate_password_hash(password)
            #update password only if it's provided
            db.get_db().execute(
                '''UPDATE users SET firstName = ?, password = ?, driverID = ?, teamID = ?, newsletter = ?
                   WHERE email = ?''',
                (first_name, password, driver, team, newsletter, email)
            )
        else:
            #no password so dont update
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
        #fetch user details from the database
        user = db.query_db('SELECT * FROM users WHERE email = ?', [email])
        if user:
            user = user[0]  #get the first (and hopefully only) user
            #fetch all drivers and teams to display on the settings page
            #so that the user can change their favourite driver and team
            teams = db.query_db('SELECT * FROM teams')
            drivers = db.query_db('SELECT * FROM drivers')
            

            return render_template('settings.html', user=user, teams=teams, drivers=drivers)

    return redirect(url_for('login'))  #redirect to login if user not found


@app.route('/logout')
def logout():
    # remove the email from the session if it's there
    session.pop('email', None)
    flash("Succesfully logged out!", 'success')
    return redirect(url_for('home'))

@app.route('/delete-account', methods=['POST'])
def delete_account():
    try:
        email = session.get('email')

        #delete user from the database
        db.get_db().execute('DELETE FROM users WHERE email = ?', [email])
        db.get_db().commit()

        #log the user out
        session.pop('email', None)

        flash('Your account has been successfully deleted.', 'info')
        return redirect(url_for('home'))
    except Exception as e:
        app.logger.error(f"Error deleting account: {e}")
        flash('An error occurred while deleting your account. Please try again.', 'danger')
        return redirect(url_for('settings'))

def get_admin():
    email = session.get('email')
    if not email:
        return 0  #return 0 if email is not found (user not signed in) so obviously their not an admin
    
    query = '''
        SELECT admin.permissions
        FROM admin
        INNER JOIN users ON admin.userID = users.userID
        WHERE users.email = ?
    '''
    result = db.query_db(query, [email], one=True)
    return result['permissions'] if result else 0  #default to 0 if no admin permissions


@app.route('/admin', methods=['GET', 'POST'])
def admin_terminal():
    admin_permissions = get_admin()  #check if the user is an admin
    if not admin_permissions:
        flash("Unauthorized access!", "danger")
        return redirect(url_for('home'))

    #sort: default is to sort by userID
    sort_by = request.args.get('sort_by', 'userID')
    valid_sort_columns = ['userID', 'email', 'is_admin']
    if sort_by not in valid_sort_columns:
        sort_by = 'userID'

    stats_query = '''
    SELECT 
        COUNT(CASE WHEN users.newsletter = 1 THEN 1 END) AS newsletter_count,
        most_common_driver.driverName AS most_common_driver,
        most_common_team.teamName AS most_common_team
    FROM users
    LEFT JOIN drivers AS most_common_driver
        ON users.driverID = most_common_driver.driverID
    LEFT JOIN teams AS most_common_team
        ON users.teamID = most_common_team.teamID
    GROUP BY most_common_driver.driverName, most_common_team.teamName
    '''
    stats = db.query_db(stats_query)
    newsletter_count = stats[0]['newsletter_count'] if stats else 0
    most_common_driver = stats[0]['most_common_driver'] if stats else None
    most_common_team = stats[0]['most_common_team'] if stats else None

    #fetch users with admin status using JOIN
    query = f'''
        SELECT users.userID, users.email, users.firstname, users.verified, 
               users.newsletter, users.driverID, users.teamID,
               CASE WHEN admin.userID IS NOT NULL THEN admin.permissions ELSE 0 END AS is_admin
        FROM users
        LEFT JOIN admin ON users.userID = admin.userID
    '''
    users = db.query_db(query)
    users = merge_sort(users, sort_by)
    if sort_by == 'is_admin':
        users.reverse()  # To display the list by admin first

    #get data from admin.html
    if request.method == 'POST':
        action = request.form.get('action')
        user_id = request.form.get('user_id')
        email = request.form.get('email')

        #check for correct admin perms before carrying out action
        if action == 'send_newsletter' and admin_permissions >= 1:
            send_newsletter()
            flash("Newsletter sent successfully!", "success")

        elif action == 'add_admin' and admin_permissions >= 3:
            level = int(request.form.get('admin_level', 1))
            add_admin(email, level)
            flash(f"{email} added as admin!", "success")

        elif action == 'remove_admin' and admin_permissions >= 3:
            remove_admin(user_id)
            flash("User removed from admins!", "success")

        elif action == 'delete_user' and admin_permissions >= 3:
            delete_user(user_id)
            flash("User account deleted!", "danger")

        elif action == 'clear_recommendations' and admin_permissions >= 2:
            #clears recommendations
            query = "DELETE FROM displayData"
            db.query_db(query)
            db.get_db().commit()
            flash("Recommendations successfully cleared", "success")

        else:
            flash("You do not have permission to perform this action.", "danger")

        return redirect(url_for('admin_terminal'))

    return render_template('admin.html', users=users, sort_by=sort_by, admin_permissions=admin_permissions, 
                           newsletter_count=newsletter_count, most_common_driver=most_common_driver, 
                           most_common_team=most_common_team)

def add_admin(email, permissions):
    #query to check if the user exists and get their userID with a LEFT JOIN
    query = '''
        SELECT u.userID, a.permissions
        FROM users u
        LEFT JOIN admin a ON u.userID = a.userID
        WHERE u.email = ?
    '''
    user = db.query_db(query, [email], one=True)

    if user:
        #if the user already has permissions in the admin table, they're already an admin
        if user['permissions'] is not None:
            app.logger.info(f"{email} is already an admin.")
            return False  #the user is already an admin

        #insert the user as an admin with the specified permissions
        insert_query = 'INSERT INTO admin (userID, permissions) VALUES (?, ?)'
        db.query_db(insert_query, [user['userID'], permissions])
        db.get_db().commit()
        app.logger.info(f"{email} has been made an admin")
        return True  #admin added successfully
    else:
        app.logger.error(f"User with email {email} not found.")
        return False  #user not found

    
def remove_admin(user_id):
    query = 'DELETE FROM admin WHERE userID = ?'
    db.query_db(query, [user_id])
    db.get_db().commit()
    app.logger.info(f"User ID: {user_id} has been removed from admin")

def delete_user(user_id):
    #first, check if the user is an admin
    query = 'SELECT * FROM admin WHERE userID = ?'
    admin_record = db.query_db(query, [user_id], one=True)

    #if the user is an admin, delete them from the admin table
    if admin_record:
        delete_admin_query = 'DELETE FROM admin WHERE userID = ?'
        db.query_db(delete_admin_query, [user_id])
        db.get_db().commit() 

    #now, delete the user from the users table
    delete_user_query = 'DELETE FROM users WHERE userID = ?'
    db.query_db(delete_user_query, [user_id])
    db.get_db().commit() 
    app.logger.info(f"User ID: {user_id} and associated admin record (if any) have been deleted.")


def merge_sort(data, key):

    #base case, less than 1 item it is sorted
    if len(data) <= 1:
        return data

    #divide into two halves
    mid = len(data) // 2

    #recursively sort the left half
    left = merge_sort(data[:mid], key)

    #recursively sort the right half
    right = merge_sort(data[mid:], key)

    #merge the two sorted halves into a single sorted list
    return merge(left, right, key)

def merge(left, right, key):

    result = []  

    #while both lists have elements, compare the first elements and merge them.
    while left and right:
        #compare based on the key
        if str(left[0][key]) <= str(right[0][key]):
            result.append(left.pop(0))  #if the element is smaller on the left assign that 
        else:
            result.append(right.pop(0))  #otherwise assign the element on the right

    #check if there are elements left, if there are then add them to the final result
    if left:
        remaining = left
    else:
        remaining = right
    result.extend(remaining)

    return result


#cache used to enhance performance of the website
@cache.cached(timeout=3600, key_prefix='upcoming_grand_prix')
def getUpcomingGrandPrixInfo():
    return f1_data.get_upcoming_grand_prix_info()

#cache again used otherwise the processing would be through the roof

@cache.cached(timeout=3600, key_prefix='driver_rankings_quali')
def driverRankingsRace():
    rankings, accuracy = ml.getRacePredictions()
    return [rankings, accuracy]
        
def qualiResults():
    return [
        "Top Speed: Charles Leclerc"
    ]
@cache.cached(timeout=3600, key_prefix='generate-graph')
@app.route('/generate-graph', methods=['GET'])
def generate_graph():
    graph_type = request.args.get('graphType')
    grand_prix = request.args.get('grandPrix')

    #increment view count for the selected graph type
    db.get_db().execute('''
        INSERT INTO displayData (displayTypeID, driverID, grandPrix, views)
        VALUES (?, ?, ?, 1)
        ON CONFLICT(displayTypeID, grandPrix)
        DO UPDATE SET views = views + 1;
    ''', [graph_type, None, grand_prix])
    db.get_db().commit()

    #based on the selected graph type and Grand Prix, generate the appropriate graph
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

    else:
        return "Graph type not supported", 400

    #serve the image data
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
def get_most_viewed_graphs(number_of_recomendations):
    query = '''
    SELECT displayTypeID, grandPrix, SUM(views) AS total_views
    FROM displayData
    GROUP BY displayTypeID, grandPrix
    ORDER BY total_views DESC
    LIMIT ?
    '''
    result = db.query_db(query, [number_of_recomendations])
    return result if result else []

def get_graph_recommendations(number_of_recomendations):
    most_viewed_graphs = get_most_viewed_graphs(number_of_recomendations)
    recommendations = []

    for graph in most_viewed_graphs:
        recommendations.append({
            "graph_type": graph['displayTypeID'],
            "grand_prix": graph['grandPrix']
        })
    
    return recommendations

def getSignedIn():
    try:
        userloggedin = session['email']
        return True
    except:
        return False
    
@app.route('/send-newsletter')
def send_newsletter():
    try:
        #get graphs
        grand_prix = f1_data.get_last_grand_prix()
        position_change_graph = f1_data.get_positions_change_during_a_race(grand_prix)
        quali_results_graph = f1_data.get_quali_results_overview(grand_prix)
        team_pace_comparison_graph = f1_data.get_team_pace_comparison(grand_prix)

        #list of graphs to be attached
        graphs = [
            ("Position Change During Race", position_change_graph),
            ("Qualifying Results Overview", quali_results_graph),
            ("Team Pace Comparison", team_pace_comparison_graph)
        ]
        
        #get newsletter subscribers
        subscribers = db.query_db("SELECT firstName, email FROM users WHERE newsletter = 1")

        #send to all subscribers
        for subscriber in subscribers:
        
            email = subscriber['email']
            msg = Message("F1 Race Update - Newsletter", recipients=[email])
            msg.body = "Dear Subscriber,\n\nHere is your latest F1 race update, with graphs for the latest race."

            #attach the graphs
            for graph_title, graph_data in graphs:
                graph_file = BytesIO(graph_data.read())  # Assuming graph_data is a file-like object
                msg.attach(f"{graph_title}.png", "image/png", graph_file.read())
                
            mail.send(msg)

        return "Newsletter sent successfully!", 200

    except Exception as e:
        return f"Error sending newsletter: {e}", 500

def get_payload():

    payload = {
        'qualiresults': qualiResults(), # api
        'driverrankingsrace': driverRankingsRace()[0], # db / ML
        'upcominggrandprixlist': getUpcomingGrandPrixInfo(), # api 
        'practiseresults' : practiseResults(), # api
        'predictionaccuracy' : str(driverRankingsRace()[1]) + "%", # ML note that prediction accuracy is dRR[1] 
        'signedin' : getSignedIn(), #session
        'graphtypes': getGraphTypes(), #f1data
        'grandprixlist': f1_data.get_events(),  # Grand Prix events from f1data.py
        'isadmin' : get_admin(), 
        'graph_recommendations' : get_graph_recommendations(3)
    }

    return payload

@app.route('/')
def home():

    payload = get_payload()

    return render_template('index.html', data=payload)

@app.route('/static/<path:path>')
def serve_static_files(path):
    return send_from_directory('static', path)