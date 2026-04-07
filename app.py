from flask import Flask, request
from datetime import datetime

app = Flask(__name__)

LOG_FILE = "confirm_log.txt"

@app.route("/")
def home():
    return "Render Flask 部署成功"

@app.route("/confirm")
def confirm():
    token = request.args.get("token", "").strip()

    if not token:
        return "缺少 token 參數", 400

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{now}, token={token}\n")

    return f"確認成功，token={token}"

@app.route("/logs")
def logs():
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        return f"<pre>{content}</pre>"
    except FileNotFoundError:
        return "目前沒有確認紀錄"
