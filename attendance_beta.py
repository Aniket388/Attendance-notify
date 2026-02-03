import os
import re
import time
import json
import base64
import argparse
import random
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
# 🎭 BOT V6.4: UNLIMITED SCAN EDITION
# ====================================================

# 🔒 SAFETY LOCK: Only runs for YOU
BETA_TESTERS = ["0231csiot122@niet.co.in"]

LOGIN_URL = "https://nietcloud.niet.co.in/login.htm"

# 1. LOAD SECRETS
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()
MASTER_KEY   = os.environ.get("MASTER_KEY", "").strip().encode()
TOKEN_JSON   = os.environ.get("GMAIL_TOKEN_JSON", "").strip()

# 2. INIT CLIENTS
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
cipher = Fernet(MASTER_KEY)

# 🚀 HELPER: Force print logs immediately
def log(msg):
    print(msg, flush=True)

def get_personality(percentage):
    p = float(percentage)
    if p >= 90: return {"quote": "Absolute Legend! 🏆", "status": "Safe", "color": "#388E3C"}
    elif p >= 75: return {"quote": "You are Safe! ✅", "status": "Safe", "color": "#388E3C"}
    elif p >= 60: return {"quote": "⚠️ Thin ice!", "status": "Low", "color": "#F57C00"}
    else: return {"quote": "🚨 DANGER ZONE!", "status": "CRITICAL", "color": "#D32F2F"}

def send_email_via_api(target_email, subject, html_content):
    log(f"   📧 Sending email to {target_email}...")
    try:
        creds_data = json.loads(TOKEN_JSON)
        creds = Credentials.from_authorized_user_info(creds_data)
        service = build('gmail', 'v1', credentials=creds)
        msg = MIMEMultipart("alternative")
        msg['Subject'] = subject
        msg['From'] = "me"
        msg['To'] = target_email
        msg.attach(MIMEText(html_content, "html", "utf-8"))
        raw_msg = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(userId="me", body={'raw': raw_msg}).execute()
        log("   ✅ Sent successfully!")
        return True
    except Exception as e:
        log(f"   ❌ API Send Failed: {e}")
        return False

