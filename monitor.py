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

def load_casters():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT name, host, port, username, password FROM casters")
    rows = c.fetchall()
    conn.close()
    return rows


def telegram_alert(text):
    url = "https://api.telegram.org/bot{}/sendMessage".format(
        TELEGRAM["bot_token"]
    )
    data = urllib.parse.urlencode({
        "chat_id": TELEGRAM["chat_id"],
        "text": text
    }).encode("utf-8")

    req = urllib.request.Request(url, data=data)
    urllib.request.urlopen(req, timeout=10)


def get_csv_filename():
    date_str = time.strftime("%Y-%m-%d")
    return "{}-{}.csv".format(CSV_PREFIX, date_str)


def write_csv_row(row):
    filename = get_csv_filename()
    file_exists = os.path.isfile(filename)

    with open(filename, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "caster", "success", "message"])
        writer.writerow(row)


def log_result(caster, success, message):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
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


def check_ntrip(caster):
    auth = "{}:{}".format(caster["username"], caster["password"])
    auth_b64 = base64.b64encode(auth.encode()).decode()

    request = (
        "GET / HTTP/1.0\r\n"
        "User-Agent: NTRIP PythonMonitor\r\n"
        "Authorization: Basic {}\r\n\r\n".format(auth_b64)
    )

    try:
        with socket.create_connection(
            (caster["host"], caster["port"]),
            timeout=TIMEOUT
        ) as s:
            s.sendall(request.encode())
            response = s.recv(4096).decode(errors="ignore")

        if "SOURCETABLE" in response:
            return True, "Sourcetable received"
        else:
            return False, "No sourcetable in response"

    except Exception as e:
        return False, str(e)


def last_two_results(caster):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        SELECT success FROM checks
        WHERE caster = ?
        ORDER BY id DESC
        LIMIT 2
    """, (caster,))
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def main():
    while True:
        for caster in load_casters():
            success, message = check_ntrip(caster)
            log_result(caster["name"], success, message)

            history = last_two_results(caster["name"])

            if history == [0, 0]:
                telegram_alert(
                    "🚨 NTRIP DOWN\n{}\n{}".format(
                        caster["name"], message
                    )
                )

            if history == [1, 0]:
                telegram_alert(
                    "✅ NTRIP RECOVERED\n{}".format(
                        caster["name"]
                    )
                )

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
