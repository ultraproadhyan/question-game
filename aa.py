import os
import sqlite3
import csv
from datetime import datetime
from flask import Flask, request, render_template_string, redirect, session
from waitress import serve

# ===== CONFIGURATION =====
CONFIG_DIR = "config"
ADMIN_FILE = os.path.join(CONFIG_DIR, "admin.txt")
CODES_FILE = os.path.join(CONFIG_DIR, "codes.txt")
QUESTIONS_FILE = os.path.join(CONFIG_DIR, "questions.txt")
DATABASE_FILE = "database.db"
WHATSAPP_NUMBER = "917694993234"

# ===== INITIALIZATION =====
def create_config_files():
    """Create configuration files if they don't exist"""
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR)
    if not os.path.exists(ADMIN_FILE):
        with open(ADMIN_FILE, "w") as f:
            f.write("admin123")
    if not os.path.exists(CODES_FILE):
        with open(CODES_FILE, "w") as f:
            f.write("TESTCODE1\nTESTCODE2")
    if not os.path.exists(QUESTIONS_FILE):
        with open(QUESTIONS_FILE, "w") as f:
            f.write("What is 2+2?|3|4|5|4\nWhich is a fruit?|Carrot|Apple|Potato|Apple")

app = Flask(__name__)
app.secret_key = os.urandom(24)

# ===== DATABASE FUNCTIONS =====
def get_db_connection():
    """Get database connection with row factory"""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database tables"""
    conn = None
    try:
        conn = get_db_connection()
        conn.execute('''CREATE TABLE IF NOT EXISTS tests
                     (id INTEGER PRIMARY KEY, name TEXT NOT NULL,
                     phone TEXT NOT NULL, age INTEGER NOT NULL,
                     score INTEGER DEFAULT 0, right_ans INTEGER DEFAULT 0,
                     wrong_ans INTEGER DEFAULT 0, start_time TEXT NOT NULL,
                     end_time TEXT, duration REAL, ip TEXT NOT NULL,
                     code TEXT NOT NULL)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS answers
                     (id INTEGER PRIMARY KEY, test_id INTEGER NOT NULL,
                     question TEXT NOT NULL, answer TEXT NOT NULL,
                     is_correct INTEGER NOT NULL, time_taken REAL NOT NULL,
                     FOREIGN KEY(test_id) REFERENCES tests(id))''')
        conn.commit()
    except Exception as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

# ===== HELPER FUNCTIONS =====
def get_current_time():
    """Get current timestamp with milliseconds"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

def calculate_duration(start, end):
    """Calculate duration between two timestamps"""
    try:
        start_dt = datetime.strptime(str(start), "%Y-%m-%d %H:%M:%S.%f")
        end_dt = datetime.strptime(str(end), "%Y-%m-%d %H:%M:%S.%f")
        return round((end_dt - start_dt).total_seconds(), 2)
    except Exception as e:
        print(f"Duration calculation error: {e}")
        return 0.0

def get_admin_password():
    """Get admin password from config file"""
    try:
        with open(ADMIN_FILE) as f:
            return f.read().strip()
    except:
        return "admin123"

def get_valid_codes():
    """Get valid test codes from config file"""
    try:
        with open(CODES_FILE) as f:
            return [line.strip() for line in f if line.strip()]
    except:
        return ["TESTCODE1", "TESTCODE2"]

def get_questions():
    """Get questions from config file"""
    try:
        with open(QUESTIONS_FILE) as f:
            return [line.strip().split("|") for line in f if line.strip()]
    except:
        return [
            ["What is 2+2?", "3", "4", "5", "4"],
            ["Which is a fruit?", "Carrot", "Apple", "Potato", "Apple"]
        ]

def add_question(question, option1, option2, option3, correct):
    """Add new question to the question bank"""
    try:
        with open(QUESTIONS_FILE, "a") as f:
            f.write(f"\n{question}|{option1}|{option2}|{option3}|{correct}")
        return True
    except:
        return False

def format_test_date(timestamp):
    """Format timestamp for display"""
    try:
        dt = datetime.strptime(str(timestamp), "%Y-%m-%d %H:%M:%S.%f")
        return dt.strftime("%d %b %Y, %I:%M %p")
    except:
        return timestamp

