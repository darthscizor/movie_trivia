import os
import sqlite3
from flask import Flask, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)

DB_PATH = os.path.join(app.root_path, "movie_trivia.db")

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only")
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = os.path.join(app.root_path, "flask_session_data")
Session(app)
@app.route("/")
def index():
    session.pop("current_question_id", None)
    session.pop("question_number", None)
    session.pop("score", None)
    session.pop("used_questions", None)
    return render_template("index.html")

@app.route("/account_info", methods=["GET", "POST"])
def account_info():
    if "id" not in session:
        return redirect("/login")
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    rows = cur.execute(
        "SELECT * FROM users WHERE id = ?", (session["id"],)
    ).fetchone()
    
    return render_template("account_info.html", username=rows[1], high_score=rows[3])

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    if request.method == "POST":
        if not request.form.get("username"):
            return render_template("apology.html", message="You must provide a username")
        elif not request.form.get("password"):
            return render_template("apology.html", message="You must provide a password")
        rows = cur.execute(
            "SELECT * FROM users WHERE username = ?", (request.form.get("username"),)
        ).fetchall()
        if len(rows) != 1 or not check_password_hash(rows[0][2], request.form.get("password")):
            return render_template("apology.html", message="Incorrect username and/or password.  Please return to the previous page")
        session["id"] = rows[0][0]
        session["username"] = rows[0][1]
        return redirect("/")
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out"""
    session.clear()
    return redirect("/")

@app.route("/question", methods=["GET", "POST"])
def question():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    if "id" not in session:
        return redirect("/")
    MAX_SCORE = 10
    if "question_number" not in session:
        session["question_number"] = 1
    if "score" not in session:
        session["score"] = 0
    if "current_question_id" not in session:
        question_id = cur.execute(
            "SELECT id FROM questions ORDER BY RANDOM() LIMIT 1"
        ).fetchone()[0]
        session["current_question_id"] = question_id
        session["used_questions"] = [session["current_question_id"]]
    if request.method == "POST":
        action = request.form.get("action")
        if action == "exit":
            return redirect("/")
        selected_choice = request.form.get("choice")
        if not selected_choice:
            return render_template("apology.html", message="Please return to the previous page and select an answer.")
        result = cur.execute(
            "SELECT is_correct, question_id FROM choices WHERE id = ?", (selected_choice,)
        ).fetchone()
        
        if not result or result[1] != session["current_question_id"]:
            return render_template("apology.html")

        if result and result[0] == 1 and session["score"] < MAX_SCORE:
            session["score"] += 1
        else:
            session["score"] = session["score"]
        session["question_number"] += 1
        used = session["used_questions"]
        placeholders = ",".join("?" * len(used))
        query = f"""
            SELECT id
            FROM questions
            WHERE id NOT IN ({placeholders})
            ORDER BY RANDOM()
            LIMIT 1
        """
        next_question_result = cur.execute(
            query,
            used
        ).fetchone()
        if session["question_number"] > 10:
            return redirect("/results")
        next_question_id = next_question_result[0]
        session["current_question_id"] = next_question_id
        session["used_questions"].append(next_question_id)
        return redirect("/question")
    rows = cur.execute("""
                       SELECT questions.question_text,
                       choices.choice_text,
                       choices.is_correct,
                       choices.id
                       FROM questions
                       JOIN choices
                       ON questions.id = choices.question_id
                       WHERE questions.id = ?
                       """, (session["current_question_id"],)).fetchall()
    return render_template("question.html", question=rows, question_number=session["question_number"], score=session["score"])

@app.route("/register", methods=["GET", "POST"])
def register():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    if request.method == "POST":
        if not request.form.get("username"):
            return render_template("apology.html", message="must provide username") 
        elif not request.form.get("password"):
            return render_template("apology.html", message="must provide password") 
        elif not request.form.get("confirmation"):
            return render_template("apology.html", message="must provide password confirmation") 
        elif not request.form.get("password") == request.form.get("confirmation"):
            return render_template("apology.html", message="must provide matching password and confirmation")
        hashed_password = generate_password_hash(request.form.get("password"))
        try:
            cur.execute(
                "INSERT INTO users (username, hash) VALUES (?, ?)",
                (request.form.get("username"), hashed_password)
            )
        except sqlite3.IntegrityError:
            return ("username already exists")
        con.commit()
        session.clear()
        return redirect("/")
    else:
        return render_template("register.html")
    

@app.route("/results", methods=["GET", "POST"])
def results():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    if "id" not in session or "score" not in session:
        return redirect("/")
    if request.method in ["GET", "POST"]:
        user_id = session["id"]
        score = session["score"]
        current_high_score = (cur.execute(
            "SELECT high_score FROM users WHERE id = ?", (session["id"],)
        ).fetchone())
        current_high_score_value = current_high_score[0]
        if score > current_high_score_value:
            cur.execute("""
                        UPDATE users
                        SET high_score = ?
                        WHERE id = ?
            """, (score, user_id))
        con.commit()
    return render_template("results.html", score=score)