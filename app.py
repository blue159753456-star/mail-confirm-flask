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

        if not row:
            return "此連結無效或不存在", 400

        status, created_time = row

        if status == "CONFIRMED":
            return "此連結已確認過"

        # 超過 24 小時視為過期
        cur.execute("""
            SELECT NOW() > (%s + INTERVAL '24 hours')
        """, (created_time,))
        expired = cur.fetchone()[0]

        if expired:
            return "此連結已過期，請重新申請"

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
