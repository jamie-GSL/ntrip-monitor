from flask import (
    Flask, request, redirect, url_for,
    render_template_string, send_from_directory
)
import sqlite3
from datetime import datetime, timedelta
from config import CSV_PREFIX
import os

DB_FILE = "monitor.db"
CSV_DIR = "."          # same directory as app
ALERT_THRESHOLD = 2    # MUST match monitor.py

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<title>NTRIP Monitor</title>
<meta http-equiv="refresh" content="60">
<meta name="viewport" content="width=device-width, initial-scale=1">

<style>
body { font-family: Arial, sans-serif; background:#f5f5f5; margin:0; }
h1, h2 { text-align:center; margin:10px 0; }
small { color:#555; }

.table-wrap { overflow-x:auto; }

table {
    border-collapse: collapse;
    width: 95%;
    margin: 10px auto;
    background:#fff;
}
th, td {
    padding: 8px 10px;
    border: 1px solid #ccc;
    text-align:center;
}
th { background:#333; color:#fff; }

.ok { background:#c8e6c9; }
.fail { background:#ffcdd2; }
.unstable { background:#fff3cd; }

.formbox {
    width:95%;
    margin:auto;
    background:#fff;
    padding:10px;
}

input {
    padding:6px;
    margin:4px;
    width:100%;
    max-width:160px;
}

.btn {
    padding:6px 10px;
    display:inline-block;
    margin:4px;
}

.danger { background:#c62828; color:#fff; text-decoration:none; }

@media (max-width: 600px) {
    th, td { padding:6px; font-size:13px; }
}
</style>
</head>
<body>

<h1>NTRIP Monitor</h1>
<div style="text-align:center;">
<small>Last refresh: {{ now }}</small>
</div>

<h2>Status</h2>
<div class="table-wrap">
<table>
<tr>
<th>Caster</th>
<th>Status</th>
<th>Outage</th>
<th>24h</th>
<th>7d</th>
<th>Last Message</th>
<th>Last Check</th>
</tr>

{% for r in status_rows %}
<tr class="{{ r.css }}">
<td>{{ r.caster }}</td>
<td>{{ r.status }}</td>
<td>{{ r.outage }}</td>
<td>{{ r.uptime_24 }}%</td>
<td>{{ r.uptime_7d }}%</td>
<td>{{ r.message }}</td>
<td>{{ r.timestamp }}</td>
</tr>
{% endfor %}
</table>
</div>

<h2>CSV Logs</h2>
<div style="text-align:center;">
{% for f in csv_files %}
<a class="btn" href="/csv/{{ f }}">{{ f }}</a>
{% endfor %}
</div>

<h2>Manage Casters</h2>
<div class="formbox">
<form method="post" action="/add">
<b>Add new caster</b><br>
<input name="name" placeholder="Name" required>
<input name="host" placeholder="Host" required>
<input name="port" value="2101" required>
<input name="username" placeholder="User" required>
<input name="password" placeholder="Pass" required>
<button class="btn" type="submit">Add</button>
</form>
</div>

<div class="table-wrap">
<table>
<tr>
<th>Name</th><th>Host</th><th>Port</th>
<th>User</th><th>Password</th><th>Actions</th>
</tr>

{% for c in casters %}
<tr>
<form method="post" action="/edit/{{ c.id }}">
<td><input name="name" value="{{ c.name }}"></td>
<td><input name="host" value="{{ c.host }}"></td>
<td><input name="port" value="{{ c.port }}"></td>
<td><input name="username" value="{{ c.username }}"></td>
<td><input name="password" value="{{ c.password }}"></td>
<td>
<button class="btn" type="submit">Save</button>
<a class="btn danger" href="/delete/{{ c.id }}">Delete</a>
</td>
</form>
</tr>
{% endfor %}
</table>
</div>

</body>
</html>
"""

# ------------------------------------------------

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


def uptime_percent(caster, since):
    conn = db()
    c = conn.cursor()
    c.execute("""
        SELECT COUNT(*) AS total,
               SUM(success) AS up
        FROM checks
        WHERE caster = ? AND timestamp >= ?
    """, (caster, since))
    r = c.fetchone()
    conn.close()

    if not r["total"]:
        return 0
    return int((r["up"] / r["total"]) * 100)


def outage_duration(caster):
    conn = db()
    c = conn.cursor()
    c.execute("""
        SELECT success, timestamp
        FROM checks
        WHERE caster = ?
        ORDER BY id DESC
    """, (caster,))
    rows = c.fetchall()
    conn.close()

    if not rows or rows[0]["success"] == 1:
        return "—"

    for r in rows:
        if r["success"] == 1:
            start = datetime.fromisoformat(r["timestamp"])
            end = datetime.fromisoformat(rows[0]["timestamp"])
            delta = end - start
            return str(delta).split(".")[0]

    start = datetime.fromisoformat(rows[-1]["timestamp"])
    end = datetime.fromisoformat(rows[0]["timestamp"])
    return str(end - start).split(".")[0]


def get_status_rows():
    conn = db()
    c = conn.cursor()

    rows = []
    casters = c.execute("SELECT * FROM casters ORDER BY name").fetchall()

    for caster in casters:
        c.execute("""
            SELECT success, message, timestamp
            FROM checks
            WHERE caster = ?
            ORDER BY id DESC
            LIMIT ?
        """, (caster["name"], ALERT_THRESHOLD))

        checks = c.fetchall()
        if not checks:
            continue

        states = [r["success"] for r in checks]

        if states == [1] * ALERT_THRESHOLD:
            status, css = "UP", "ok"
        elif states == [0] * ALERT_THRESHOLD:
            status, css = "DOWN", "fail"
        else:
            status, css = "UNSTABLE", "unstable"

        rows.append({
            "caster": caster["name"],
            "status": status,
            "css": css,
            "message": checks[0]["message"],
            "timestamp": checks[0]["timestamp"],
            "outage": outage_duration(caster["name"]),
            "uptime_24": uptime_percent(
                caster["name"],
                (datetime.now() - timedelta(days=1)).isoformat()
            ),
            "uptime_7d": uptime_percent(
                caster["name"],
                (datetime.now() - timedelta(days=7)).isoformat()
            ),
        })

    conn.close()
    return rows


def list_csv_files():
    return sorted(
        f for f in os.listdir(CSV_DIR)
        if f.startswith(CSV_PREFIX) and f.endswith(".csv")
    )

# ------------------------------------------------

@app.route("/")
def index():
    ensure_tables()
    return render_template_string(
        HTML_TEMPLATE,
        status_rows=get_status_rows(),
        casters=db().execute("SELECT * FROM casters").fetchall(),
        csv_files=list_csv_files(),
        now=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )


@app.route("/csv/<path:filename>")
def csv_download(filename):
    return send_from_directory(CSV_DIR, filename, as_attachment=True)


@app.route("/add", methods=["POST"])
def add():
    db().execute(
        "INSERT INTO casters (name, host, port, username, password) VALUES (?, ?, ?, ?, ?)",
        (request.form["name"], request.form["host"],
         int(request.form["port"]),
         request.form["username"], request.form["password"])
    ).connection.commit()
    return redirect(url_for("index"))


@app.route("/edit/<int:id>", methods=["POST"])
def edit(id):
    db().execute("""
        UPDATE casters
        SET name=?, host=?, port=?, username=?, password=?
        WHERE id=?
    """, (request.form["name"], request.form["host"],
          int(request.form["port"]),
          request.form["username"],
          request.form["password"], id)).connection.commit()
    return redirect(url_for("index"))


@app.route("/delete/<int:id>")
def delete(id):
    db().execute("DELETE FROM casters WHERE id=?", (id,)).connection.commit()
    return redirect(url_for("index"))


if __name__ == "__main__":
    ensure_tables()
    app.run(host="0.0.0.0", port=8080)
