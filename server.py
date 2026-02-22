from flask import Flask, request, jsonify, send_from_directory
import sqlite3
import os
import re
from datetime import datetime, timedelta
import jwt
from werkzeug.security import generate_password_hash, check_password_hash
import time

app = Flask(__name__)
app.secret_key = r"G%fyyf&NKjt538Frjf\oo3Fek*f/ooS3)hmfcqzGju[b]v_v-3=!"

DB_FILE = "database.db"

app.config['JWT_SECRET'] = app.secret_key
app.config['JWT_ALGORITHM'] = "HS256"
app.config['JWT_EXP_DELTA_SECONDS'] = int(os.environ.get("JWT_EXP_DELTA_SECONDS", 3600))  

def init_db():
    if not os.path.exists(DB_FILE):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password_hash TEXT,
                is_admin INTEGER DEFAULT 0,
                gov_id INTEGER UNIQUE,
                first_name TEXT,
                second_name TEXT
            )
        """)
        conn.commit()
        conn.close()
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)", 
                  ("admin", generate_password_hash("Admin@123"), 1))
        conn.commit()
        conn.close()

def is_valid_password(password: str) -> bool:
    return True # Placeholder to disable password validation
    if not password or len(password) < 6:
        return False
    pattern = r'^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[^A-Za-z0-9])[A-Za-z0-9!"#$%&\'()*+,\-./:;<=>?@\[\]^_`{|}~]+$'
    return re.match(pattern, password) is not None

def create_token(user_id: int, username: str):
    now = datetime.utcnow()
    exp = now + timedelta(seconds=app.config['JWT_EXP_DELTA_SECONDS'])
    payload = {
        "sub": username,
        "user_id": user_id,
        "iat": now,
        "exp": exp
    }
    token = jwt.encode(payload, app.config['JWT_SECRET'], algorithm=app.config['JWT_ALGORITHM'])
    if isinstance(token, bytes):
        token = token.decode('utf-8')
    return token

def verify_token(token: str):
    try:
        payload = jwt.decode(token, app.config['JWT_SECRET'], algorithms=[app.config['JWT_ALGORITHM']])
        return True, payload
    except jwt.ExpiredSignatureError:
        return False, {"error": "Token expired"}
    except jwt.InvalidTokenError:
        return False, {"error": "Invalid token"}

def get_token_from_header_or_cookie():
    auth = request.headers.get("Authorization", "")
    if auth and auth.startswith("Bearer "):
        return auth.split(" ", 1)[1].strip()
    token = request.cookies.get("token")
    if token:
        return token
    return None


def check_auth():
    """Check if user is authenticated and exists in DB. Returns (is_valid, user_id, username, is_admin) or (False, None, None, False)"""
    token = get_token_from_header_or_cookie()
    if not token:
        return False, None, None, False
    valid, payload = verify_token(token)
    if not valid:
        return False, None, None, False
    
    user_id = payload.get("user_id")
    username = payload.get("sub")

    # Verify user still exists in database
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT is_admin FROM users WHERE id=? AND username=?", (user_id, username))
    row = c.fetchone()
    conn.close()
    
    if not row:
        return False, None, None, False
    
    is_admin = row[0] if row else 0
    return True, user_id, username, bool(is_admin)

# --- USER API ---
@app.route("/api/register", methods=["POST"])
def register():
    data = request.json or {}
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"success": False, "message": "Username and password are required."}), 400

    if not is_valid_password(password):
        return jsonify({"success": False, "message": "Password must contain at least one capital letter, one digit, one special symbol, and contain only latin letters/digits/punctuation, min length 6."})

    password_hash = generate_password_hash(password)

    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)", (username, password_hash, 0))
        conn.commit()
        user_id = c.lastrowid
        conn.close()

        token = create_token(user_id, username)
        return jsonify({"success": True, "message": "Registration successful!", "token": token})
    except sqlite3.IntegrityError:
        return jsonify({"success": False, "message": "There is already an account with this username."})

@app.route("/api/login", methods=["POST"])
def login():
    data = request.json or {}
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"success": False, "message": "Username and password are required."}), 400

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, password_hash FROM users WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()

    if row and check_password_hash(row[1], password):
        user_id = row[0]
        token = create_token(user_id, username)
        resp = jsonify({"success": True, "message": "Login successful!", "token": token})
        max_age = app.config['JWT_EXP_DELTA_SECONDS']
        resp.set_cookie("token", token, max_age=max_age, httponly=True, samesite='Lax')  # secure=True в prod
        return resp 
    else:
        return jsonify({"success": False, "message": "Wrong username or password."})

@app.route("/api/logout", methods=["POST"])
def logout():
    resp = jsonify({"success": True, "message": "Logged out on server (client should remove token)."})
    resp.set_cookie("token", "", max_age=0, httponly=True, samesite='Lax')
    return resp


@app.route("/api/me", methods=["GET"])
def me():
    valid, user_id, username, is_admin = check_auth()
    if not valid:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    return jsonify({"success": True, "user_id": user_id, "username": username, "is_admin": is_admin})

# --- ADMIN API ---
@app.route("/api/admin/users", methods=["GET"])
def admin_get_users():
    valid, user_id, username, is_admin = check_auth()
    if not valid or not is_admin:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, username, is_admin FROM users")
    users = [{"id": row[0], "username": row[1], "is_admin": bool(row[2])} for row in c.fetchall()]
    conn.close()
    
    return jsonify({"success": True, "users": users})

@app.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
def admin_delete_user(user_id):
    valid, auth_user_id, username, is_admin = check_auth()
    if not valid or not is_admin and user_id != auth_user_id:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()
    
    return jsonify({"success": True, "message": "User deleted successfully"})

@app.route("/api/admin/users/<int:user_id>/admin", methods=["PUT"])
def admin_toggle_admin(user_id):
    valid, auth_user_id, username, is_admin = check_auth()
    if not valid or not is_admin:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    data = request.json or {}
    is_admin_flag = data.get("is_admin", 0)
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET is_admin=? WHERE id=?", (int(is_admin_flag), user_id))
    conn.commit()
    conn.close()
    
    return jsonify({"success": True, "message": "Admin status updated"})

@app.route("/api/admin/users/<int:user_id>/password", methods=["PUT"])
def admin_edit_password(user_id):
    valid, auth_user_id, username, is_admin = check_auth()
    if not valid or not is_admin and user_id != auth_user_id:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    data = request.json or {}
    new_password = data.get("password")
    
    if not new_password:
        return jsonify({"success": False, "message": "Password is required"}), 400
    
    password_hash = generate_password_hash(new_password)
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET password_hash=? WHERE id=?", (password_hash, user_id))
    conn.commit()
    conn.close()
    
    return jsonify({"success": True, "message": "Password updated successfully"})

# --- PAGES ---
@app.route("/")
def index():
    valid, user_id, username, is_admin = check_auth()
    if not valid:
        return send_from_directory("templates", "login.html")
    if is_admin:
        return send_from_directory("templates", "admin.html")
    return send_from_directory("templates", "index.html")

@app.route("/login")
def login_page():
    return send_from_directory("templates", "login.html")

@app.route("/register")
def register_page():
    return send_from_directory("templates", "register.html")

@app.route("/admin")
def admin_page():
    valid, user_id, username, is_admin = check_auth()
    if not valid or not is_admin:
        return send_from_directory("templates", "login.html")
    return send_from_directory("templates", "admin.html")

@app.route("/<path:path>")
def static_files(path):
    return send_from_directory("templates", path)

if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=8080, debug=True)