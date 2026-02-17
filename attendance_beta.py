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
# 🛡️ BOT V8.5: ENGINEERING STANDARD
# ====================================================

LOGIN_URL = "https://nietcloud.niet.co.in/login.htm"
ATTENDANCE_URL = "https://nietcloud.niet.co.in/studentCourseFileNew.htm"
BETA_TARGET_ID = "0231csiot122@niet.co.in" 

# 1. LOAD SECRETS
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()
MASTER_KEY   = os.environ.get("MASTER_KEY", "").strip().encode()
TOKEN_JSON   = os.environ.get("GMAIL_TOKEN_JSON", "").strip()

# 2. INIT CLIENTS
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
cipher = Fernet(MASTER_KEY)

def get_personality(percentage):
    p = float(percentage)
    if p >= 90: return {"quote": "Absolute Legend! 🏆", "status": "Safe", "color": "#388E3C", "subject_icon": "🏆"}
    elif p >= 75: return {"quote": "You are Safe! ✅", "status": "Safe", "color": "#388E3C", "subject_icon": "✅"}
    elif p >= 60: return {"quote": "⚠️ Thin ice!", "status": "Low", "color": "#F57C00", "subject_icon": "⚠️"}
    else: return {"quote": "🚨 DANGER ZONE!", "status": "CRITICAL", "color": "#D32F2F", "subject_icon": "🚨"}

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

