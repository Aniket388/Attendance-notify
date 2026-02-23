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
# 🛡️ BOT V9.4: MATTE MODERN UI EDITION
# ====================================================

LOGIN_URL = "https://nietcloud.niet.co.in/login.htm"
BETA_TARGET_ID = "0231csiot122@niet.co.in" 

# 1. LOAD SECRETS
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()
MASTER_KEY   = os.environ.get("MASTER_KEY", "").strip().encode()
TOKEN_JSON   = os.environ.get("GMAIL_TOKEN_JSON", "").strip()

# 2. INIT CLIENTS
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
cipher = Fernet(MASTER_KEY)

# 🎨 NEW MATTE COLOR PALETTE
def get_personality(percentage):
    p = float(percentage)
    # Colors updated to sophisticated matte tones
    if p >= 90: return {"quote": "Absolute Legend! 🏆 Basically living at college.", "status": "Safe Zone", "color": "#3A7D68", "subject_icon": "🏆"} # Matte Deep Sage
    elif p >= 75: return {"quote": "You are Safe! Keep maintaining this flow.", "status": "On Track", "color": "#3A7D68", "subject_icon": "✅"} # Matte Deep Sage
    elif p >= 60: return {"quote": "You are on thin ice! Don't skip anymore classes.", "status": "Attendance is Low", "color": "#C27C2E", "subject_icon": "⚠️"} # Matte Burnt Ochre
    else: return {"quote": "DANGER ZONE! Run to college immediately!", "status": "Critical Low", "color": "#B94A40", "subject_icon": "🚨"} # Matte Brick Red

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
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        
        try:
            WebDriverWait(driver, 5).until(EC.alert_is_present())
            driver.switch_to.alert.accept()
        except: pass

        print("   ⏳ Waiting for Dashboard (home.htm)...")
        wait.until(EC.url_contains("home.htm"))

        # 2. CLICK DASHBOARD WIDGET 
        print("   🧭 Scanning Dashboard for Attendance Block...")
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(1) 
        
        dash_text = driver.find_element(By.TAG_NAME, "body").text
        
        if p_match := re.search(r'(\d+\.\d+)%', dash_text):
            final_percent = p_match.group(0)
            print(f"   📊 Found Overall Percentage: {final_percent}")
            
            try:
                xpath_query = f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'attendance')]/ancestor::*//*[contains(text(),'{final_percent}')]"
                target = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_query)))
                driver.execute_script("arguments[0].click();", target)
            except:
                print("   ⚠️ Strict widget locator failed. Falling back to text match...")
                xpath_query = f"//*[contains(text(),'{final_percent}')]"
                target = driver.find_element(By.XPATH, xpath_query)
                driver.execute_script("arguments[0].click();", target)
                
            try: driver.execute_script("arguments[0].click();", target.find_element(By.XPATH, ".."))
            except: pass
        else:
            print("   ❌ Could not find percentage on dashboard.")
            return

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
                    driver.execute_script("arguments[0].click();", link_element)
                    
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
            # Matte Color Logic for low attendance text
            p_val = float(subj['percent']) if subj['percent'].replace('.','',1).isdigit() else 100
            # Use the new matte brick red for low attendance text
            p_color = "#B94A40" if p_val < 75 else "#3C4043" 
            p_weight = "600" if p_val < 75 else "500"

            # Matte Badges (Pills) - Subtle backgrounds, strong matte text
            if subj['yesterday'] == "Present":
                # Subtle Sage BG, Matte Teal Text
                badge = "<span style='background-color:#E8F3F0; color:#2E6B58; padding:6px 12px; border-radius:16px; font-size:0.75em; font-weight:700; letter-spacing:0.3px; text-transform:uppercase;'>Present</span>"
            elif subj['yesterday'] == "Absent":
                # Subtle Coral BG, Matte Brick Text
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
        
        # Unified Matte Modern Card Template with updated fonts and softer shadows
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
                    NIET Attendance Bot • Matte Edition
                </div>
            </div>
        </div>
        """
        
        send_email_via_api(target_email, subject_line, html_body)

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

    print(f"🚀 BOT V9.4 STARTED")

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
