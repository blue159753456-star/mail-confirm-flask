from flask import Flask, request, jsonify
import psycopg2
import os

app = Flask(__name__)


def get_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def format_dt(dt_value):
    """
    將資料庫取出的時間統一格式化為 YYYY-MM-DD HH:MM:SS
    若 dt_value 已是字串，則去掉小數秒
    """
    if dt_value is None:
        return ""

    if hasattr(dt_value, "strftime"):
        return dt_value.strftime("%Y-%m-%d %H:%M:%S")

    return str(dt_value).split(".")[0]


@app.route("/")
def home():
    return "Render Flask + DB 成功"


@app.route("/reset_db")
def reset_db():
    conn = None
    cur = None
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("DROP TABLE IF EXISTS confirm_logs")
        cur.execute("""
            CREATE TABLE confirm_logs (
                id SERIAL PRIMARY KEY,
                token TEXT UNIQUE,
                confirm_time TIMESTAMPTZ,
                processed BOOLEAN DEFAULT FALSE
            )
        """)

        conn.commit()
        return "confirm_logs 已重建完成"

    except Exception as e:
        if conn:
            conn.rollback()
        return f"reset_db 發生錯誤：{e}", 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


@app.route("/confirm")
def confirm():
    token = request.args.get("token", "").strip()

    if not token:
        return "缺少 token", 400

    conn = None
    cur = None
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS confirm_logs (
                id SERIAL PRIMARY KEY,
                token TEXT UNIQUE,
                confirm_time TIMESTAMPTZ,
                processed BOOLEAN DEFAULT FALSE
            )
        """)

        cur.execute("""
            INSERT INTO confirm_logs (token, confirm_time)
            VALUES (%s, NOW())
            ON CONFLICT (token) DO NOTHING
        """, (token,))

        conn.commit()

        if cur.rowcount == 0:
            return "此連結已確認過"

        return "您已完成確認"

    except Exception as e:
        if conn:
            conn.rollback()
        return f"系統錯誤：{e}", 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


@app.route("/logs")
def logs():
    conn = None
    cur = None
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            SELECT token, confirm_time AT TIME ZONE 'Asia/Taipei', processed
            FROM confirm_logs
            ORDER BY confirm_time DESC
        """)

        rows = cur.fetchall()

        result = ""
        for token, confirm_time, processed in rows:
            result += f"{format_dt(confirm_time)}, token={token}, processed={processed}\n"

        return f"<pre>{result}</pre>"

    except Exception as e:
        return f"logs 發生錯誤：{e}", 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


@app.route("/api/confirmed_tokens")
def api_confirmed_tokens():
    conn = None
    cur = None
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            SELECT token, confirm_time AT TIME ZONE 'Asia/Taipei', processed
            FROM confirm_logs
            ORDER BY confirm_time DESC
        """)

        rows = cur.fetchall()

        data = []
        for token, confirm_time, processed in rows:
            data.append({
                "token": token,
                "confirm_time": format_dt(confirm_time),
                "processed": processed
            })

        return jsonify(data)

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


@app.route("/api/new_tokens")
def api_new_tokens():
    conn = None
    cur = None
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            SELECT id, token, confirm_time AT TIME ZONE 'Asia/Taipei'
            FROM confirm_logs
            WHERE processed = FALSE
            ORDER BY confirm_time
        """)

        rows = cur.fetchall()
        ids = [row[0] for row in rows]

        if ids:
            cur.execute("""
                UPDATE confirm_logs
                SET processed = TRUE
                WHERE id = ANY(%s)
            """, (ids,))
            conn.commit()

        data = []
        for _, token, confirm_time in rows:
            data.append({
                "token": token,
                "confirm_time": format_dt(confirm_time)
            })

        return jsonify(data)

    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
