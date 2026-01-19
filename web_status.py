# Dynamic web status + caster management page for NTRIP monitor
# Refactored to match symmetric alerting logic in monitor.py
# Suitable for Raspberry Pi 1

from flask import Flask, request, redirect, url_for, render_template_string
import sqlite3
from datetime import datetime

DB_FILE = "monitor.db"
ALERT_THRESHOLD = 2  # MUST match monitor.py

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>NTRIP Monitor</title>
    <meta http-equiv="refresh" content="60">
    <style>
        body { font-family: Arial, sans-serif; background:#f5f5f5; }
        h1, h2 { text-align:center; }
        table { border-collapse: collapse; width: 90%; margin: 20px auto; }
        th, td { padding: 8px 12px; border: 1px solid #ccc; }
        th { background:#333; color:#fff; }
        .ok { background:#c8e6c9; }
        .fail { background:#ffcdd2; }
        .unstable { background:#fff3cd; }
        .formbox { width: 90%; margin: auto; background:#fff; padding:15px; }
        input { padding:6px; margin:4px; }
        .btn { padding:6px 10px; }
        .danger { background:#c62828; color:#fff; }
    </style>
</head>
<body>

<h1>NTRIP Monitor Status</h1>
<div style="text-align:center; color:#555;">Last refresh: {{ now }}</div>

<h2>Current Status</h2>
<table>
<tr>
    <th>Caster</th>
    <th>Status</th>
    <th>Last Message</th>
    <th>Last Check</th>
</tr>
{% for row in status_rows %}
<tr class="{{ row['css'] }}">
<td>{{ row['caster'] }}</td>
<td>{{ row['status'] }}</td>
<td>{{ row['message'] }}</td>
<td>{{ row['timestamp'] }}</td>
</tr>
{% endfor %}
</table>

<h2>Manage NTRIP Casters</h2>
<div class="formbox">
<form method="post" action="/add">
<b>Add new caster</b><br>
Name <input name="name" required>
Host <input name="host" required>
Port <input name="port" value="2101" required size="5">
User <input name="username" required>
Pass <input name="password" required>
<button class="btn" type="submit">Add</button>
</form>
</div>

<table>
<tr><th>Name</th><th>Host</th><th>Port</th><th>User</th><th>Password</th><th>Actions</th></tr>
{% for c in casters %}
<tr>
<form method="post" action="/edit/{{ c['id'] }}">
<td><input name="name" value="{{ c['name'] }}"></td>
<td><input name="host" value="{{ c['host'] }}"></td>
<td><input name="port" value="{{ c['port'] }}" size="5"></td>
<td><input name="username" value="{{ c['username'] }}"></td>
<td><input name="password" value="{{ c['password'] }}"></td>
<td>
    <button class="btn" type="submit">Save</button>
    <a href="/delete/{{ c['id'] }}" class="btn danger">Delete</a>
</td>
</form>
</tr>
{% endfor %}
</table>

</body>
</html>
"""

# -----------------------------
# DB helpers
# -----------------------------

def db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_tables():
    conn = db()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS casters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            host TEXT,
            port INTEGER,
            username TEXT,
            password TEXT
        )
    """)

    conn.commit()
    conn.close()


def get_casters():
    conn = db()
    c = conn.cursor()
    c.execute("SELECT * FROM casters ORDER BY name")
    rows = c.fetchall()
    conn.close()
    return rows


def get_status_rows():
    conn = db()
    c = conn.cursor()

    status_rows = []

    for caster in get_casters():
        c.execute("""
            SELECT success, message, timestamp
            FROM checks
            WHERE caster = ?
            ORDER BY id DESC
            LIMIT ?
        """, (caster["name"], ALERT_THRESHOLD))

        rows = c.fetchall()

        if not rows:
            status = "UNKNOWN"
            css = "unstable"
            message = ""
            timestamp = ""
        else:
            successes = [r["success"] for r in rows]
            message = rows[0]["message"]
            timestamp = rows[0]["timestamp"]

            if successes == [1] * ALERT_THRESHOLD:
                status = "UP"
                css = "ok"
            elif successes == [0] * ALERT_THRESHOLD:
                status = "DOWN"
                css = "fail"
            else:
                status = "UNSTABLE"
                css = "unstable"

        status_rows.append({
            "caster": caster["name"],
            "status": status,
            "css": css,
            "message": message,
            "timestamp": timestamp
        })

    conn.close()
    return status_rows

# -----------------------------
# Routes
# -----------------------------

@app.route("/")
def index():
    ensure_tables()
    return render_template_string(
        HTML_TEMPLATE,
        status_rows=get_status_rows(),
        casters=get_casters(),
        now=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )


@app.route("/add", methods=["POST"])
def add():
    conn = db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO casters (name, host, port, username, password) VALUES (?, ?, ?, ?, ?)",
        (request.form["name"], request.form["host"], int(request.form["port"]),
         request.form["username"], request.form["password"])
    )
    conn.commit()
    conn.close()
    return redirect(url_for("index"))


@app.route("/edit/<int:id>", methods=["POST"])
def edit(id):
    conn = db()
    c = conn.cursor()

    c.execute(
        "UPDATE casters SET name=?, host=?, port=?, username=?, password=? WHERE id=?",
        (request.form["name"], request.form["host"], int(request.form["port"]),
         request.form["username"], request.form["password"], id)
    )

    conn.commit()
    conn.close()
    return redirect(url_for("index"))


@app.route("/delete/<int:id>")
def delete(id):
    conn = db()
    c = conn.cursor()
    c.execute("DELETE FROM casters WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))


if __name__ == "__main__":
    ensure_tables()
    app.run(host="0.0.0.0", port=8080)
