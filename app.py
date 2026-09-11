import os
import sqlite3
from datetime import datetime, timezone
from functools import wraps

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "analytics.db")

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "troque-esta-chave-em-producao")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "arapucapishing")


def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with get_db() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.commit()


def record_event(event_type):
    with get_db() as connection:
        connection.execute(
            "INSERT INTO events (event_type, created_at) VALUES (?, ?)",
            (event_type, datetime.now(timezone.utc).isoformat()),
        )
        connection.commit()


def dashboard_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("dashboard_authenticated"):
            return redirect(url_for("dashboard_login"))
        return view(*args, **kwargs)

    return wrapped_view


@app.route("/", methods=["GET"])
def index():
    record_event("view")
    return render_template("index.html")


@app.post("/api/password-intent")
def password_intent():
    record_event("password_intent")
    return jsonify({"ok": True})


@app.post("/submit")
def submit():
    name = request.form.get("name", "").strip()
    password = request.form.get("password", "")
    if not name or not password:
        return render_template("index.html", error="Preencha seu nome e sua senha."), 400

    # Registra apenas o envio; a senha nunca e armazenada.
    record_event("submission")
    return render_template("index.html", submitted=True, name=name)


@app.route("/dashboard/login", methods=["GET", "POST"])
def dashboard_login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["dashboard_authenticated"] = True
            return redirect(url_for("dashboard"))
        error = "Senha incorreta."
    return render_template("dashboard_login.html", error=error)


@app.get("/dashboard/logout")
def dashboard_logout():
    session.pop("dashboard_authenticated", None)
    return redirect(url_for("dashboard_login"))


@app.get("/dashboard")
@dashboard_required
def dashboard():
    with get_db() as connection:
        totals = connection.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(event_type = 'view') AS views,
                SUM(event_type = 'password_intent') AS password_intents,
                SUM(event_type = 'submission') AS submissions
            FROM events
            """
        ).fetchone()
        recent_events = connection.execute(
            "SELECT event_type, created_at FROM events ORDER BY id DESC LIMIT 8"
        ).fetchall()

    stats = {
        "total": totals["total"] or 0,
        "views": totals["views"] or 0,
        "password_intents": totals["password_intents"] or 0,
        "submissions": totals["submissions"] or 0,
    }
    return render_template("dashboard.html", stats=stats, recent_events=recent_events)


init_db()

if __name__ == "__main__":
    app.run(debug=False, port=int(os.environ.get("PORT", "5000")))
