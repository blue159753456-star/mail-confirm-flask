from flask import Flask, request, jsonify
import psycopg2
import os

app = Flask(__name__)


def get_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def format_dt(dt_value):
    if dt_value is None:
        return ""
    if hasattr(dt_value, "strftime"):
        return dt_value.strftime("%Y-%m-%d %H:%M:%S")
    return str(dt_value).split(".")[0]


@app.route("/")
def home():
    return "MAIL CONFIRM SYSTEM OK"


# ✅ 確認連結
@app.route("/confirm")
def confirm():
    token = request.args.get("token", "").strip()

    if not token or len(token) > 200:
        return "此連結無效", 400

    conn = None
    cur = None
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO confirm_logs (token, confirm_time)
            VALUES (%s, NOW())
            ON CONFLICT (token) DO NOTHING
        """, (token,))
        conn.commit()

        if cur.rowcount == 0:
            return "此連結已確認過"

        return "您已完成電子郵件確認"

    except Exception as e:
        if conn:
            conn.rollback()
        return f"系統錯誤：{e}", 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# ✅ 查詢「尚未處理」資料（只讀）
@app.route("/api/new_tokens")
def api_new_tokens():
    conn = None
    cur = None
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            SELECT token, confirm_time AT TIME ZONE 'Asia/Taipei'
            FROM confirm_logs
            WHERE processed = FALSE
            ORDER BY confirm_time
        """)

        rows = cur.fetchall()

        data = []
        for token, confirm_time in rows:
            data.append({
                "token": token,
                "confirm_time": format_dt(confirm_time)
            })

        return jsonify(data)

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# ✅ 標記已處理
@app.route("/api/mark_processed", methods=["POST"])
def api_mark_processed():
    conn = None
    cur = None
    try:
        data = request.get_json(silent=True) or {}
        tokens = data.get("tokens", [])

        if not tokens:
            return jsonify({"ok": False, "error": "缺少 tokens"}), 400

        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            UPDATE confirm_logs
            SET processed = TRUE
            WHERE token = ANY(%s)
        """, (tokens,))

        updated = cur.rowcount
        conn.commit()

        return jsonify({"ok": True, "updated": updated})

    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
