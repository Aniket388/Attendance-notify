import os
import re
import time
import json
import base64
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from supabase import create_client, Client
from cryptography.fernet import Fernet
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# ====================================================
# 🚀 BOT V6.5 BETA — FAST + YESTERDAY INTEL
# ====================================================

LOGIN_URL = "https://nietcloud.niet.co.in/login.htm"
BETA_TESTERS = ["0231csiot122@niet.co.in"]

# ENV
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()
MASTER_KEY   = os.environ.get("MASTER_KEY", "").strip().encode()
TOKEN_JSON   = os.environ.get("GMAIL_TOKEN_JSON", "").strip()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
cipher = Fernet(MASTER_KEY)

# ----------------------------------------------------
# 🧠 PERSONALITY
# ----------------------------------------------------
def get_personality(p):
    p = float(p)
    if p >= 75:
        return {"status": "Safe", "color": "#388E3C"}
    elif p >= 60:
        return {"status": "Low", "color": "#F57C00"}
    return {"status": "CRITICAL", "color": "#D32F2F"}

# ----------------------------------------------------
# 📧 EMAIL
# ----------------------------------------------------
def send_email(target, subject, html):
    creds = Credentials.from_authorized_user_info(json.loads(TOKEN_JSON))
    service = build("gmail", "v1", credentials=creds)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = "me"
    msg["To"] = target
    msg.attach(MIMEText(html, "html"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()

# ----------------------------------------------------
# 🤖 CORE
# ----------------------------------------------------
def check_user(user):
    uid = user["college_id"]
    email = user["target_email"]

    print(f"\n🧪 Beta Scan: {uid}")

    try:
        password = cipher.decrypt(user["encrypted_pass"].encode()).decode()
    except:
        print("❌ Password decrypt failed")
        return

    # ⚡ FAST CHROME
    opt = Options()
    opt.add_argument("--headless")
    opt.add_argument("--no-sandbox")
    opt.add_argument("--disable-dev-shm-usage")
    opt.add_argument("--window-size=1920,1080")
    opt.add_argument("--disable-popup-blocking")
    opt.set_capability("unhandledPromptBehavior", "accept")

    opt.add_experimental_option("prefs", {
        "profile.managed_default_content_settings.images": 2,
        "profile.managed_default_content_settings.stylesheets": 2,
        "profile.default_content_setting_values.notifications": 2,
    })

    driver = webdriver.Chrome(options=opt)
    wait = WebDriverWait(driver, 20)

    table_html = ""
    yesterday_updates = []
    total_attended = total_delivered = 0

    try:
        # LOGIN
        driver.get(LOGIN_URL)
        try: driver.switch_to.alert.accept()
        except: pass

        wait.until(EC.visibility_of_element_located((By.ID, "j_username"))).send_keys(uid)
        driver.find_element(By.ID, "password-1").send_keys(password)
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

        wait.until(EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "Attendance"))

        dash = driver.find_element(By.TAG_NAME, "body").text
        match = re.search(r'(\d+\.\d+)%', dash)
        if not match:
            return

        percent = match.group(1)

        # OPEN ATTENDANCE
        driver.find_element(By.XPATH, f"//*[contains(text(),'{percent}%')]").click()
        time.sleep(1.5)

        # ---------------------------
        # 📊 MAIN TABLE (FAST)
        # ---------------------------
        rows = driver.find_elements(By.TAG_NAME, "tr")
        for r in rows:
            c = r.find_elements(By.TAG_NAME, "td")
            if len(c) < 4:
                continue

            subj = c[1].text.strip()
            if not subj:
                continue

            count = c[-2].text.strip()
            per = c[-1].text.strip()

            if "Total" not in c[0].text:
                try:
                    a, d = map(int, count.split("/"))
                    total_attended += a
                    total_delivered += d
                except:
                    pass
            else:
                subj = "GRAND TOTAL"

            table_html += f"""
            <tr>
                <td>{subj}</td>
                <td align="right">{per}%<br><small>{count}</small></td>
            </tr>
            """

        # ---------------------------
        # 🕵️ YESTERDAY SCAN (OPTIMIZED)
        # ---------------------------
        subjects = driver.find_elements(By.XPATH, "//table[.//th[text()='Course Name']]//tr[td]")
        yesterday = datetime.now().date() - timedelta(days=1)

        for row in subjects:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) < 3:
                continue

            name = cols[1].text.strip()
            try:
                cols[2].find_element(By.TAG_NAME, "a").click()
            except:
                continue

            time.sleep(0.8)

            logs = driver.find_elements(By.XPATH, "//table[.//th[text()='Date']]//tr[td]")
            for l in reversed(logs):
                d = l.find_elements(By.TAG_NAME, "td")
                try:
                    date = datetime.strptime(d[1].text.strip(), "%b %d, %Y").date()
                    if date == yesterday:
                        status = d[4].text.strip()
                        icon = "✅" if status == "P" else "❌"
                        yesterday_updates.append(f"<li>{name}: {icon} {status}</li>")
                        break
                    if date < yesterday:
                        break
                except:
                    continue

            driver.back()
            time.sleep(0.6)

        # ---------------------------
        # 📧 EMAIL
        # ---------------------------
        personality = get_personality(percent)

        y_html = (
            "<ul>" + "".join(yesterday_updates) + "</ul>"
            if yesterday_updates else
            "<i>No classes yesterday</i>"
        )

        html = f"""
        <div style="font-family:sans-serif;max-width:480px;margin:auto">
            <div style="background:{personality['color']};color:white;padding:20px;text-align:center">
                <h1>{percent}%</h1>
                <p>{total_attended} / {total_delivered}</p>
            </div>
            <div style="padding:15px">
                <h3>Yesterday</h3>
                {y_html}
                <h3>Overall</h3>
                <table width="100%">{table_html}</table>
            </div>
        </div>
        """

        send_email(email, f"📅 Attendance {percent}%", html)

    finally:
        driver.quit()

# ----------------------------------------------------
# ▶️ ENTRY
# ----------------------------------------------------
def main():
    users = supabase.table("users").select("*").eq("is_active", True).execute().data
    beta_users = [u for u in users if u["college_id"] in BETA_TESTERS]

    if not beta_users:
        print("⚠️ No beta users found")
        return

    for u in beta_users:
        check_user(u)

if __name__ == "__main__":
    main()