# ===== HTML TEMPLATES =====
HOME_HTML = '''<!DOCTYPE html><html><head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>body { font-family: Arial; max-width: 600px; margin: 0 auto; padding: 20px; }
    .btn { display: block; width: 100%; padding: 12px; margin: 10px 0; 
           background: #4CAF50; color: white; border: none; border-radius: 5px; 
           text-align: center; font-size: 16px; }
    input { width: 100%; padding: 12px; margin: 8px 0; box-sizing: border-box; }
    .container { background: #f9f9f9; padding: 20px; border-radius: 10px; }
    .error { color: red; margin: 10px 0; }
    </style></head>
<body><div class="container">
    <h1 style="text-align: center;">📝 Online Test</h1>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    <a href="/get_code" class="btn">Get Code via WhatsApp</a>
    <form action="/start_test" method="POST">
        <input type="text" name="code" placeholder="Enter Test Code" required maxlength="20">
        <button type="submit" class="btn">Start Test</button>
    </form>
</div></body></html>'''

TEST_FORM_HTML = '''<!DOCTYPE html><html><head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>body { font-family: Arial; max-width: 600px; margin: 0 auto; padding: 20px; }
    input, button { width: 100%; padding: 12px; margin: 8px 0; box-sizing: border-box; }
    .btn { background: #4CAF50; color: white; border: none; border-radius: 5px; }
    .error { color: red; margin: 10px 0; }
    </style></head>
<body>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    <form action="/submit_test" method="POST">
        <input type="text" name="name" placeholder="Name" required maxlength="50"><br>
        <input type="tel" name="phone" placeholder="Phone" required maxlength="15"><br>
        <input type="number" name="age" placeholder="Age" required min="10" max="100"><br>
        <input type="hidden" name="code" value="{{ code }}">
        <button type="submit" class="btn">Submit</button>
    </form>
</body></html>'''

QUESTION_HTML = '''<!DOCTYPE html><html><head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>body { font-family: Arial; max-width: 600px; margin: 0 auto; padding: 20px; }
    .btn { display: block; width: 100%; padding: 12px; margin: 5px 0; 
           background: #f0f0f0; border: 1px solid #ddd; text-align: left; }
    .btn:hover { background: #e0e0e0; }
    #timer { position: fixed; top: 10px; right: 10px; background: #333; color: white; padding: 5px 10px; border-radius: 5px; }
    .progress { margin: 10px 0; height: 5px; background: #ddd; }
    .progress-bar { height: 100%; background: #4CAF50; }
    </style></head>
<body>
    <div id="timer">Time: 00:00</div>
    <div class="progress">
        <div class="progress-bar" style="width: {{ (qno/total)*100 }}%"></div>
    </div>
    <h3>Question {{ qno }}/{{ total }}: {{ question }}</h3>
    <form action="/submit_answer" method="POST">
        <input type="hidden" name="test_id" value="{{ test_id }}">
        <input type="hidden" name="qno" value="{{ qno }}">
        {% for option in options %}
        <button type="submit" name="answer" value="{{ option }}" class="btn">{{ option }}</button>
        {% endfor %}
    </form>
    <script>
        let startTime = Date.now();
        function updateTimer() {
            const elapsed = Math.floor((Date.now() - startTime)/1000);
            const mins = Math.floor(elapsed/60).toString().padStart(2,'0');
            const secs = (elapsed % 60).toString().padStart(2,'0');
            document.getElementById('timer').textContent = `Time: ${mins}:${secs}`;
        }
        setInterval(updateTimer, 1000);
    </script>
</body></html>'''