def check_attendance_for_user(user):
    user_id = user['college_id']
    target_email = user['target_email']
    log(f"\n🔄 Beta Processing: {user_id}")
    
    try:
        college_pass = cipher.decrypt(user['encrypted_pass'].encode()).decode()
    except:
        log("    ❌ Decryption Failed")
        return

    # BROWSER SETUP
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument('--ignore-certificate-errors')
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-popup-blocking")
    
    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 25)
    
    final_percent = "N/A"
    table_html = ""
    yesterday_updates = []

    try:
        driver.get(LOGIN_URL)
        try: driver.switch_to.alert.accept()
        except: pass

        wait.until(EC.visibility_of_element_located((By.ID, "j_username"))).send_keys(user_id)
        driver.find_element(By.ID, "password-1").send_keys(college_pass)
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        try: driver.switch_to.alert.accept()
        except: pass

        wait.until(EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "Attendance"))
        log("    ✨ Login Success!")

        dash_text = driver.find_element(By.TAG_NAME, "body").text
        
        if p_match := re.search(r'(\d+\.\d+)%', dash_text):
            final_percent = p_match.group(0)
            
            # --- SCRAPE MAIN TABLE ---
            try:
                xpath_query = f"//*[contains(text(),'{final_percent}')]"
                target = driver.find_element(By.XPATH, xpath_query)
                driver.execute_script("arguments[0].click();", target)
                time.sleep(2)
                
                total_attended = 0
                total_delivered = 0
                rows = driver.find_elements(By.TAG_NAME, "tr")
                for row in rows:
                    cols = row.find_elements(By.TAG_NAME, "td")
                    if len(cols) >= 4:
                        subj = cols[1].text.strip()
                        if not subj: continue
                        count_text = cols[-2].text.strip()
                        per = cols[-1].text.strip()
                        
                        bg = "border-bottom:1px solid #eee;"
                        if "Total" in cols[0].text: 
                            bg = "background-color:#f0f7ff; font-weight:bold;"
                            subj = "GRAND TOTAL"
                        else:
                            try:
                                parts = count_text.split('/')
                                if len(parts) == 2:
                                    total_attended += int(parts[0])
                                    total_delivered += int(parts[1])
                            except: pass

                        table_html += f"<tr style='{bg}'><td style='padding:8px;'>{subj}</td><td style='text-align:right;'>{per}%<br><span style='color:#666;font-size:0.8em'>{count_text}</span></td></tr>"
            except: pass

            # ============================================================
            # 🆕 PART 2: YESTERDAY'S REPORT (UNLIMITED & SMART)
            # ============================================================
            log("    🕵️ Deep Dive: Scanning ALL Subjects...")
            try:
                # 1. Get total count first
                subject_rows = driver.find_elements(By.XPATH, "//table[.//th[text()='Course Name']]//tr[td]")
                total_subjects = len(subject_rows)
                
                # 2. Loop through EVERY subject
                for i in range(total_subjects):
                    try:
                        # Refresh elements
                        rows = driver.find_elements(By.XPATH, "//table[.//th[text()='Course Name']]//tr[td]")
                        if i >= len(rows): break
                        
                        cols = rows[i].find_elements(By.TAG_NAME, "td")
                        if len(cols) < 3: continue
                        subj_name = cols[1].text.strip()
                        
                        try: count_link = cols[2].find_element(By.TAG_NAME, "a")
                        except: continue 

                        log(f"       [{i+1}/{total_subjects}] Checking: {subj_name}...")
                        driver.execute_script("arguments[0].click();", count_link)
                        time.sleep(1) # Keeping it fast
                        
                        details_rows = driver.find_elements(By.XPATH, "//table[.//th[text()='Date']]//tr[td]")
                        
                        # 🛠️ SMART BACKWARDS SCAN
                        if details_rows:
                            for detail in reversed(details_rows):
                                d_cols = detail.find_elements(By.TAG_NAME, "td")
                                if len(d_cols) >= 5:
                                    date_text = d_cols[1].text.strip()
                                    status = d_cols[4].text.strip()
                                    
                                    try:
                                        entry_date = datetime.strptime(date_text, "%b %d, %Y").date()
                                        today = datetime.now().date()
                                        yesterday = today - timedelta(days=1)
                                        
                                        # Skip today, keep looking back
                                        if entry_date == today: continue 
                                        
                                        # MATCH!
                                        if entry_date == yesterday:
                                            icon = "✅" if status == "P" else "❌"
                                            yesterday_updates.append(f"<strong>{subj_name}</strong>: {icon} {status}")
                                            log(f"          🎯 FOUND: {status}")
                                            break 
                                        
                                        # Too old, stop checking this subject
                                        if entry_date < yesterday: break 
                                    except: continue

                        driver.back()
                        time.sleep(1)
                        
                    except Exception as e:
                        driver.get(LOGIN_URL) 
                        continue
            except Exception as e:
                log(f"    ⚠️ Deep Dive Error: {e}")

            # ============================================================
            # 🆕 PART 3: BUILD EMAIL
            # ============================================================
            try:
                val = float(re.search(r'\d+\.?\d*', final_percent).group())
                personality = get_personality(val)
            except: 
                personality = {"quote": "Update", "status": "Update", "color": "#1976D2"}

            subject_line = f"📅 Daily: {final_percent}"
            grand_total_text = f"{total_attended} / {total_delivered}"

            y_html = ""
            if yesterday_updates:
                items = "".join([f"<li style='margin-bottom:5px;'>{u}</li>" for u in yesterday_updates])
                y_html = f"<div style='background:#e3f2fd; padding:10px; border-left: 5px solid #2196F3;'><h3>📉 Yesterday's Updates</h3><ul>{items}</ul></div>"
            else:
                 y_html = "<div style='text-align:center; color:#888; font-style:italic;'>No classes found for yesterday.</div>"

            html_body = f"""
            <div style="font-family:sans-serif; max-width:500px; margin:auto; border:1px solid #ddd; border-radius:10px; overflow:hidden;">
                <div style="background:{personality['color']}; padding:20px; text-align:center; color:white;">
                    <h1>{final_percent}</h1>
                    <p>{grand_total_text}</p>
                </div>
                <div style="padding:20px;">
                    {y_html}
                    <h3>Current Status</h3>
                    <table style="width:100%; border-collapse:collapse;">
                        {table_html}
                    </table>
                </div>
            </div>
            """
            
            send_email_via_api(target_email, subject_line, html_body)
    
    except Exception as e:
        log(f"    ❌ Login/Scrape Error: {e}")

    finally:
        driver.quit()

def main():
    log(f"🚀 BOT V6.4 BETA STARTED")
    try:
        response = supabase.table("users").select("*").eq("is_active", True).execute()
        all_users = response.data
        my_users = [u for u in all_users if u['college_id'] in BETA_TESTERS]

        if not my_users:
            log("    ⚠️ No Beta Testers found.")
            return

        log(f"🧪 Running ONLY for: {BETA_TESTERS}")
        for user in my_users:
            check_attendance_for_user(user)
            
    except Exception as e:
        log(f"🔥 CRITICAL ERROR: {e}")

if __name__ == "__main__":
    main()
