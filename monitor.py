import socket
import base64
import sqlite3
import time
import csv
import os
import urllib.request
import urllib.parse

from config import CHECK_INTERVAL, TELEGRAM, DB_FILE, CSV_PREFIX

TIMEOUT = 10
ALERT_THRESHOLD = 2   # N consecutive results required

# ------------------------------------------------
# DB helpers
# ------------------------------------------------

def db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def load_casters():
    conn = db()
    rows = conn.execute(
        "SELECT name, host, port, username, password FROM casters"
    ).fetchall()
    conn.close()
    return rows


def ensure_state_table():
    conn = db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS caster_state (
            caster TEXT PRIMARY KEY,
            last_state TEXT
        )
    """)
    conn.commit()
    conn.close()


def get_last_state(caster):
    conn = db()
    row = conn.execute(
        "SELECT last_state FROM caster_state WHERE caster=?",
        (caster,)
    ).fetchone()
    conn.close()
    return row["last_state"] if row else None


def set_last_state(caster, state):
    conn = db()
    conn.execute("""
        INSERT INTO caster_state (caster, last_state)
        VALUES (?, ?)
        ON CONFLICT(caster) DO UPDATE SET last_state=excluded.last_state
    """, (caster, state))
    conn.commit()
    conn.close()


def log_result(caster, success, message):
    conn = db()
    conn.execute(
        "INSERT INTO checks (caster, success, message) VALUES (?, ?, ?)",
        (caster, int(success), message)
    )
    conn.commit()
    conn.close()

    write_csv_row([
        time.strftime("%Y-%m-%d %H:%M:%S"),
        caster,
        success,
        message
    ])


def last_n_results(caster, n):
    conn = db()
    rows = conn.execute("""
        SELECT success FROM checks
        WHERE caster=?
        ORDER BY id DESC
        LIMIT ?
    """, (caster, n)).fetchall()
    conn.close()
    return [r["success"] for r in rows]

# ------------------------------------------------
# CSV
# ------------------------------------------------

def get_csv_filename():
    return "{}-{}.csv".format(
        CSV_PREFIX, time.strftime("%Y-%m-%d")
    )


def write_csv_row(row):
    filename = get_csv_filename()
    exists = os.path.isfile(filename)

    with open(filename, "a", newline="") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["timestamp", "caster", "success", "message"])
        w.writerow(row)

def cleanup_old_csv_files(days=30):
    cutoff = time.time() - (days * 86400)

    for fname in os.listdir("."):
        if not fname.startswith(CSV_PREFIX) or not fname.endswith(".csv"):
            continue

        try:
            if os.path.getmtime(fname) <= cutoff:
                os.remove(fname)
        except Exception:
            # Never allow cleanup to break monitoring
            pass


# ------------------------------------------------
# Telegram (hardened)
# ------------------------------------------------

def telegram_alert(text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM['bot_token']}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": TELEGRAM["chat_id"],
            "text": text
        }).encode("utf-8")
        urllib.request.urlopen(
            urllib.request.Request(url, data=data),
            timeout=10
        )
    except Exception:
        pass

# ------------------------------------------------
# NTRIP check (hardened)
# ------------------------------------------------

def check_ntrip(caster):
    auth = f"{caster['username']}:{caster['password']}"
    auth_b64 = base64.b64encode(auth.encode()).decode()

    request = (
        "GET / HTTP/1.1\r\n"
        f"Host: {caster['host']}\r\n"
        "User-Agent: NTRIP PythonMonitor\r\n"
        f"Authorization: Basic {auth_b64}\r\n"
        "Accept: */*\r\n"
        "Connection: close\r\n\r\n"
    )

    try:
        with socket.create_connection(
            (caster["host"], caster["port"]),
            timeout=TIMEOUT
        ) as s:
            s.sendall(request.encode())
            response = s.recv(4096).decode(errors="ignore")

        if (
            "SOURCETABLE" in response
            or "200 OK" in response
            or response.startswith("ICY 200")
        ):
            return True, "Caster responded OK"

        return False, "Unexpected response"

    except Exception as e:
        return False, str(e)

# ------------------------------------------------
# Main loop
# ------------------------------------------------

def derive_state(results):
    if results == [1] * ALERT_THRESHOLD:
        return "UP"
    if results == [0] * ALERT_THRESHOLD:
        return "DOWN"
    return "UNSTABLE"


def main():
    ensure_state_table()

    while True:
        for caster in load_casters():
            try:
                success, message = check_ntrip(caster)
                log_result(caster["name"], success, message)

                history = last_n_results(
                    caster["name"], ALERT_THRESHOLD
                )
                if len(history) < ALERT_THRESHOLD:
                    continue

                current_state = derive_state(history)
                last_state = get_last_state(caster["name"])

                # Only alert on state change
                if current_state != last_state:
                    if current_state == "DOWN":
                        telegram_alert(
                            f"🚨 NTRIP DOWN\n{caster['name']}\n{message}"
                        )
                    elif current_state == "UP":
                        telegram_alert(
                            f"✅ NTRIP RECOVERED\n{caster['name']}"
                        )

                    set_last_state(caster["name"], current_state)

            except Exception as e:
                telegram_alert(
                    f"⚠️ Monitor error\n{caster['name']}\n{e}"
                )

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