RESULT_HTML = '''<!DOCTYPE html><html><head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>body { font-family: Arial; max-width: 600px; margin: 0 auto; padding: 20px; }
    .result-card { background: white; padding: 25px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
    .score { font-size: 28px; font-weight: bold; color: #4CAF50; text-align: center; margin: 15px 0; }
    .stat-row { display: flex; justify-content: space-between; margin: 10px 0; padding: 10px; background: #f9f9f9; border-radius: 5px; }
    .home-btn { display: block; width: 100%; padding: 12px; margin-top: 20px; 
                background: #2196F3; color: white; text-align: center; 
                border: none; border-radius: 5px; font-size: 18px; text-decoration: none; }
    @media (max-width: 480px) {
        body { padding: 10px; }
        .result-card { padding: 15px; }
    }
    </style></head>
<body>
    <div class="result-card">
        <h1 style="text-align: center;">Test Completed! 🎉</h1>
        <div class="score">{{ score }}/{{ total }}</div>
        
        <div class="stat-row">
            <span>✅ Correct Answers:</span>
            <span>{{ right }}</span>
        </div>
        <div class="stat-row">
            <span>❌ Wrong Answers:</span>
            <span>{{ wrong }}</span>
        </div>
        <div class="stat-row">
            <span>⏱️ Time Taken:</span>
            <span>{{ duration }} seconds</span>
        </div>
        <div class="stat-row">
            <span>📅 Test Date:</span>
            <span>{{ test_date }}</span>
        </div>
        
        <a href="/" class="home-btn">Go to Home</a>
    </div>
</body></html>'''

ADMIN_HTML = '''<!DOCTYPE html><html><head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>body { font-family: Arial; margin: 0 auto; padding: 20px; max-width: 1200px; }
    table { width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 14px; }
    th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
    th { background-color: #4CAF50; color: white; position: sticky; top: 0; }
    tr:nth-child(even) { background-color: #f2f2f2; }
    tr:hover { background-color: #e6e6e6; }
    .export-btn { background: #2196F3; color: white; padding: 10px; border: none; border-radius: 5px; margin: 10px 0; }
    .admin-section { margin: 20px 0; padding: 20px; background: #f9f9f9; border-radius: 5px; }
    </style></head>
<body>
    <h1>🔒 Admin Panel</h1>
    
    <div class="admin-section">
        <h2>Test Results</h2>
        <div style="overflow-x: auto;">
            {{ table|safe }}
        </div>
        <a href="/export_csv?password={{ password }}" class="export-btn">Export CSV</a>
    </div>
    
    <div class="admin-section">
        <h2>Manage Questions</h2>
        <form action="/add_question" method="POST">
            <input type="hidden" name="password" value="{{ password }}">
            <input type="text" name="question" placeholder="Question" required style="width: 100%; margin-bottom: 10px;"><br>
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;">
                <input type="text" name="option1" placeholder="Option 1" required>
                <input type="text" name="option2" placeholder="Option 2" required>
                <input type="text" name="option3" placeholder="Option 3" required>
            </div>
            <input type="text" name="correct" placeholder="Correct Answer" required style="margin-top: 10px; width: 100%;">
            <button type="submit" class="export-btn" style="margin-top: 10px;">Add Question</button>
        </form>
    </div>
</body></html>'''

# ===== ROUTES =====
@app.route("/")
def home():
    error = request.args.get("error")
    return render_template_string(HOME_HTML, error=error)

@app.route("/get_code")
def get_code():
    return redirect(f"https://wa.me/{WHATSAPP_NUMBER}?text=Send%20Test%20Code")

@app.route("/start_test", methods=["POST"])
def start_test():
    try:
        code = request.form.get("code", "").strip()
        if not code or code not in get_valid_codes():
            return redirect("/?error=Invalid+Test+Code")
        return render_template_string(TEST_FORM_HTML, code=code)
    except Exception as e:
        print(f"Error in start_test: {e}")
        return redirect("/?error=System+Error")

@app.route("/submit_test", methods=["POST"])
def submit_test():
    conn = None
    try:
        # Validate inputs
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        age = request.form.get("age", "").strip()
        code = request.form.get("code", "").strip()
        
        if not all([name, phone, age, code]) or not age.isdigit():
            return render_template_string(TEST_FORM_HTML, code=code, error="Invalid Input")
        
        age = int(age)
        if age < 10 or age > 100:
            return render_template_string(TEST_FORM_HTML, code=code, error="Invalid Age")
        
        # Save to database
        conn = get_db_connection()
        cursor = conn.cursor()
        start_time = get_current_time()
        
        cursor.execute('''INSERT INTO tests 
                     (name, phone, age, score, right_ans, wrong_ans, 
                     start_time, ip, code) 
                     VALUES (?, ?, ?, 0, 0, 0, ?, ?, ?)''',
                  (name, phone, age, start_time, request.remote_addr, code))
        
        test_id = cursor.lastrowid
        conn.commit()
        session['start_time'] = start_time
        return redirect(f"/show_question?test_id={test_id}&qno=1")
    except Exception as e:
        print(f"Error in submit_test: {e}")
        return redirect("/?error=Submission+Failed")
    finally:
        if conn:
            conn.close()

