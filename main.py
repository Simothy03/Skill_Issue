import os
import psycopg2
from flask import Flask, request, jsonify, redirect, url_for, session, g
from flask_cors import CORS
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from dotenv import load_dotenv
from google_auth_oauthlib.flow import Flow
import requests
import json
import traceback
import chess.engine

try:
    from backend import matches
    from backend import analysis
except ImportError as e:
    print(f"Error importing from 'backend' module: {e}")
    matches = None
    analysis = None

# --- App Initialization ---
load_dotenv()
app = Flask(__name__)
CORS(app, supports_credentials=True)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY')
DATABASE_URL = os.environ.get('DATABASE_URL')
STOCKFISH_PATH = os.environ.get('STOCKFISH_PATH')
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:5173')

if not app.config['SECRET_KEY'] or not DATABASE_URL or not STOCKFISH_PATH:
    print("Error: FLASK_SECRET_KEY, DATABASE_URL, or STOCKFISH_PATH not found.")

# --- Database and Engine Connection Management ---

def get_db():
    """Opens a new database connection if there is none yet."""
    if 'db' not in g:
        try:
            g.db = psycopg2.connect(DATABASE_URL)
        except psycopg2.Error as e:
            print(f"Error connecting to database: {e}")
            raise
    return g.db

def get_engine():
    """Opens a new Stockfish engine if there is none yet."""
    if 'engine' not in g:
        try:
            g.engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
        except Exception as e:
            print(f"Error starting Stockfish engine: {e}")
            raise
    return g.engine

