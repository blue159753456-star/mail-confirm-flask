from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "Render Flask 部署成功"

@app.route("/confirm")
def confirm():
    return "確認頁面正常"