@app.route("/show_question")
def show_question():
    try:
        test_id = request.args.get("test_id")
        qno = int(request.args.get("qno", 1))
        
        if not test_id or not qno:
            return redirect("/?error=Invalid+Test+Session")
        
        questions = get_questions()
        if qno > len(questions):
            return redirect(f"/result?test_id={test_id}")
        
        question_data = questions[qno-1]
        if len(question_data) < 5:
            raise ValueError("Invalid question format")
        
        return render_template_string(QUESTION_HTML, 
            qno=qno, total=len(questions), question=question_data[0],
            options=question_data[1:-1], test_id=test_id)
    except Exception as e:
        print(f"Error in show_question: {e}")
        return redirect("/?error=Question+Loading+Failed")

@app.route("/submit_answer", methods=["POST"])
def submit_answer():
    try:
        test_id = request.form.get("test_id")
        qno = int(request.form.get("qno", 1))
        answer = request.form.get("answer", "").strip()
        
        if not all([test_id, qno, answer]):
            return redirect("/?error=Invalid+Answer+Submission")
        
        questions = get_questions()
        if qno > len(questions):
            return redirect(f"/result?test_id={test_id}")
        
        question_data = questions[qno-1]
        correct_answer = question_data[-1]
        answer_time = get_current_time()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Calculate time taken for this question
        if qno == 1:
            start_time = session.get('start_time')
        else:
            start_time_row = cursor.execute('''SELECT MAX(time_taken) FROM answers 
                                         WHERE test_id = ?''', (test_id,)).fetchone()
            start_time = start_time_row[0] if start_time_row else session.get('start_time')
        
        time_taken = calculate_duration(start_time, answer_time)
        
        # Record answer
        cursor.execute('''INSERT INTO answers 
                     (test_id, question, answer, is_correct, time_taken) 
                     VALUES (?, ?, ?, ?, ?)''',
                  (test_id, question_data[0], answer, 
                   1 if answer == correct_answer else 0, time_taken))
        
        # Update score
        if answer == correct_answer:
            cursor.execute('''UPDATE tests SET score = score + 1, right_ans = right_ans + 1 
                         WHERE id = ?''', (test_id,))
        else:
            cursor.execute('''UPDATE tests SET wrong_ans = wrong_ans + 1 
                         WHERE id = ?''', (test_id,))
        
        conn.commit()
        return redirect(f"/show_question?test_id={test_id}&qno={qno+1}")
    except Exception as e:
        print(f"Error in submit_answer: {e}")
        return redirect("/?error=Answer+Submission+Failed")
    finally:
        if conn:
            conn.close()

@app.route("/result")
def result():
    conn = None
    try:
        test_id = request.args.get("test_id")
        if not test_id:
            return redirect("/?error=Invalid+Test+ID")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Update end time and duration
        end_time = get_current_time()
        test_data = cursor.execute("SELECT * FROM tests WHERE id = ?", (test_id,)).fetchone()
        
        if not test_data:
            return redirect("/?error=Test+Not+Found")
        
        start_time = test_data['start_time']
        duration = calculate_duration(start_time, end_time)
        
        cursor.execute('''UPDATE tests SET end_time = ?, duration = ? 
                     WHERE id = ?''', (end_time, duration, test_id))
        conn.commit()
        
        # Format test date nicely
        test_date = format_test_date(test_data['start_time'])
        
        return render_template_string(RESULT_HTML, 
            score=test_data['score'],
            total=len(get_questions()),
            right=test_data['right_ans'],
            wrong=test_data['wrong_ans'],
            duration=duration,
            test_date=test_date)
    except Exception as e:
        print(f"Error in result: {e}")
        return redirect("/?error=Result+Processing+Failed")
    finally:
        if conn:
            conn.close()

