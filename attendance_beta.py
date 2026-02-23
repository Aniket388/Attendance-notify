import os
import re
import time
import json
import base64
import argparse
import traceback
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
# 🛡️ BOT V10.0-BETA: ROBUST INFRASTRUCTURE TEST
# ====================================================

LOGIN_URL = "https://nietcloud.niet.co.in/login.htm"
BETA_TARGET_ID = "0231csiot122@niet.co.in" # 🔒 BETA LOCK ACTIVE

# 1. LOAD SECRETS
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()
MASTER_KEY   = os.environ.get("MASTER_KEY", "").strip().encode()
TOKEN_JSON   = os.environ.get("GMAIL_TOKEN_JSON", "").strip()

# 2. INIT CLIENTS
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
cipher = Fernet(MASTER_KEY)

# 🛡️ SAFE CLICK WRAPPER (Robustness)
def safe_click(driver, element):
    try:
        driver.execute_script("arguments[0].click();", element)
    except:
        element.click()

def get_personality(percentage):
    p = float(percentage)
    if p >= 90: return {"quote": "Absolute Legend! 🏆 Basically living at college.", "status": "Safe Zone", "color": "#3A7D68", "subject_icon": "🏆"}
    elif p >= 75: return {"quote": "You are Safe! Keep maintaining this flow.", "status": "On Track", "color": "#3A7D68", "subject_icon": "✅"}
    elif p >= 60: return {"quote": "You are on thin ice! Don't skip anymore classes.", "status": "Attendance is Low", "color": "#C27C2E", "subject_icon": "⚠️"}
    else: return {"quote": "DANGER ZONE! Run to college immediately!", "status": "Critical Low", "color": "#B94A40", "subject_icon": "🚨"}

def send_email_via_api(target_email, subject, html_content):
    print(f"   📧 Sending to {target_email}...")
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
        print("   ✅ Sent successfully!")
        return True
    except Exception as e:
        print(f"   ❌ API Send Failed: {e}")
        return False

