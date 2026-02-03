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
# 🎭 BOT V6.1: BETA EDITION (V6 Core + Yesterday's Report)
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

# 🧠 BRAIN: MOTIVATION LOGIC
def get_personality(percentage):
    p = float(percentage)
    if p >= 90:
        return {"quote": "Absolute Legend! 🏆 You basically live at college.", "status": "Safe Category", "color": "#388E3C", "subject_icon": "🏆"}
    elif p >= 75:
        return {"quote": "You are Safe! ✅ Keep maintaining this flow.", "status": "Safe Category", "color": "#388E3C", "subject_icon": "✅"}
    elif p >= 60:
        return {"quote": "⚠️ You are on thin ice! Don't skip anymore classes.", "status": "Attendance is Low", "color": "#F57C00", "subject_icon": "⚠️"}
    else:
        return {"quote": "🚨 DANGER ZONE! Run to college immediately!", "status": "CRITICAL LOW", "color": "#D32F2F", "subject_icon": "🚨"}

def send_email_via_api(target_email, subject, html_content):
    print(f"   📧 Sending via Gmail API to {target_email}...")
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
        print("   ✅ Sent successfully (API)!")
        return True
    except Exception as e:
        print(f"   ❌ API Send Failed: {e}")
        return False

def check_attendance_for_user(user):
    user_id = user['college_id']
    target_email = user['target_email']
    current_fails = user.get('fail_count', 0)
    
    print(f"\n🔄 Processing: {user_id} (Fail Count: {current_fails})")
    
    try:
        college_pass = cipher.decrypt(user['encrypted_pass'].encode()).decode()
    except:
        print("    ❌ Decryption Failed")
        return

    # BROWSER SETUP (Your Original Config)
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument('--ignore-certificate-errors')
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.set_capability("unhandledPromptBehavior", "accept")

    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.default_content_setting_values.notifications": 2,
        "profile.managed_default_content_settings.stylesheets": 2,
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 25)
    
    final_percent = "N/A"
    table_html = ""
    yesterday_updates = [] # 🆕 New Storage

    try:
        driver.get(LOGIN_URL)
        
        # POP-UP HANDLER 1
        try:
            WebDriverWait(driver, 3).until(EC.alert_is_present())
            driver.switch_to.alert.accept()
        except: pass

        wait.until(EC.visibility_of_element_located((By.ID, "j_username"))).send_keys(user_id)
        driver.find_element(By.ID, "password-1").send_keys(college_pass)
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        
        # POP-UP HANDLER 2
        try:
            WebDriverWait(driver, 3).until(EC.alert_is_present())
            driver.switch_to.alert.accept()
        except: pass

        wait.until(EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "Attendance"))
        print("    ✨ Login Success!")

        dash_text = driver.find_element(By.TAG_NAME, "body").text
        
        if p_match := re.search(r'(\d+\.\d+)%', dash_text):
            final_percent = p_match.group(0)
            print(f"    📊 Found: {final_percent}")
            
            # --- SCRAPING MAIN TABLE (Your Logic) ---
            try:
                xpath_query = f"//*[contains(text(),'{final_percent}')]"
                target = driver.find_element(By.XPATH, xpath_query)
                driver.execute_script("arguments[0].click();", target)
                try: driver.execute_script("arguments[0].click();", target.find_element(By.XPATH, ".."))
                except: pass
                
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "tr")))
                time.sleep(2)
                
                # 🆕 1. INITIALIZE COUNTERS
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
                        text_style = "color:#333;"
                        count_style = "color:#666; font-size: 0.85em;"
                        
                        is_total_row = False

                        if "Total" in cols[0].text: 
                            bg = "background-color:#f0f7ff; font-weight:bold; border-top: 2px solid #ddd;"
                            subj = "GRAND TOTAL"
                            text_style = "color:#000;"
                            is_total_row = True
                        
                        # Math Logic
                        if not is_total_row:
                            try:
                                parts = count_text.split('/')
                                if len(parts) == 2:
                                    total_attended += int(parts[0])
                                    total_delivered += int(parts[1])
                            except: pass

                        if float(per) < 75 and "TOTAL" not in subj: 
                            text_style = "color:#D32F2F; font-weight:bold;"
                            count_style = "color:#D32F2F; font-size: 0.85em;"
                        
                        table_html += f"""
                        <tr style='{bg}'>
                            <td style='padding:12px 5px; {text_style}'>{subj}</td>
                            <td style='text-align:right; padding:12px 5px;'>
                                <div style='{text_style}'>{per}%</div>
                                <div style='{count_style}'>{count_text}</div>
                            </td>
                        </tr>
                        """
            except: pass

            # ============================================================
            # 🆕 PART 2: YESTERDAY'S REPORT (Added Feature)
            # ============================================================
            print("    🕵️ Checking Yesterday's Attendance...")
            try:
                # Re-find subject rows to click into them
                subject_rows = driver.find_elements(By.XPATH, "//table[.//th[text()='Course Name']]//tr[td]")
                
                # LIMIT TO FIRST 4 SUBJECTS to prevent Timeout/Crash
                scan_limit = min(4, len(subject_rows))
                
                for i in range(scan_limit):
                    try:
                        # Refresh to avoid Stale Element
                        rows = driver.find_elements(By.XPATH, "//table[.//th[text()='Course Name']]//tr[td]")
                        if i >= len(rows): break
                        
                        cols = rows[i].find_elements(By.TAG_NAME, "td")
                        if len(cols) < 3: continue
                        subj_name = cols[1].text.strip()
                        
                        # Find Clickable Link
                        try: count_link = cols[2].find_element(By.TAG_NAME, "a")
                        except: continue 

                        # Click
                        driver.execute_script("arguments[0].click();", count_link)
                        time.sleep(1) # Short wait
                        
                        # Find Dates
                        details_rows = driver.find_elements(By.XPATH, "//table[.//th[text()='Date']]//tr[td]")
                        
                        # Check Latest Entry
                        if details_rows:
                            last_row_cols = details_rows[-1].find_elements(By.TAG_NAME, "td")
                            if len(last_row_cols) >= 5:
                                date_text = last_row_cols[1].text.strip()
                                status = last_row_cols[4].text.strip()
                                
                                # Logic: Is it yesterday?
                                entry_date = datetime.strptime(date_text, "%b %d, %Y").date()
                                yesterday = datetime.now().date() - timedelta(days=1)
                                
                                if entry_date == yesterday:
                                    icon = "✅" if status == "P" else "❌"
                                    yesterday_updates.append(f"<strong>{subj_name}</strong>: {icon} {status}")

                        # Go Back
                        driver.back()
                        time.sleep(1)
                        
                    except Exception as e:
                        driver.get(LOGIN_URL) # Reset if lost
                        continue
            except Exception as e:
                print(f"    ⚠️ Deep Dive Error (Skipping): {e}")

            # ============================================================
            # 🆕 PART 3: BUILD EMAIL (V6 Style + New Section)
            # ============================================================
            try:
                val = float(re.search(r'\d+\.?\d*', final_percent).group())
                personality = get_personality(val)
            except: 
                personality = {"quote": "Update", "status": "Update", "color": "#1976D2", "subject_icon": "📅"}

            subject_line = f"📅 Daily: {final_percent}"
            grand_total_text = f"{total_attended} / {total_delivered}"

            # New HTML Section
            y_html = ""
            if yesterday_updates:
                items = "".join([f"<li style='margin-bottom:5px;'>{u}</li>" for u in yesterday_updates])
                y_html = f"""
                <div style='background:#e3f2fd; padding:15px; border-radius:8px; margin-bottom:20px; border-left: 5px solid #2196F3;'>
                    <h3 style='margin-top:0; color:#1565C0; font-size:1.1em;'>📉 Yesterday's Updates</h3>
                    <ul style='padding-left:20px; margin-bottom:0;'>{items}</ul>
                </div>
                """
            else:
                 y_html = "<div style='text-align:center; color:#888; margin-bottom:20px; font-style:italic; font-size:0.9em;'>No classes found for yesterday.</div>"

            html_body = f"""
            <div style="font-family:'Segoe UI', sans-serif; max-width:500px; margin:auto; border:1px solid #e0e0e0; border-radius:12px; overflow:hidden;">
                
                <div style="background:{personality['color']}; padding:25px; text-align:center; color:white;">
                    <h1 style="margin:0; font-size:2.8em; font-weight:bold;">{final_percent}</h1>
                    <p style="margin:5px 0 0 0; font-size:1.4em; font-weight:bold; opacity:0.9;">{grand_total_text}</p>
                    <p style="margin:5px 0 0 0; font-size:1.1em; opacity:0.8;">{personality['status']}</p>
                </div>

                <div style="padding:20px;">
                    {y_html}
                    
                    <h3 style="color:#333; border-bottom:2px solid #eee; padding-bottom:10px;">Current Status</h3>
                    <table style="width:100%; border-collapse:collapse; font-size:0.9em;">
                        {table_html}
                    </table>
                </div>

                <div style="background:#fafafa; padding:15px; text-align:center; font-size:0.75em; color:#999;">
                    NIET Beta V6.1 • <a href="https://attendance-notify.vercel.app/" style="color:#999; text-decoration:underline;">Update Settings</a>
                </div>
            </div>
            """
            
            send_email_via_api(target_email, subject_line, html_body)
    
    except Exception as e:
        print(f"    ❌ Login/Scrape Error: {e}")
        # Not adding 'Fail Count' logic for beta to avoid locking account during tests

    finally:
        driver.quit()

def main():
    print(f"🚀 BOT V6.1 BETA STARTED")

    try:
        response = supabase.table("users").select("*").eq("is_active", True).execute()
        all_users = response.data
        
        # 🛡️ SAFETY LOCK: ONLY YOU
        my_users = [u for u in all_users if u['college_id'] in BETA_TESTERS]

        if not my_users:
            print("    ⚠️ No Beta Testers found.")
            return

        print(f"🧪 Running ONLY for: {BETA_TESTERS}")
        
        for user in my_users:
            check_attendance_for_user(user)
            
    except Exception as e:
        print(f"🔥 CRITICAL ERROR: {e}")

if __name__ == "__main__":
    main()
