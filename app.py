import os
import requests
import logging
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chatbot.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db = SQLAlchemy(app)

# Define User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(15), unique=True, nullable=False)
    chats = db.relationship('Chat', backref='user', lazy=True)

# Define Chat model
class Chat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user_message = db.Column(db.Text, nullable=False)
    bot_response = db.Column(db.Text, nullable=False)

# Create database tables
with app.app_context():
    db.create_all()

# Load school info
SCHOOL_INFO_FILE = "school_info.txt"
if os.path.exists(SCHOOL_INFO_FILE):
    with open(SCHOOL_INFO_FILE, "r") as file:
        school_info = file.read()
else:
    school_info = "School information not available."

# Replace with your actual Groq API key
GROQ_API_KEY = "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"

app.secret_key = 'your_secret_key_here'  # Change this to a secure random value

# Admin credentials (for demo, use env vars or DB in production)
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD_HASH = generate_password_hash('admin123')

@app.route("/register", methods=["POST"])
def register_user():
    data = request.json
    name = data.get("name")
    phone = data.get("phone")

    if not name or not phone:
        return jsonify({"error": "Name and phone are required."}), 400

    # Check if user already exists
    existing_user = User.query.filter_by(phone=phone).first()
    if existing_user:
        return jsonify({"message": "User already registered."})

    # Add new user
    new_user = User(name=name, phone=phone)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"message": "User registered successfully."})

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    user_id = data.get("user_id")
    message = data.get("message")

    # Check if user exists in the database
    user = User.query.filter_by(phone=user_id).first()  # Use phone as user_id from frontend
    if not user:
        return jsonify({"error": "User not registered."}), 400

    try:
        groq_response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama3-8b-8192",
                "messages": [
                    {
                        "role": "system",
                        "content": f"You are a helpful assistant for Premiere Academy. Only answer using the info below:\n\n{school_info}"
                    },
                    {"role": "user", "content": message}
                ],
                "temperature": 0.7,
                "max_tokens": 512
            }
        )

        logging.debug(f"Groq API response: {groq_response.text}")
        if groq_response.status_code == 200:
            response_json = groq_response.json()
            response = response_json["choices"][0]["message"]["content"]
        else:
            response = f"Error: {groq_response.status_code} - {groq_response.text}"

    except Exception as e:
        logging.error(f"Error communicating with Groq API: {e}")
        response = f"Error: {str(e)}"

    # Save chat to database
    new_chat = Chat(user_id=user.id, user_message=message, bot_response=response)
    db.session.add(new_chat)
    db.session.commit()

    return jsonify({"response": response})

@app.route("/ui")
def chat_ui():
    return render_template("chat.html")

@app.route("/users", methods=["GET"])
def users():
    users = User.query.all()
    user_data = [{"id": user.id, "name": user.name, "phone": user.phone} for user in users]
    return jsonify(user_data)

@app.route("/users_page", methods=["GET"])
def users_page():
    return render_template("users.html")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password):
            session['admin_logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error='Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('login'))

@app.route("/dashboard", methods=["GET"])
def dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))
    return render_template("dashboard.html")

@app.route("/user_chats/<int:user_id>", methods=["GET"])
def user_chats(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found."}), 404

    chats = Chat.query.filter_by(user_id=user_id).all()
    chat_data = [{"user_message": chat.user_message, "bot_response": chat.bot_response} for chat in chats]

    return jsonify({"user": {"name": user.name, "phone": user.phone}, "chats": chat_data})

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        username = request.form.get('username')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        if username != ADMIN_USERNAME:
            return render_template('reset_password.html', error='Invalid username')
        if new_password != confirm_password:
            return render_template('reset_password.html', error='Passwords do not match')
        global ADMIN_PASSWORD_HASH
        ADMIN_PASSWORD_HASH = generate_password_hash(new_password)
        flash('Password reset successful. Please log in with your new password.', 'success')
        return redirect(url_for('login'))
    return render_template('reset_password.html')

@app.route("/")
def index():
    return redirect(url_for('chat_ui'))

if __name__ == "__main__":
    app.run(debug=True)