@app.route("/admin")
def admin():
    try:
        password = request.args.get("password")
        if not password or password != get_admin_password():
            return "Access Denied!"
        
        conn = get_db_connection()
        cursor = conn.cursor()
        tests = cursor.execute("SELECT * FROM tests ORDER BY start_time DESC").fetchall()
        questions = get_questions()
        
        table = """<table>
            <tr>
                <th>ID</th>
                <th>Name</th>
                <th>Phone</th>
                <th>Age</th>
                <th>Score</th>
                <th>Right</th>
                <th>Wrong</th>
                <th>Duration (s)</th>
                <th>Start Time</th>
                <th>Code</th>
            </tr>"""
        
        for test in tests:
            table += f"""
            <tr>
                <td>{test['id']}</td>
                <td>{test['name']}</td>
                <td>{test['phone']}</td>
                <td>{test['age']}</td>
                <td>{test['score']}/{len(questions)}</td>
                <td>{test['right_ans']}</td>
                <td>{test['wrong_ans']}</td>
                <td>{test['duration'] or 'N/A'}</td>
                <td>{test['start_time']}</td>
                <td>{test['code']}</td>
            </tr>"""
        
        table += "</table>"
        
        return render_template_string(ADMIN_HTML, table=table, password=password)
    except Exception as e:
        print(f"Error in admin: {e}")
        return "System Error", 500
    finally:
        if conn:
            conn.close()

@app.route("/add_question", methods=["POST"])
def add_question_route():
    try:
        password = request.form.get("password")
        if not password or password != get_admin_password():
            return "Access Denied!"
        
        question = request.form.get("question", "").strip()
        option1 = request.form.get("option1", "").strip()
        option2 = request.form.get("option2", "").strip()
        option3 = request.form.get("option3", "").strip()
        correct = request.form.get("correct", "").strip()
        
        if not all([question, option1, option2, option3, correct]):
            return "All fields are required", 400
        
        if add_question(question, option1, option2, option3, correct):
            return redirect(f"/admin?password={password}")
        else:
            return "Failed to add question", 500
    except Exception as e:
        print(f"Error in add_question: {e}")
        return "System Error", 500

@app.route("/export_csv")
def export_csv():
    conn = None
    try:
        password = request.args.get("password")
        if not password or password != get_admin_password():
            return "Access Denied!"
        
        conn = get_db_connection()
        cursor = conn.cursor()
        tests = cursor.execute("SELECT * FROM tests").fetchall()
        
        # Create CSV in memory
        output = []
        output.append("ID,Name,Phone,Age,Score,Right Answers,Wrong Answers,Duration (s),Start Time,End Time,IP,Code")
        
        for test in tests:
            output.append(f"{test['id']},{test['name']},{test['phone']},{test['age']},"
                         f"{test['score']},{test['right_ans']},{test['wrong_ans']},"
                         f"{test['duration'] or ''},{test['start_time']},"
                         f"{test['end_time'] or ''},{test['ip']},{test['code']}")
        
        # Return as downloadable file
        response = app.response_class(
            response="\n".join(output),
            mimetype="text/csv",
            headers={"Content-disposition": "attachment; filename=test_results.csv"}
        )
        return response
    except Exception as e:
        print(f"Download error: {e}")
        return "Error generating download", 500
    finally:
        if conn:
            conn.close()

# ===== ERROR HANDLERS =====
@app.errorhandler(403)
def forbidden(e):
    return render_template_string("<h1>403 - Forbidden</h1><p>You don't have permission to access this page.</p>"), 403

@app.errorhandler(404)
def page_not_found(e):
    return render_template_string("<h1>404 - Page Not Found</h1><p>Return to <a href='/'>home</a></p>"), 404

@app.errorhandler(500)
def internal_error(e):
    return render_template_string("<h1>500 - Server Error</h1><p>Return to <a href='/'>home</a></p>"), 500

# ===== START APP =====
if __name__ == "__main__":
    create_config_files()
    init_db()
    
    # For development
    app.run(debug=True, host='0.0.0.0', port=5000)
    
    # For production (uncomment when deploying):
    # serve(app, host='0.0.0.0', port=5000)