def check_attendance_for_user(user, is_final_attempt=True):
    user_id = user['college_id']
    target_email = user['target_email']
    
    # 🛡️ FAILURE TRACKING (Robustness)
    current_fails = user.get('fail_count', 0)
    
    print(f"\n🔄 Processing: {user_id} (Current Fails: {current_fails})")
    
    try:
        college_pass = cipher.decrypt(user['encrypted_pass'].encode()).decode()
    except:
        print("   ❌ Decryption Failed")
        return

    # 🛡️ DEFENSIVE CHROME OPTIONS (Robustness)
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument('--ignore-certificate-errors')
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.set_capability("unhandledPromptBehavior", "accept")

    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.default_content_setting_values.notifications": 2,
        "profile.managed_default_content_settings.stylesheets": 2,
    }
    chrome_options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 30)
    
    final_percent = "N/A"
    parsed_subjects = [] 
    total_attended = 0
    total_delivered = 0
    
    yesterday_obj = datetime.now() - timedelta(days=1)
    yesterday_str = yesterday_obj.strftime("%b %d,%Y")

    try:
        # 1. LOGIN
        print("   ⏳ Logging in...")
        driver.get(LOGIN_URL)
        
        wait.until(EC.visibility_of_element_located((By.ID, "j_username"))).send_keys(user_id)
        driver.find_element(By.ID, "password-1").send_keys(college_pass)
        safe_click(driver, driver.find_element(By.CSS_SELECTOR, "button[type='submit']"))
        
        try:
            WebDriverWait(driver, 5).until(EC.alert_is_present())
            driver.switch_to.alert.accept()
        except: pass

        # 🛡️ HARDEN DASHBOARD READINESS (Robustness)
        print("   ⏳ Waiting for Dashboard (home.htm)...")
        wait.until(EC.url_contains("home.htm"))
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        
        # 🛡️ RESET FAILURE TRACKING ON SUCCESSFUL LOGIN
        if current_fails > 0:
            supabase.table("users").update({"fail_count": 0}).eq("college_id", user_id).execute()

        # 2. CLICK DASHBOARD WIDGET 
        print("   🧭 Scanning Dashboard for Attendance Block...")
        time.sleep(2) 
        
        # 🎯 DETERMINISTIC SCOPING: Only look at the text inside the Attendance widget
        try:
            xpath_query = "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'attendance')]/ancestor::*[contains(., '%')][1]"
            attendance_widget = wait.until(EC.presence_of_element_located((By.XPATH, xpath_query)))
            dash_text = attendance_widget.text
        except Exception:
            raise Exception("Could not locate the specific Attendance widget container on the dashboard.")
        
        # 🛡️ FLEXIBLE REGEX - SCOPED
        if p_match := re.search(r'(\d+(\.\d+)?)%', dash_text):
            final_percent = p_match.group(0)
            print(f"   📊 Found Scoped Percentage: {final_percent}")
            
            try:
                target = attendance_widget.find_element(By.XPATH, f".//*[contains(text(),'{final_percent}')]")
                safe_click(driver, target) 
            except:
                print("   ⚠️ Strict locator failed. Clicking widget body...")
                safe_click(driver, attendance_widget) 
                
            try: safe_click(driver, target.find_element(By.XPATH, ".."))
            except: pass
        else:
            raise Exception(f"Attendance percentage not found in scoped text: {dash_text}")

        # 3. WAIT FOR MAIN ATTENDANCE TABLE
        print("   ⏳ Waiting for Summary Table...")
        main_table_xpath = "//table[contains(., 'Course Name')]"
        wait.until(EC.presence_of_element_located((By.XPATH, main_table_xpath)))
        time.sleep(1)
        
        # 4. START SCRAPING (AJAX Flow)
        target_table = driver.find_element(By.XPATH, main_table_xpath)
        initial_rows = target_table.find_elements(By.TAG_NAME, "tr")
        row_count = len(initial_rows)
        
        print(f"   📋 Scanning {row_count} subjects...")

        for i in range(row_count):
            try:
                current_table = driver.find_element(By.XPATH, main_table_xpath)
                current_rows = current_table.find_elements(By.TAG_NAME, "tr")
                
                if i >= len(current_rows): break
                row = current_rows[i]
                cols = row.find_elements(By.TAG_NAME, "td")
                
                if len(cols) < 4: continue
                subj_name = cols[1].text.strip()
                if not subj_name: continue
                
                count_text = cols[-2].text.strip()
                per = cols[-1].text.strip()

                if "Total" in cols[0].text: continue 

                try:
                    parts = count_text.split('/')
                    if len(parts) == 2:
                        total_attended += int(parts[0])
                        total_delivered += int(parts[1])
                except: pass

                y_status = "No Class"

                try:
                    link_element = cols[-2].find_element(By.TAG_NAME, "a")
                    safe_click(driver, link_element) 
                    
                    clean_subj = subj_name.split()[0][:10] if subj_name else ""
                    detail_header_xpath = f"//*[contains(text(), 'Attendance Details') and contains(text(), '{clean_subj}')]"
                    
                    try:
                        wait.until(EC.presence_of_element_located((By.XPATH, detail_header_xpath)))
                    except:
                        detail_header_xpath = "//*[contains(text(), 'Attendance Details')]"
                        wait.until(EC.presence_of_element_located((By.XPATH, detail_header_xpath)))
                    
                    detail_table_xpath = f"({detail_header_xpath}/following::table)[1]"
                    
                    try:
                        detail_table = driver.find_element(By.XPATH, detail_table_xpath)
                    except:
                        all_tables = driver.find_elements(By.TAG_NAME, "table")
                        detail_table = all_tables[-1]
                        
                    detail_rows = detail_table.find_elements(By.TAG_NAME, "tr")
                    daily_statuses = []
                    
                    for d_row in reversed(detail_rows):
                        d_cols = d_row.find_elements(By.TAG_NAME, "td")
                        if len(d_cols) < 5: continue
                        
                        d_date_str = d_cols[1].text.strip()
                        d_stat = d_cols[4].text.strip() 
                        
                        if d_date_str == yesterday_str:
                            if d_stat == "P": daily_statuses.append("P")
                            else: daily_statuses.append("A")
                        
                        try:
                            current_row_date = datetime.strptime(d_date_str, "%b %d,%Y")
                            if current_row_date.date() < yesterday_obj.date(): break
                        except: pass
                        
                    if not daily_statuses: y_status = "No Class"
                    elif all(s == "P" for s in daily_statuses): y_status = "Present"
                    else: y_status = "Absent"
                        
                except Exception as e:
                    print(f"   ⚠️ Details scrape failed for {subj_name}")
                    y_status = "Error"
                
                parsed_subjects.append({
                    "name": subj_name,
                    "percent": per,
                    "count": count_text,
                    "yesterday": y_status
                })
            
            except Exception as row_e: continue

        # ==========================================
        # 🎨 BUILD MATTE MODERN HTML EMAIL
        # ==========================================
        try:
            val = float(re.search(r'\d+\.?\d*', final_percent).group())
            personality = get_personality(val)
        except: 
            personality = {"quote": "Attendance Updated", "status": "View Data", "color": "#1976d2", "subject_icon": "📅"}

        table_html = ""
        for subj in parsed_subjects:
            p_val = float(subj['percent']) if subj['percent'].replace('.','',1).isdigit() else 100
            p_color = "#B94A40" if p_val < 75 else "#3C4043" 
            p_weight = "600" if p_val < 75 else "500"

            if subj['yesterday'] == "Present":
                badge = "<span style='background-color:#E8F3F0; color:#2E6B58; padding:6px 12px; border-radius:16px; font-size:0.75em; font-weight:700; letter-spacing:0.3px; text-transform:uppercase;'>Present</span>"
            elif subj['yesterday'] == "Absent":
                badge = "<span style='background-color:#F7EBEA; color:#9E3F36; padding:6px 12px; border-radius:16px; font-size:0.75em; font-weight:700; letter-spacing:0.3px; text-transform:uppercase;'>Absent</span>"
            else:
                badge = "<span style='color:#9AA0A6; font-size:1.5em; line-height:0.8;'>-</span>"

            table_html += f"""
            <tr style="border-bottom: 1px solid #F1F3F4;">
                <td style="padding: 16px 20px; font-size: 0.9em; color: #3C4043; line-height: 1.4; font-weight:500; vertical-align:middle;">{subj['name']}</td>
                <td style="padding: 16px 20px; text-align: right; white-space: nowrap; vertical-align:middle;">
                    <div style="font-size: 1em; color: {p_color}; font-weight: {p_weight};">{subj['percent']}%</div>
                    <div style="font-size: 0.8em; color: #70757A; margin-top: 4px; font-weight: 500;">{subj['count']}</div>
                </td>
                <td style="padding: 16px 20px; text-align: right; white-space: nowrap; width: 90px; vertical-align:middle;">
                    {badge}
                </td>
            </tr>
            """

        subject_line = f"{personality['subject_icon']} {personality['status']}: {final_percent}"
        
        html_body = f"""
        <div style="background-color: #F8F9FA; padding: 30px 10px; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased;">
            <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); border: 1px solid rgba(0,0,0,0.05);">
                
                <div style="background-color: {personality['color']}; padding: 45px 30px; text-align: center;">
                    <h1 style="margin: 0; font-size: 4.5em; font-weight: 700; color: #ffffff; letter-spacing: -1.5px; line-height: 1;">{final_percent}</h1>
                    <div style="font-size: 1.4em; font-weight: 600; color: rgba(255,255,255,0.95); margin-top: 12px; letter-spacing: 0.5px;">{total_attended} / {total_delivered}</div>
                    <div style="font-size: 1.1em; color: rgba(255,255,255,0.85); font-weight: 600; margin-top: 10px; text-transform: uppercase; letter-spacing: 1.2px;">{personality['status']}</div>
                </div>

                <div style="background-color: #FFFFFF; padding: 20px 30px; text-align: center; border-bottom: 1px solid #F1F3F4;">
                    <p style="margin: 0; color: #5F6368; font-style: italic; font-size: 1em; font-weight: 400; line-height: 1.5;">
                        {personality['subject_icon']} "{personality['quote']}"
                    </p>
                </div>

                <table style="width: 100%; border-collapse: collapse; margin-top: 10px;">
                    <thead>
                        <tr>
                            <th style="padding: 12px 20px; text-align: left; font-size: 0.7em; text-transform: uppercase; color: #9AA0A6; font-weight: 700; letter-spacing: 0.8px;">Subject</th>
                            <th style="padding: 12px 20px; text-align: right; font-size: 0.7em; text-transform: uppercase; color: #9AA0A6; font-weight: 700; letter-spacing: 0.8px;">Overall</th>
                            <th style="padding: 12px 20px; text-align: right; font-size: 0.7em; text-transform: uppercase; color: #9AA0A6; font-weight: 700; letter-spacing: 0.8px;">Yesterday</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_html}
                    </tbody>
                </table>
                
                <div style="padding: 20px; text-align: center; font-size: 0.75em; color: #BDC1C6; border-top: 1px solid #F1F3F4; background-color: #FFFFFF;">
                    NIET Attendance Bot • <a href="https://attendance-notify.vercel.app/" style="color:#BDC1C6; text-decoration:underline;">Update Settings</a>
                </div>
            </div>
        </div>
        """
        
        send_email_via_api(target_email, subject_line, html_body)

    except Exception as e:
        print(f"   ❌ FATAL ERROR: {e}")
        traceback.print_exc()

        # 🛡️ SOFT RETRY ESCAPE (Don't log failure if it's going to retry)
        if not is_final_attempt:
            raise e 

        # 🛡️ 3-STRIKES FAILURE TRACKING
        new_fail = current_fails + 1

        if new_fail >= 3:
            print("   💀 3 Strikes. Deactivating.")
            supabase.table("users").update({
                "fail_count": new_fail,
                "is_active": False
            }).eq("college_id", user_id).execute()

            send_email_via_api(
                target_email,
                "Bot Deactivated",
                "<h1>Login Failed 3 Times</h1><p>Please update your password on the portal: <a href='https://attendance-notify.vercel.app/'>Update Settings</a>.</p>"
            )
        else:
            supabase.table("users").update({
                "fail_count": new_fail
            }).eq("college_id", user_id).execute()
        
    finally:
        driver.quit()

