# ====================================================
# 🚀 BOT V10.1 (FULL + FIXED SCRAPER + BETA LOCK)
# ====================================================

import os, re, time, json, base64, argparse, traceback
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from supabase import create_client, Client
from cryptography.fernet import Fernet
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

LOGIN_URL = "https://nietcloud.niet.co.in/login.htm"

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()
MASTER_KEY   = os.environ.get("MASTER_KEY", "").strip().encode()
TOKEN_JSON   = os.environ.get("GMAIL_TOKEN_JSON", "").strip()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
cipher = Fernet(MASTER_KEY)

# =============================
# HELPERS
# =============================

def safe_click(driver, el):
    try:
        driver.execute_script("arguments[0].click();", el)
    except:
        el.click()

def send_email_via_api(target_email, subject, html):
    try:
        creds = Credentials.from_authorized_user_info(json.loads(TOKEN_JSON))
        service = build('gmail', 'v1', credentials=creds)

        msg = MIMEMultipart("alternative")
        msg['Subject'] = subject
        msg['From'] = "me"
        msg['To'] = target_email
        msg.attach(MIMEText(html, "html", "utf-8"))

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(userId="me", body={'raw': raw}).execute()
        return True
    except Exception as e:
        print("Mail error:", e)
        return False

# =============================
# 🔥 FIXED NAVIGATION
# =============================

def open_attendance(driver, wait):
    try:
        el = wait.until(EC.element_to_be_clickable((
            By.XPATH, "//div[contains(.,'Attendance') and contains(.,'%')]"
        )))
        safe_click(driver, el)
    except:
        safe_click(driver, wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//a[contains(.,'SYLLABUS')]")
        )))
        safe_click(driver, wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//*[text()='Attendance']")
        )))

    wait.until(EC.presence_of_element_located((
        By.XPATH, "//table"
    )))

# =============================
# 🔥 FIXED DETAIL SCRAPER
# =============================

def get_yesterday(driver, wait, cell, yesterday):
    before = driver.current_url

    safe_click(driver, cell)
    time.sleep(1)

    tables = driver.find_elements(By.TAG_NAME, "table")
    detail = None

    for t in reversed(tables):
        if "Date" in t.text and "Status" in t.text:
            detail = t
            break

    if not detail:
        return "Error"

    statuses = []

    for r in detail.find_elements(By.TAG_NAME, "tr"):
        cols = r.find_elements(By.TAG_NAME, "td")
        if len(cols) < 5:
            continue

        d = cols[1].text.strip()
        s = cols[4].text.strip().upper()

        if d == yesterday:
            statuses.append(s)

    # close
    if driver.current_url != before:
        driver.back()
    else:
        try:
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        except:
            pass

    if not statuses:
        return "No Class"

    return "Present" if all(x == "P" for x in statuses) else "Absent"

# =============================
# MAIN SCRAPER
# =============================

def check_attendance_for_user(user, is_final_attempt=True):

    user_id = user['college_id']
    target_email = user['target_email']
    fails = user.get("fail_count", 0)

    print(f"\nProcessing {user_id}")

    try:
        password = cipher.decrypt(user['encrypted_pass'].encode()).decode()
    except:
        return

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")

    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 25)

    yesterday = (datetime.now() - timedelta(days=1)).strftime("%b %d,%Y")

    parsed = []
    total_a, total_d = 0, 0
    final_percent = "N/A"

    try:
        # LOGIN
        driver.get(LOGIN_URL)
        wait.until(EC.presence_of_element_located((By.ID, "j_username"))).send_keys(user_id)
        driver.find_element(By.ID, "password-1").send_keys(password)
        safe_click(driver, driver.find_element(By.CSS_SELECTOR, "button[type='submit']"))

        wait.until(EC.url_contains("home.htm"))

        # RESET FAIL COUNT
        if fails > 0:
            supabase.table("users").update({"fail_count": 0}).eq("college_id", user_id).execute()

        # OPEN ATTENDANCE
        open_attendance(driver, wait)

        table = wait.until(EC.presence_of_element_located((By.XPATH, "//table")))
        rows = table.find_elements(By.TAG_NAME, "tr")

        for row in rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) < 6:
                continue

            name = cols[2].text.strip()
            count = cols[4].text.strip()
            percent = cols[5].text.strip()

            if not name:
                continue

            if "%" in percent:
                final_percent = percent

            try:
                a, d = count.split("/")
                total_a += int(a)
                total_d += int(d)
            except:
                pass

            status = get_yesterday(driver, wait, cols[4], yesterday)

            parsed.append({
                "name": name,
                "percent": percent,
                "count": count,
                "yesterday": status
            })

        # SIMPLE EMAIL (keep your old if needed)
        html = f"<h1>{final_percent}</h1><p>{total_a}/{total_d}</p>"
        send_email_via_api(target_email, f"Attendance {final_percent}", html)

    except Exception as e:
        print("ERROR:", e)

        if is_final_attempt:
            new_fail = fails + 1

            if new_fail >= 3:
                supabase.table("users").update({
                    "fail_count": new_fail,
                    "is_active": False
                }).eq("college_id", user_id).execute()
            else:
                supabase.table("users").update({
                    "fail_count": new_fail
                }).eq("college_id", user_id).execute()
        else:
            raise e

    finally:
        driver.quit()

# =============================
# MAIN
# =============================

def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("--shard_id", type=int, default=0)
    parser.add_argument("--total_shards", type=int, default=1)
    args = parser.parse_args()

    # 🔒 BETA LOCK
    BETA_USER = "0231csiot122@niet.co.in"

    response = supabase.table("users") \
        .select("*") \
        .eq("is_active", True) \
        .eq("college_id", BETA_USER) \
        .execute()

    users = response.data

    print("Users:", len(users))

    for user in users:
        for attempt in range(2):
            try:
                check_attendance_for_user(user, is_final_attempt=(attempt == 1))
                break
            except:
                time.sleep(2)

if __name__ == "__main__":
    main()
