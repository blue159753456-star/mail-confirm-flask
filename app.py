import os
from flask import Flask, request, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)


def get_conn():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("找不到 DATABASE_URL 環境變數")
    return psycopg2.connect(database_url)


def init_db():
    conn = None
    cur = None
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS confirm_tokens (
                id SERIAL PRIMARY KEY,
                token TEXT UNIQUE NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                created_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                confirm_time TIMESTAMPTZ,
                processed BOOLEAN NOT NULL DEFAULT FALSE
            )
        """)

        conn.commit()
        print("資料表 confirm_tokens 初始化完成")

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"init_db 發生錯誤：{e}")

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


@app.route("/")
def index():
    return "mail confirm service is running"


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
            SELECT status, created_time
            FROM confirm_tokens
            WHERE token = %s
        """, (token,))
        row = cur.fetchone()

        # 舊 token 若已被新一批覆蓋，這裡會查不到
        if not row:
            return "此連結已失效或已被更新", 400

        status, created_time = row

        if status == "CONFIRMED":
            return "此連結已確認過"

        # 超過 24 小時視為過期
        cur.execute("""
            SELECT NOW() > (%s + INTERVAL '24 hours')
        """, (created_time,))
        expired = cur.fetchone()[0]

        if expired:
            return "此連結已過期，請重新申請", 400

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


@app.route("/api/upload_tokens", methods=["POST"])
def upload_tokens():
    """
    接收格式：
    {
        "tokens": ["token1", "token2", ...]
    }

    邏輯：
    1. 清掉舊 token
    2. 插入最新一批 token
    """
    data = request.get_json(silent=True) or {}
    tokens = data.get("tokens", [])

    if not isinstance(tokens, list) or not tokens:
        return jsonify({"error": "tokens 格式錯誤或為空"}), 400

    # 清理空白與重複
    clean_tokens = []
    seen = set()
    for t in tokens:
        token = str(t).strip()
        if token and token not in seen:
            clean_tokens.append(token)
            seen.add(token)

    if not clean_tokens:
        return jsonify({"error": "沒有有效 token"}), 400

    conn = None
    cur = None
    try:
        conn = get_conn()
        cur = conn.cursor()

        # 關鍵：清掉舊 token，避免客戶點舊連結仍成功
        cur.execute("DELETE FROM confirm_tokens")

        for token in clean_tokens:
            cur.execute("""
                INSERT INTO confirm_tokens (token, status, created_time, processed)
                VALUES (%s, 'PENDING', NOW(), FALSE)
            """, (token,))

        conn.commit()

        return jsonify({
            "message": "tokens uploaded successfully",
            "count": len(clean_tokens)
        })

    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"error": str(e)}), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


@app.route("/api/new_tokens", methods=["GET"])
def new_tokens():
    """
    回傳已確認但尚未 processed 的 token
    """
    conn = None
    cur = None
    try:
        conn = get_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("""
            SELECT token, confirm_time
            FROM confirm_tokens
            WHERE status = 'CONFIRMED'
              AND processed = FALSE
            ORDER BY confirm_time ASC
        """)
        rows = cur.fetchall()

        return jsonify(rows)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


@app.route("/api/mark_processed", methods=["POST"])
def mark_processed():
    """
    接收格式：
    {
        "tokens": ["token1", "token2", ...]
    }
    """
    data = request.get_json(silent=True) or {}
    tokens = data.get("tokens", [])

    if not isinstance(tokens, list) or not tokens:
        return jsonify({"error": "tokens 格式錯誤或為空"}), 400

    clean_tokens = [str(t).strip() for t in tokens if str(t).strip()]
    if not clean_tokens:
        return jsonify({"error": "沒有有效 token"}), 400

    conn = None
    cur = None
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            UPDATE confirm_tokens
            SET processed = TRUE
            WHERE token = ANY(%s)
        """, (clean_tokens,))

        updated_count = cur.rowcount
        conn.commit()

        return jsonify({
            "message": "processed updated",
            "count": updated_count
        })

    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"error": str(e)}), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


@app.route("/api/reset_db", methods=["POST"])
def reset_db():
    """
    測試用：清空 confirm_tokens
    正式環境若不需要可刪除
    """
    conn = None
    cur = None
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("TRUNCATE TABLE confirm_tokens RESTART IDENTITY")
        conn.commit()

        return jsonify({"message": "confirm_tokens 已清空"})

    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"error": str(e)}), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# 啟動時初始化資料表
init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
