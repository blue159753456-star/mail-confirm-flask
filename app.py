@app.route("/confirm")
def confirm():
    token = request.args.get("token", "").strip()

    if not token:
        return "缺少 token", 400

    conn = get_conn()
    cur = conn.cursor()

    # 🔥 這段是你剛換的
    cur.execute("DROP TABLE IF EXISTS confirm_logs")

    cur.execute("""
        CREATE TABLE confirm_logs (
            id SERIAL PRIMARY KEY,
            token TEXT UNIQUE,
            confirm_time TIMESTAMP
        )
    """)

    # 檢查是否已存在
    cur.execute("""
        SELECT id FROM confirm_logs WHERE token = %s
    """, (token,))

    exists = cur.fetchone()

    if exists:
        cur.close()
        conn.close()
        return f"此連結已確認過（token={token}）"

    # 寫入
    cur.execute("""
        INSERT INTO confirm_logs (token, confirm_time)
        VALUES (%s, %s)
    """, (token, datetime.now()))

    conn.commit()
    cur.close()
    conn.close()

    return f"確認成功 token={token}"