@app.teardown_appcontext
def close_connections(error):
    """Closes database and engine at the end of the request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()
        
    engine = g.pop('engine', None)
    if engine is not None:
        engine.quit()

# --- User Class (to work with Flask-Login) ---
class User(UserMixin):
    def __init__(self, id, google_id, email, name, chess_com_username, created_at):
        self.id = id
        self.google_id = google_id
        self.email = email
        self.name = name
        self.chess_com_username = chess_com_username
        self.created_at = created_at

# --- Flask-Login Setup ---
login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    db_conn = get_db()
    cursor = None
    try:
        cursor = db_conn.cursor()
        cursor.execute("SELECT id, google_id, email, name, chess_com_username, created_at FROM users WHERE id = %s", (int(user_id),))
        user_data = cursor.fetchone()
        if user_data:
            return User(
                id=user_data[0], 
                google_id=user_data[1], 
                email=user_data[2], 
                name=user_data[3], 
                chess_com_username=user_data[4], 
                created_at=user_data[5]
            )
        return None
    except (psycopg2.Error, ValueError) as e:
        print(f"Error loading user {user_id}: {e}")
        return None
    finally:
        if cursor:
            cursor.close()

@login_manager.unauthorized_handler
def unauthorized():
    return jsonify({"error": "Login required"}), 401


# --- Google OAuth Setup ---
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")

if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
    print("Error: Google Client ID or Secret not found.")
    client_secrets = {}
else:
    client_secrets = {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            # "redirect_uris": ["http://localhost:5000/callback/google"],
            "javascript_origins": [FRONTEND_URL]
        }
    }
SCOPES = ['openid', 'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile']

# --- Google Login Route ---
@app.route('/login/google')
def google_login():
    if not client_secrets:
        return jsonify({"error": "Server configuration error: Google credentials missing"}), 500
    flow = Flow.from_client_config(
        client_config=client_secrets,
        scopes=SCOPES,
        redirect_uri=url_for('google_callback', _external=True)
    )
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    session['state'] = state
    return redirect(authorization_url) # <-- THIS IS THE FIX

# --- Google Callback Route ---
@app.route('/callback/google')
def google_callback():
    state = session.get('state')
    if not state or state != request.args.get('state'):
        print("Error: State mismatch.")
        return redirect(f'{FRONTEND_URL}/login?error=state_mismatch')
    if 'error' in request.args:
        print(f"User denied access: {request.args['error']}")
        return redirect(f'{FRONTEND_URL}/login?error=access_denied')
    if not client_secrets:
        print("Error: Server configuration error: Google credentials missing during callback.")
        return redirect(f'{FRONTEND_URL}/login?error=server_config')

    flow = Flow.from_client_config(
        client_config=client_secrets,
        scopes=SCOPES,
        state=state,
        redirect_uri=url_for('google_callback', _external=True)
    )

    db_conn = None
    cursor = None
    try:
        authorization_response = request.url
        flow.fetch_token(authorization_response=authorization_response)
        credentials = flow.credentials
        userinfo_response = requests.get(
            'https://openidconnect.googleapis.com/v1/userinfo',
            headers={'Authorization': f'Bearer {credentials.token}'}
        )
        userinfo_response.raise_for_status()
        user_info = userinfo_response.json()

        google_id = user_info.get('sub')
        email = user_info.get('email')
        name = user_info.get('name')
        if not google_id:
            raise ValueError("Google ID ('sub') not found in user info")

        # --- Find or Create User in Database ---
        db_conn = get_db()
        cursor = db_conn.cursor()

        cursor.execute("SELECT id, google_id, email, name, chess_com_username, created_at FROM users WHERE google_id = %s", (google_id,))
        user_data = cursor.fetchone()
        
        user = None
        if user_data:
            print(f"Found existing user: {user_data[2]}")
            cursor.execute("UPDATE users SET email = %s, name = %s WHERE google_id = %s", (email, name, google_id))
            db_conn.commit()
            user = User(
                id=user_data[0], google_id=user_data[1], email=email, name=name, 
                chess_com_username=user_data[4], created_at=user_data[5]
            )
        else:
            print(f"Creating new user for Google ID: {google_id}")
            cursor.execute(
                "INSERT INTO users (google_id, email, name) VALUES (%s, %s, %s) RETURNING id, created_at",
                (google_id, email, name)
            )
            new_user_id, new_created_at = cursor.fetchone()
            db_conn.commit()
            user = User(
                id=new_user_id, google_id=google_id, email=email, name=name, 
                chess_com_username=None, created_at=new_created_at
            )

        login_user(user, remember=True)
        session.pop('state', None)
        return redirect(f'{FRONTEND_URL}/dashboard')

    except Exception as e:
        if db_conn:
            db_conn.rollback() 
        print(f"Error during Google callback processing: {e}")
        traceback.print_exc()
        return redirect(f'{FRONTEND_URL}/login?error=oauth_processing_failed')
    finally:
        if cursor:
            cursor.close()

# --- Endpoint: Link Chess.com Account ---
@app.route('/api/user/link_chess_account', methods=['POST'])
@login_required
def link_chess_account():
    data = request.json
    chess_username = data.get('username')
    if not chess_username:
        return jsonify({"error": "Username is required"}), 400

    db_conn = get_db()
    cursor = None
    try:
        cursor = db_conn.cursor()
        cursor.execute("UPDATE users SET chess_com_username = %s WHERE id = %s", (chess_username, current_user.id))
        db_conn.commit()
        
        current_user.chess_com_username = chess_username
        
        return jsonify({"success": True, "message": "Account linked successfully", "username": chess_username}), 200
    except psycopg2.Error as e:
        db_conn.rollback()
        if e.pgcode == '23505':
            return jsonify({"error": "That Chess.com username is already linked to another account."}), 409
        print(f"Database error linking account: {e}")
        return jsonify({"error": "Database error"}), 500
    except Exception as e:
        db_conn.rollback()
        print(f"Error linking account: {e}")
        return jsonify({"error": "An internal server error occurred"}), 500
    finally:
        if cursor:
            cursor.close()

# --- Login Status Check ---
@app.route('/api/user/status')
def user_status():
    if current_user.is_authenticated:
        return jsonify({
            "logged_in": True,
            "user_info": {
                "id": current_user.id,
                "name": current_user.name,
                "email": current_user.email,
                "google_id": current_user.google_id,
                "chess_com_username": current_user.chess_com_username 
            }
        }) 
    else:
        return jsonify({"logged_in": False})

# --- Logout Route ---
@app.route('/logout')
@login_required
def logout():
    logout_user()
    print("User logged out.")
    return redirect(FRONTEND_URL)


# --- *** NEW ANALYZE ENDPOINT *** ---
@app.route("/api/analyze", methods=['POST'])
@login_required
def analyze_games():
    if not matches or not analysis:
        return jsonify({"error": "Analysis modules not loaded"}), 500

    # 1. Get user info from the session
    chess_username = current_user.chess_com_username
    user_id = current_user.id
    
    if not chess_username:
        return jsonify({"error": "No Chess.com account is linked."}), 400

    print(f"--- Analysis Request Started for user {user_id} ({chess_username}) ---")

    try:
        db_conn = get_db()
        engine = get_engine()

        print(f"Running ingest for {chess_username}...")
        # November 2025 for now
        matches.process_user_games(chess_username, 2025, 11, engine, db_conn)
        print("Ingest complete.")

        # 4. --- RUN STEP 2: ANALYZE ---
        print(f"Running analysis pipeline for user {user_id}...")
        analysis_results = analysis.main_analysis_pipeline(user_id, db_conn)
        print("Analysis complete.")
        
        # 5. --- COMMIT TRANSACTION ---
        db_conn.commit()
        print("--- Analysis Request Finished Successfully ---")
        
        return jsonify({
            "success": True, 
            "message": "Analysis complete!",
            "results": analysis_results
        }), 200

    except Exception as e:
        db_conn = g.get('db', None)
        if db_conn:
            db_conn.rollback() 
            
        print(f"Error during analysis for {chess_username}: {e}")
        traceback.print_exc()
        return jsonify({"error": "An internal server error occurred during analysis."}), 500
    

# --- Run the server ---
if __name__ == "__main__":
    app.run(port=5000, debug=True)