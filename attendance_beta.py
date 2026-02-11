import os
import re
import time
import json
import base64
import argparse
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
# 🎭 BOT V7.4 (BETA): EXACT STATUS LOGIC
# ====================================================

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
    
    print(f"\n🔄 Processing: {user_id}")
    
    try:
        college_pass = cipher.decrypt(user['encrypted_pass'].encode()).decode()
    except:
        print("    ❌ Decryption Failed")
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
    overall_subjects = [] 
    yesterday_html_rows = ""
    has_yesterday_data = False

    try:
        driver.get(LOGIN_URL)
        
        # POP-UP HANDLER
        try:
            WebDriverWait(driver, 3).until(EC.alert_is_present())
            driver.switch_to.alert.accept()
        except: pass

        wait.until(EC.visibility_of_element_located((By.ID, "j_username"))).send_keys(user_id)
        driver.find_element(By.ID, "password-1").send_keys(college_pass)
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        
        try:
            WebDriverWait(driver, 5).until(EC.alert_is_present())
            driver.switch_to.alert.accept()
        except: pass

        wait.until(EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "Attendance"))
        
        # --- 1. GET TOTAL PERCENTAGE ---
        dash_text = driver.find_element(By.TAG_NAME, "body").text
        if p_match := re.search(r'(\d+\.\d+)%', dash_text):
            final_percent = p_match.group(0)
            print(f"    📊 Found Total: {final_percent}")

        # --- 2. PREPARE YESTERDAY'S DATE ---
        yesterday_obj = (datetime.now() - timedelta(days=1))
        date_str_full = yesterday_obj.strftime("%b %d, %Y").replace(" 0", " ") 
        print(f"    📅 Hunting for date: {date_str_full}")

        # --- 3. PHASE 1: SAFE SCRAPE (Get Main Table First) ---
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "tr")))
        rows = driver.find_elements(By.CSS_SELECTOR, "tr")
        
        for row in rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 4:
                subj_name = cols[1].text.strip()
                # Skip header, empty rows, or Total row
                if "TOTAL" in subj_name.upper() or not subj_name or "Course Name" in subj_name: continue
                
                count_text = cols[2].text.strip() # 4/16
                per_text = cols[3].text.strip()   # 25.00
                
                # 🛡️ FILTER: Check if 'per_text' is actually a number
                try:
                    float(per_text)
                except ValueError:
                    continue 
                
                # Save to list
                overall_subjects.append({
                    "name": subj_name,
                    "count": count_text,
                    "percent": per_text
                })

        print(f"    ✅ Scraped {len(overall_subjects)} subjects. Now checking details...")

        # --- 4. PHASE 2: CLICK COUNTS & CHECK YESTERDAY ---
        for subj in overall_subjects:
            try:
                # Re-find row by subject name
                xpath_query = f"//td[contains(text(), '{subj['name']}')]/.."
                row = driver.find_element(By.XPATH, xpath_query)
                cols = row.find_elements(By.TAG_NAME, "td")
                
                # Click the "Count" link (3rd Column)
                link = cols[2].find_element(By.TAG_NAME, "a")
                driver.execute_script("arguments[0].click();", link)
                
                time.sleep(1.5)
                
                # Search for Yesterday's Date
                date_xpath = f"//td[contains(text(), '{date_str_full}')]"
                found_date_cells = driver.find_elements(By.XPATH, date_xpath)
                
                status_yesterday = None
                
                if found_date_cells:
                    # Get the row where the date was found
                    date_row = found_date_cells[0].find_element(By.XPATH, "./..")
                    
                    # Look at the 5th column (Index 4) for Status
                    # Based on your screenshot, it's: Sr | Date | Time | Session | Status | Punch In...
                    d_cols = date_row.find_elements(By.TAG_NAME, "td")
                    
                    if len(d_cols) > 4:
                        status_text = d_cols[4].text.strip()
                        
                        # LOGIC: P = Present, Anything else = Absent
                        if "P" in status_text:
                            status_yesterday = "✅ Present"
                        else:
                            status_yesterday = "❌ Absent"

                if status_yesterday:
                    has_yesterday_data = True
                    color = "#388E3C" if "Present" in status_yesterday else "#D32F2F"
                    yesterday_html_rows += f"""
                    <tr>
                        <td style="padding:8px; border-bottom:1px solid #eee; font-size:0.9em; color:#555;">{subj['name']}</td>
                        <td style="padding:8px; border-bottom:1px solid #eee; text-align:right; font-weight:bold; color:{color};">{status_yesterday}</td>
                    </tr>
                    """
            except Exception as e:
                pass 

        # --- 5. BUILD FINAL EMAIL ---
        table_html = ""
        total_attended = 0
        total_delivered = 0

        for subj in overall_subjects:
            try:
                parts = subj['count'].split('/')
                total_attended += int(parts[0])
                total_delivered += int(parts[1])
            except: pass

            bg = "border-bottom:1px solid #eee;"
            text_style = "color:#333;"
            try:
                if float(subj['percent']) < 75:
                    text_style = "color:#D32F2F; font-weight:bold;"
            except: pass
            
            table_html += f"""
            <tr style='{bg}'>
                <td style='padding:10px; {text_style}'>{subj['name']}</td>
                <td style='text-align:right; padding:10px;'>
                    <div style='{text_style}'>{subj['percent']}%</div>
                    <div style='color:#777; font-size:0.8em;'>{subj['count']}</div>
                </td>
            </tr>
            """

        if has_yesterday_data:
            yesterday_section = f"""
            <div style="margin:15px 0; border:1px solid #e0e0e0; border-radius:8px; overflow:hidden;">
                <div style="background:#f0f7ff; padding:8px; font-weight:bold; text-align:center; color:#0056b3; font-size:0.9em; border-bottom:1px solid #e0e0e0;">
                    📅 Yesterday's Report ({date_str_full})
                </div>
                <table style="width:100%; border-collapse:collapse; background:#fff;">
                    {yesterday_html_rows}
                </table>
            </div>
            """
        else:
            yesterday_section = f"""
            <div style="margin:15px 0; padding:12px; text-align:center; background:#fafafa; border-radius:8px; color:#888; font-size:0.85em; border:1px dashed #ddd;">
                No classes recorded for yesterday ({date_str_full}).
            </div>
            """

        val = float(re.search(r'\d+\.?\d*', final_percent).group()) if final_percent != "N/A" else 0
        personality = get_personality(val)
        
        subject_line = f"{personality['subject_icon']} {personality['status']}: {final_percent}"
        grand_total_text = f"{total_attended} / {total_delivered}"

        final_body = f"""
        <div style="font-family:'Segoe UI', sans-serif; max-width:500px; margin:auto; border:1px solid #e0e0e0; border-radius:12px; overflow:hidden;">
            <div style="background:{personality['color']}; padding:25px; text-align:center; color:white;">
                <h1 style="margin:0; font-size:2.8em; font-weight:bold;">{final_percent}</h1>
                <p style="margin:5px 0 0 0; font-size:1.4em; font-weight:bold; opacity:0.9;">{grand_total_text}</p>
                <p style="margin:5px 0 0 0; font-size:1.1em; opacity:0.8;">{personality['status']}</p>
            </div>
            
            <div style="padding:0 20px;">
                {yesterday_section}
            </div>

            <div style="padding:0 20px;">
                <h3 style="border-bottom:2px solid #eee; padding-bottom:5px; margin-bottom:10px; color:#444; font-size:1.1em;">Overall Status</h3>
                <table style="width:100%; border-collapse:collapse; font-size:0.9em;">
                    {table_html}
                </table>
            </div>

            <div style="background:#f5f5f5; padding:15px; text-align:center; font-size:0.75em; color:#999; margin-top:20px;">
                NIET Attendance Bot V7.4 (Beta) • <a href="#" style="color:#999;">Aniket Jain</a>
            </div>
        </div>
        """
        
        send_email_via_api(target_email, subject_line, final_body)

    except Exception as e:
        print(f"    ❌ Error: {e}")

    finally:
        driver.quit()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard_id", type=int, default=0)
    parser.add_argument("--total_shards", type=int, default=1)
    args = parser.parse_args()

    print(f"🚀 BOT V7.4 (BETA MODE) STARTED")
    
    # 🔒 LOCK TO YOUR COLLEGE ID
    target_id = "0231csiot122@niet.co.in"
    print(f"    🔒 Restricted to College ID: {target_id}")

    try:
        response = supabase.table("users").select("*").eq("college_id", target_id).execute()
        my_users = response.data
        
        if not my_users:
            print(f"    ❌ Error: No user found with college_id {target_id}")
            return

        for user in my_users:
            print(f"    ✅ Found User! Sending to: {user.get('target_email')}")
            check_attendance_for_user(user)
            
    except Exception as e:
        print(f"    🔥 CRITICAL ERROR: {e}")

if __name__ == "__main__":
    main()
