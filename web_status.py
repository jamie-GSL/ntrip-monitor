# Dynamic web status + caster management page for NTRIP monitor
# Lightweight Flask app suitable for Raspberry Pi 1
# Provides status view AND add/edit/delete NTRIP casters

from flask import Flask, request, redirect, url_for, render_template_string
import sqlite3
from datetime import datetime

DB_FILE = "monitor.db"

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
<tr><th>Caster</th><th>Status</th><th>Last Message</th><th>Last Check</th></tr>
{% for row in status_rows %}
<tr class="{{ 'ok' if row['success'] else 'fail' }}">
<td>{{ row['caster'] }}</td>
<td>{{ 'UP' if row['success'] else 'DOWN' }}</td>
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
<td><button class="btn" type="submit">Save</button>
<a href="/delete/{{ c['id'] }}" class="btn danger">Delete</a>
</td>
</form>
</tr>
{% endfor %}
</table>

</body>
</html>
"""


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


def get_latest_status():
    conn = db()
    c = conn.cursor()

    c.execute("""
        SELECT c1.caster, c1.success, c1.message, c1.timestamp
        FROM checks c1
        JOIN (
            SELECT caster, MAX(id) AS max_id
            FROM checks
            GROUP BY caster
        ) c2
	        ON c1.caster = c2.caster AND c1.id = c2.max_id
	JOIN casters c3
		ON c1.caster = c3.name
        ORDER BY c1.caster
    """)

    rows = c.fetchall()
    conn.close()
    return rows


def get_casters():
    conn = db()
    c = conn.cursor()
    c.execute("SELECT * FROM casters ORDER BY name")
    rows = c.fetchall()
    conn.close()
    return rows


@app.route("/")
def index():
    ensure_tables()
    return render_template_string(
        HTML_TEMPLATE,
        status_rows=get_latest_status(),
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

    if request.form.get("password"):
        c.execute(
            "UPDATE casters SET name=?, host=?, port=?, username=?, password=? WHERE id=?",
            (request.form["name"], request.form["host"], int(request.form["port"]),
             request.form["username"], request.form["password"], id)
        )
    else:
        c.execute(
            "UPDATE casters SET name=?, host=?, port=?, username=? WHERE id=?",
            (request.form["name"], request.form["host"], int(request.form["port"]),
             request.form["username"], id)
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
