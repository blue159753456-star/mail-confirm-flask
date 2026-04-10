from flask import request, render_template_string
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TW_TZ = ZoneInfo("Asia/Taipei")


CONFIRM_PAGE_HTML = """
<!doctype html>
<html lang="zh-Hant">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ title }}</title>
    <style>
        * { box-sizing: border-box; }
        body {
            margin: 0;
            font-family: "Microsoft JhengHei", Arial, sans-serif;
            background: #f3f4f6;
            color: #222;
        }
        .topbar {
            background: #d70022;
            color: #fff;
            padding: 22px 0;
            font-size: 22px;
            font-weight: 700;
            text-align: center;
            letter-spacing: 1px;
        }
        .wrap {
            min-height: calc(100vh - 72px);
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 30px 15px;
        }
        .card {
            width: 100%;
            max-width: 670px;
            background: #fff;
            border-radius: 18px;
            box-shadow: 0 12px 40px rgba(0,0,0,0.08);
            padding: 48px 36px;
            text-align: center;
        }
        .icon {
            font-size: 72px;
            line-height: 1;
            margin-bottom: 20px;
        }
        .icon.success { color: #1f9d55; }
        .icon.error { color: #ef4444; }
        .icon.info { color: #2563eb; }
        h1 {
            margin: 0 0 18px 0;
            font-size: 24px;
            color: #111827;
        }
        .msg {
            font-size: 16px;
            line-height: 1.9;
            color: #4b5563;
            white-space: pre-line;
        }
        .sub {
            margin-top: 26px;
            padding-top: 24px;
            border-top: 1px solid #e5e7eb;
            font-size: 14px;
            color: #9ca3af;
        }
    </style>
</head>
<body>
    <div class="topbar">花蓮信用合作社</div>
    <div class="wrap">
        <div class="card">
            <div class="icon {{ icon_class }}">{{ icon }}</div>
            <h1>{{ heading }}</h1>
            <div class="msg">{{ message }}</div>
            <div class="sub">The First Credit Cooperative Of Hualien</div>
        </div>
    </div>
</body>
</html>
"""


def render_confirm_page(title: str, heading: str, message: str, icon: str, icon_class: str):
    return render_template_string(
        CONFIRM_PAGE_HTML,
        title=title,
        heading=heading,
        message=message,
        icon=icon,
        icon_class=icon_class
    )


@app.route("/confirm")
def confirm():
    token = request.args.get("token", "").strip()

    if not token:
        return render_confirm_page(
            title="驗證失敗",
            heading="缺少驗證碼",
            message="連結格式不正確，未提供 token。",
            icon="✕",
            icon_class="error"
        ), 400

    conn = None
    cur = None

    try:
        conn = get_conn()
        cur = conn.cursor()

        # 只抓最新一筆，這是固定 token 設計的關鍵
        cur.execute("""
            SELECT id, token, created_time, confirm_time, status
            FROM confirm_tokens
            WHERE token = %s
            ORDER BY created_time DESC
            LIMIT 1
        """, (token,))
        row = cur.fetchone()

        if not row:
            return render_confirm_page(
                title="驗證失敗",
                heading="查無此連結",
                message="找不到此驗證連結，請重新申請驗證信。",
                icon="✕",
                icon_class="error"
            ), 404

        row_id, db_token, created_time, confirm_time, status = row

        # 轉成台北時間顯示
        now_tw = datetime.now(TW_TZ)

        if created_time is not None:
            if created_time.tzinfo is None:
                created_time_tw = created_time.replace(tzinfo=TW_TZ)
            else:
                created_time_tw = created_time.astimezone(TW_TZ)
        else:
            created_time_tw = None

        if confirm_time is not None:
            if confirm_time.tzinfo is None:
                confirm_time_tw = confirm_time.replace(tzinfo=TW_TZ)
            else:
                confirm_time_tw = confirm_time.astimezone(TW_TZ)
        else:
            confirm_time_tw = None

        # 已確認過
        if status == "Y":
            msg = "此電子郵件信箱已完成驗證。"
            if confirm_time_tw:
                msg += f"\\n確認時間：{confirm_time_tw.strftime('%Y-%m-%d %H:%M:%S')}"
            return render_confirm_page(
                title="已完成驗證",
                heading="信箱已確認",
                message=msg,
                icon="✓",
                icon_class="success"
            ), 200

        # 檢查是否過期：created_time + 24hr
        if created_time_tw is None:
            return render_confirm_page(
                title="驗證失敗",
                heading="資料異常",
                message="此驗證資料缺少建立時間，請重新申請驗證信。",
                icon="✕",
                icon_class="error"
            ), 400

        expire_time_tw = created_time_tw + timedelta(hours=24)

        if now_tw > expire_time_tw:
            return render_confirm_page(
                title="連結已失效",
                heading="連結已失效",
                message=(
                    "此連結已超過 24 小時有效期限。\\n"
                    "請使用最新的驗證信重新確認。"
                ),
                icon="✕",
                icon_class="error"
            ), 400

        # 更新為已確認
        cur.execute("""
            UPDATE confirm_tokens
            SET status = 'Y',
                confirm_time = %s
            WHERE id = %s
        """, (now_tw, row_id))
        conn.commit()

        return render_confirm_page(
            title="驗證成功",
            heading="電子郵件驗證成功",
            message=(
                "您的電子郵件信箱已完成確認。\\n"
                f"確認時間：{now_tw.strftime('%Y-%m-%d %H:%M:%S')}"
            ),
            icon="✓",
            icon_class="success"
        ), 200

    except Exception as e:
        if conn:
            conn.rollback()

        return render_confirm_page(
            title="系統錯誤",
            heading="系統處理失敗",
            message=f"系統發生錯誤：{str(e)}",
            icon="✕",
            icon_class="error"
        ), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