def main():
    # ⚡ SHARDING / LOAD BALANCING ARGUMENTS
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard_id", type=int, default=0, help="Current Worker ID (0, 1, 2...)")
    parser.add_argument("--total_shards", type=int, default=1, help="Total number of Workers")
    args = parser.parse_args()

    print(f"🚀 ROBUST BETA TEST STARTED")

    try:
        # 1. FETCH ONLY BETA USER 🔒
        response = supabase.table("users").select("*").eq("is_active", True).eq("college_id", BETA_TARGET_ID).execute()
        all_users = response.data
        
        if not all_users:
            print(f"   ⚠️ Beta User {BETA_TARGET_ID} not found or inactive.")
            return

        print(f"   ✅ Found Beta User. Starting robust test...")
        
        # 3. OUTER SHELL SOFT RETRY FOR EACH USER
        for user in all_users:
            for attempt in range(2):
                try:
                    check_attendance_for_user(user, is_final_attempt=(attempt == 1))
                    break
                except Exception as e:
                    print(f"   🔄 Retry attempt {attempt + 1} for {user['college_id']}")
                    if attempt == 1:
                        print(f"   ❌ Final failure for {user['college_id']}")
                    time.sleep(2)
            
    except Exception as e:
        print(f"🔥 CRITICAL ERROR: {e}")

if __name__ == "__main__":
    main()
