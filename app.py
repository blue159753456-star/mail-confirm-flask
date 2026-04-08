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


@app.route("/init_db")
def init_db():
    conn = None
    cur = None
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS confirm_tokens (
                token TEXT PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'PENDING',
                created_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                confirm_time TIMESTAMPTZ,
                processed BOOLEAN NOT NULL DEFAULT FALSE
            )
        """)

        conn.commit()
        return "confirm_tokens 建立完成"

    except Exception as e:
        if conn:
            conn.rollback()
        return f"init_db 發生錯誤：{e}", 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


@app.route("/api/upload_tokens", methods=["POST"])
def api_upload_tokens():
    conn = None
    cur = None
    try:
        data = request.get_json(silent=True) or {}
        tokens = data.get("tokens", [])

        if not isinstance(tokens, list) or not tokens:
            return jsonify({"ok": False, "error": "缺少 tokens"}), 400

        conn = get_conn()
        cur = conn.cursor()

        # 保險起見，若尚未建表則自動建表
        cur.execute("""
            CREATE TABLE IF NOT EXISTS confirm_tokens (
                token TEXT PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'PENDING',
                created_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                confirm_time TIMESTAMPTZ,
                processed BOOLEAN NOT NULL DEFAULT FALSE
            )
        """)

        inserted = 0
        skipped = 0

        for token in tokens:
            token = str(token).strip()

            if not token:
                skipped += 1
                continue

            cur.execute("""
                INSERT INTO confirm_tokens (token, status, processed)
                VALUES (%s, 'PENDING', FALSE)
                ON CONFLICT (token) DO NOTHING
            """, (token,))

            if cur.rowcount > 0:
                inserted += 1
            else:
                skipped += 1

        conn.commit()

        return jsonify({
            "ok": True,
            "received": len(tokens),
            "inserted": inserted,
            "skipped": skipped
        })

    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500

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
            SELECT status
            FROM confirm_tokens
            WHERE token = %s
        """, (token,))
        row = cur.fetchone()

        if not row:
            return "此連結無效或不存在", 400

        status = row[0]

        if status == "CONFIRMED":
            return "此連結已確認過"

        cur.execute("""
            UPDATE confirm_tokens
            SET status = 'CONFIRMED',
                confirm_time = NOW()
            WHERE token = %s
        """, (token,))

        conn.commit()
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


@app.route("/api/new_tokens")
def api_new_tokens():
    conn = None
    cur = None
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            SELECT token, confirm_time AT TIME ZONE 'Asia/Taipei'
            FROM confirm_tokens
            WHERE status = 'CONFIRMED'
              AND processed = FALSE
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


@app.route("/api/mark_processed", methods=["POST"])
def api_mark_processed():
    conn = None
    cur = None
    try:
        data = request.get_json(silent=True) or {}
        tokens = data.get("tokens", [])

        if not isinstance(tokens, list) or not tokens:
            return jsonify({"ok": False, "error": "缺少 tokens"}), 400

        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            UPDATE confirm_tokens
            SET processed = TRUE
            WHERE token = ANY(%s)
        """, (tokens,))

        updated = cur.rowcount
        conn.commit()

        return jsonify({
            "ok": True,
            "updated": updated
        })

    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