def check_attendance_for_user(user):
    user_id = user['college_id']
    target_email = user['target_email']
    
    print(f"\n🔄 Processing: {user_id}")
    
    try:
        college_pass = cipher.decrypt(user['encrypted_pass'].encode()).decode()
    except:
        print("   ❌ Decryption Failed")
        return

    # BROWSER SETUP
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument('--ignore-certificate-errors')
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 30)
    
    final_percent = "N/A"
    main_table_rows_html = ""
    yesterday_data = {} 
    
    yesterday_obj = datetime.now() - timedelta(days=1)
    yesterday_str = yesterday_obj.strftime("%b %d,%Y")

    try:
        # 1. LOGIN
        print("   ⏳ Logging in...")
        driver.get(LOGIN_URL)
        
        wait.until(EC.visibility_of_element_located((By.ID, "j_username"))).send_keys(user_id)
        driver.find_element(By.ID, "password-1").send_keys(college_pass)
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        
        try:
            WebDriverWait(driver, 5).until(EC.alert_is_present())
            driver.switch_to.alert.accept()
        except: pass

        # 🚀 FORCE NAVIGATION
        print("   🚀 Redirecting to Attendance Page...")
        time.sleep(2) 
        driver.get(ATTENDANCE_URL)
        
        # 🛡️ HARDENED WAIT: LOOK FOR DATA TABLE, NOT JUST TEXT
        print("   ⏳ Waiting for Table Structure...")
        # Looks for a table that specifically contains the header 'Course Name'
        # This avoids picking up sidebar tables or layout tables.
        main_table_xpath = "//table[contains(., 'Course Name')]"
        wait.until(EC.presence_of_element_located((By.XPATH, main_table_xpath)))
        
        # 2. GET TOTAL PERCENTAGE (SCOPED)
        # We find the table first to avoid "100% Profile" noise
        target_table = driver.find_element(By.XPATH, main_table_xpath)
        table_text = target_table.text
        
        if p_match := re.search(r'(\d+\.\d+)%', table_text):
            final_percent = p_match.group(0)
            print(f"   📊 Found Percentage (Scoped): {final_percent}")
            
            # ====================================================
            # 🕵️ DEEP SCRAPING (SCOPED & ITERATIVE)
            # ====================================================
            
            # 🛡️ SCOPED SELECTION: Only get rows from the Target Table
            initial_rows = target_table.find_elements(By.TAG_NAME, "tr")
            row_count = len(initial_rows)

            print(f"   📋 Scanning {row_count} rows in Target Table...")

            for i in range(row_count):
                try:
                    # RE-FIND TABLE to handle Stale Elements
                    # We must re-scope to the specific table every time
                    current_table = driver.find_element(By.XPATH, main_table_xpath)
                    current_rows = current_table.find_elements(By.TAG_NAME, "tr")
                    
                    if i >= len(current_rows): break
                    
                    row = current_rows[i]
                    cols = row.find_elements(By.TAG_NAME, "td")
                    
                    if len(cols) < 4: continue
                    subj_name = cols[1].text.strip()
                    if not subj_name: continue
                    
                    # Handle Grand Total Row
                    if "Total" in cols[0].text:
                        main_table_rows_html += f"""
                        <tr style='background-color:#f0f7ff; font-weight:bold; border-top: 2px solid #ddd;'>
                           <td style='padding:8px 4px; color:#000; font-size:0.9em;'>GRAND TOTAL</td>
                           <td style='text-align:right; padding:8px 4px; font-size:0.9em;'>{cols[-1].text.strip()}%</td>
                        </tr>"""
                        continue

                    count_text = cols[-2].text.strip()
                    per = cols[-1].text.strip()
                    
                    # Math for delivered/attended
                    try:
                        parts = count_text.split('/')
                        # (Optional: Add your math total tracking here if you want grand totals calculated manually)
                    except: pass
                    
                    color_style = "color:#333;"
                    if float(per) < 75: color_style = "color:#D32F2F; font-weight:bold;"
                    
                    main_table_rows_html += f"""
                    <tr style='border-bottom:1px solid #eee;'>
                        <td style='padding:8px 4px; {color_style}'>{subj_name}</td>
                        <td style='text-align:right; padding:8px 4px; {color_style}'>
                            {per}% <span style='font-size:0.8em; color:#999;'>({count_text})</span>
                        </td>
                    </tr>"""

                    # CLICK & CHECK YESTERDAY
                    try:
                        link_element = cols[-2].find_element(By.TAG_NAME, "a")
                        driver.execute_script("arguments[0].click();", link_element)
                        time.sleep(1.5)
                        
                        # Find the NEW details table that appeared (usually last in DOM)
                        all_tables = driver.find_elements(By.TAG_NAME, "table")
                        detail_rows = all_tables[-1].find_elements(By.TAG_NAME, "tr")
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
                            
                        if not daily_statuses: yesterday_data[subj_name] = "No Class"
                        elif all(s == "P" for s in daily_statuses): yesterday_data[subj_name] = "Present"
                        else: yesterday_data[subj_name] = "Absent"
                            
                        # RECOVERY
                        try:
                            driver.back()
                            # Wait for Main Table to reappear
                            wait.until(EC.presence_of_element_located((By.XPATH, main_table_xpath)))
                            time.sleep(0.5)
                        except:
                            driver.get(ATTENDANCE_URL) 
                            wait.until(EC.presence_of_element_located((By.XPATH, main_table_xpath)))
                        
                    except Exception:
                        yesterday_data[subj_name] = "Error"
                        if "studentCourseFileNew" not in driver.current_url: driver.get(ATTENDANCE_URL)
                
                except Exception: continue

            # --- BUILD EMAIL ---
            yesterday_rows_html = ""
            for subj, status in yesterday_data.items():
                bg_color = "transparent"
                text_color = "#333"
                if status == "Present": text_color = "#388E3C"
                elif status == "Absent": text_color = "#D32F2F"; bg_color = "#ffebee"
                elif status == "No Class": text_color = "#999"

                yesterday_rows_html += f"""
                <tr>
                    <td style='padding:6px; font-size:0.85em; color:#555;'>{subj}</td>
                    <td style='padding:6px; font-size:0.85em; font-weight:bold; text-align:right; color:{text_color}; background:{bg_color}; border-radius:4px;'>{status}</td>
                </tr>"""
            
            if not yesterday_rows_html:
                yesterday_rows_html = "<tr><td colspan='2' style='text-align:center; color:#999; padding:10px;'>No classes yesterday</td></tr>"

            try:
                val = float(re.search(r'\d+\.?\d*', final_percent).group())
                personality = get_personality(val)
            except: 
                personality = {"quote": "Update", "status": "Update", "color": "#1976D2", "subject_icon": "📅"}

            subject_line = f"{personality['subject_icon']} Attendance: {final_percent}"
            # You can calculate total_attended / total_delivered manually if needed, 
            # or rely on the extraction if you added it.
            grand_total_text = "See Details" 

            html_body = f"""
            <div style="font-family:'Segoe UI', sans-serif; max-width:600px; margin:auto; border:1px solid #e0e0e0; border-radius:12px; overflow:hidden;">
                <div style="background:{personality['color']}; padding:20px; text-align:center; color:white;">
                    <h1 style="margin:0; font-size:2.5em; font-weight:bold;">{final_percent}</h1>
                    <p style="margin:5px 0 0 0; font-size:1.2em; opacity:0.9;">{personality['status']}</p>
                </div>
                <table style="width:100%; border-collapse:collapse;">
                    <tr>
                        <td style="width:60%; vertical-align:top; padding:0; border-right:1px solid #eee;">
                            <div style="padding:10px; background:#f9f9f9; border-bottom:1px solid #eee; font-weight:bold; color:#555; font-size:0.9em;">CURRENT STATUS</div>
                            <table style="width:100%; border-collapse:collapse; font-size:0.9em;">{main_table_rows_html}</table>
                        </td>
                        <td style="width:40%; vertical-align:top; padding:0; background:#fafafa;">
                            <div style="padding:10px; background:#eee; border-bottom:1px solid #ddd; font-weight:bold; color:#555; font-size:0.9em;">YESTERDAY ({yesterday_str})</div>
                            <table style="width:100%; border-collapse:collapse;">{yesterday_rows_html}</table>
                        </td>
                    </tr>
                </table>
                <div style="padding:15px; text-align:center; background:#fff; border-top:1px solid #eee; font-style:italic; color:#666;">"{personality['quote']}"</div>
                <div style="background:#f5f5f5; padding:10px; text-align:center; font-size:0.7em; color:#aaa;">Bot V8.5 • Engineering Standard</div>
            </div>
            """
            send_email_via_api(target_email, subject_line, html_body)

        else:
            print("   ⚠️ Percentage not found in table.")

    except Exception as e:
        print(f"   ❌ FATAL ERROR: {e}")
        traceback.print_exc()
        
    finally:
        driver.quit()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard_id", type=int, default=0)
    parser.add_argument("--total_shards", type=int, default=1)
    args = parser.parse_args()

    print(f"🚀 BOT V8.5 STARTED")

    try:
        response = supabase.table("users").select("*").eq("is_active", True).eq("college_id", BETA_TARGET_ID).execute()
        all_users = response.data
        if not all_users:
            print(f"   ⚠️ Beta User {BETA_TARGET_ID} not found or inactive.")
            return

        print(f"   ✅ Found Beta User. Starting...")
        for user in all_users:
            check_attendance_for_user(user)
            
    except Exception as e:
        print(f"🔥 CRITICAL ERROR: {e}")

if __name__ == "__main__":
    main()
