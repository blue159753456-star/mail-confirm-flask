@app.route("/confirm")
def confirm():
    token = request.args.get("token", "").strip()

    if not token:
        return "缺少 token", 400

    conn = get_conn()
    cur = conn.cursor()

    # 建表（只建立一次）
    cur.execute("""
        CREATE TABLE IF NOT EXISTS confirm_logs (
            id SERIAL PRIMARY KEY,
            token TEXT UNIQUE,
            confirm_time TIMESTAMP
        )
    """)

    # 插入（防重複）
    cur.execute("""
        INSERT INTO confirm_logs (token, confirm_time)
        VALUES (%s, %s)
        ON CONFLICT (token) DO NOTHING
    """, (token, datetime.now()))

    conn.commit()

    # 判斷是否重複
    if cur.rowcount == 0:
        cur.close()
        conn.close()
        return f"此連結已確認過（token={token}）"

    cur.close()
    conn.close()

    return f"確認成功 token={token}"
