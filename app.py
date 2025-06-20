from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3, os
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date, datetime
import calendar
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev_secret_key')

db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'gym.db')

def get_db_connection():
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('DROP TABLE IF EXISTS workouts')
    conn.execute('''
        CREATE TABLE workouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            exercise TEXT NOT NULL,
            weight REAL NOT NULL,
            reps INTEGER NOT NULL,
            sets INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            UNIQUE(user_id, date),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapped

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('menu'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            today_str = date.today().isoformat()
            conn = get_db_connection()
            try:
                conn.execute('INSERT INTO attendance (user_id, date) VALUES (?, ?)', (user['id'], today_str))
                conn.commit()
            except sqlite3.IntegrityError:
                pass
            conn.close()
            return redirect(url_for('menu'))
        return 'ユーザー名またはパスワードが正しくありません'
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, generate_password_hash(password)))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return 'ユーザー名は既に存在します'
        conn.close()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/menu')
@login_required
def menu():
    return render_template('menu.html')

@app.route('/record', methods=['GET', 'POST'])
@login_required
def index():
    user_id = session['user_id']
    if request.method == 'POST':
        date_str = request.form['date']
        exercise = request.form['exercise']
        weight = request.form['weight']
        reps = request.form['reps']
        sets_ = request.form['sets']
        conn = get_db_connection()
        conn.execute('INSERT INTO workouts (user_id, date, exercise, weight, reps, sets) VALUES (?, ?, ?, ?, ?, ?)', (user_id, date_str, exercise, weight, reps, sets_))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    conn = get_db_connection()
    workouts = conn.execute('SELECT * FROM workouts WHERE user_id = ? ORDER BY date DESC', (user_id,)).fetchall()
    conn.close()
    return render_template('index.html', workouts=workouts, now=datetime.now())

@app.route('/monthly')
@login_required
def monthly():
    user_id = session['user_id']
    now = datetime.now()
    month_prefix = now.strftime('%Y-%m')
    conn = get_db_connection()
    workouts = conn.execute('SELECT * FROM workouts WHERE user_id = ? AND date LIKE ? ORDER BY date DESC', (user_id, f'{month_prefix}%')).fetchall()
    conn.close()
    return render_template('monthly.html', workouts=workouts, now=now)

@app.route('/attendance')
@login_required
def attendance():
    user_id = session['user_id']
    conn = get_db_connection()
    rows = conn.execute('SELECT date FROM attendance WHERE user_id = ?', (user_id,)).fetchall()
    conn.close()
    dates = [r['date'] for r in rows]
    today = date.today()
    year = today.year
    month = today.month
    cal = calendar.monthcalendar(year, month)
    return render_template('attendance.html', dates=dates, cal=cal, year=year, month=month)

if __name__ == '__main__':
    app.run(debug=True)