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
# 🧪 BETA CHANNEL: V2.0 (Yesterday + Weekly + Monthly)
# ====================================================

# 🔒 SAFETY LOCK: This script will ONLY run for this user.
BETA_TESTERS = ["0231csiot122@niet.co.in"] 

LOGIN_URL = "https://nietcloud.niet.co.in/login.htm"

# 1. LOAD SECRETS (Same as your main bot)
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()
MASTER_KEY   = os.environ.get("MASTER_KEY", "").strip().encode()
TOKEN_JSON   = os.environ.get("GMAIL_TOKEN_JSON", "").strip()

# 2. INIT CLIENTS
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
cipher = Fernet(MASTER_KEY)

# 🗓️ HELPER: Decide which report to generate
def get_report_mode():
    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    
    # Priority 1: Month End (Last day of month)
    if tomorrow.month != today.month:
        return "MONTHLY"
    # Priority 2: Sunday
    elif today.weekday() == 6:
        return "WEEKLY"
    # Priority 3: Normal Day
    else:
        return "DAILY"

# 🧠 BRAIN: MOTIVATION LOGIC (Your Original)
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
    print(f"   📧 Sending V2 Beta Report to {target_email}...")
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

def check_attendance_beta(user):
    user_id = user['college_id']
    target_email = user['target_email']
    
    print(f"\n🔄 Beta Processing: {user_id}")
    
    try:
        college_pass = cipher.decrypt(user['encrypted_pass'].encode()).decode()
    except:
        print("    ❌ Decryption Failed")
        return

    mode = get_report_mode()
    # 🧪 UNCOMMENT TO FORCE MODE FOR TESTING:
    # mode = "DAILY" 
    print(f"    📅 Report Mode: {mode}")

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
    grand_total_text = "0 / 0"
    current_table_html = ""
    
    # New Data Buckets
    yesterday_updates = [] 
    weekly_stats = {"attended": 0, "total": 0}

    try:
        # --- LOGIN ---
        driver.get(LOGIN_URL)
        try: driver.switch_to.alert.accept() 
        except: pass
        
        wait.until(EC.visibility_of_element_located((By.ID, "j_username"))).send_keys(user_id)
        driver.find_element(By.ID, "password-1").send_keys(college_pass)
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        
        wait.until(EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "Attendance"))
        print("    ✨ Login Success")

        # ============================================================
        # PART 1: SCRAPE CURRENT STATUS (Your Original Code Logic)
        # ============================================================
        print("    📊 Scraping Current Status...")
        dash_text = driver.find_element(By.TAG_NAME, "body").text
        
        if p_match := re.search(r'(\d+\.\d+)%', dash_text):
            final_percent = p_match.group(0)
            
            # Click percentage to open main table
            try:
                xpath_query = f"//*[contains(text(),'{final_percent}')]"
                target = driver.find_element(By.XPATH, xpath_query)
                driver.execute_script("arguments[0].click();", target)
                try: driver.execute_script("arguments[0].click();", target.find_element(By.XPATH, ".."))
                except: pass
                time.sleep(2)
            except: pass

            # Scrape Rows for Email Body
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
                    
                    # Style Logic
                    bg = "border-bottom:1px solid #eee;"
                    text_style = "color:#333;"
                    if "Total" in cols[0].text: 
                        bg = "background-color:#f0f7ff; font-weight:bold; border-top: 2px solid #ddd;"
                        subj = "GRAND TOTAL"
                        text_style = "color:#000;"
                    else:
                        # Math for Grand Total
                        try:
                            parts = count_text.split('/')
                            if len(parts) == 2:
                                total_attended += int(parts[0])
                                total_delivered += int(parts[1])
                        except: pass

                    if "Total" not in cols[0].text and float(per) < 75:
                        text_style = "color:#D32F2F; font-weight:bold;"

                    current_table_html += f"""
                    <tr style='{bg}'>
                        <td style='padding:12px 5px; {text_style}'>{subj}</td>
                        <td style='text-align:right; padding:12px 5px;'>
                            <div style='{text_style}'>{per}%</div>
                            <div style='color:#666; font-size:0.8em;'>{count_text}</div>
                        </td>
                    </tr>
                    """
            grand_total_text = f"{total_attended} / {total_delivered}"

        # ============================================================
        # PART 2: THE DEEP DIVE (New V2 Logic)
        # ============================================================
        if mode != "MONTHLY": # (Skip scanning if monthly, we'll add that logic later)
            print(f"    🕵️ Starting Deep Dive ({mode})...")
            
            # Re-Find Subject Rows (Main Dashboard View)
            # We look for rows where the 3rd column is the "Attendance Count" (e.g. 58/110)
            subject_rows = driver.find_elements(By.XPATH, "//table[.//th[text()='Course Name']]//tr[td]")
            total_subjects = len(subject_rows)

            for i in range(total_subjects):
                try:
                    # Refresh elements to avoid StaleElement
                    rows = driver.find_elements(By.XPATH, "//table[.//th[text()='Course Name']]//tr[td]")
                    if i >= len(rows): break
                    
                    row = rows[i]
                    cols = row.find_elements(By.TAG_NAME, "td")
                    if len(cols) < 3: continue
                    
                    subj_name = cols[1].text.strip()
                    
                    # Find the clickable count (It's usually an <a> tag inside the 3rd column)
                    try:
                        count_link = cols[2].find_element(By.TAG_NAME, "a")
                    except: continue # Skip if not clickable

                    print(f"       Scanning: {subj_name}...")
                    driver.execute_script("arguments[0].click();", count_link)
                    time.sleep(1.5) 
                    
                    # Scrape Details Table (Look for 'Date' header)
                    details_rows = driver.find_elements(By.XPATH, "//table[.//th[text()='Date']]//tr[td]")
                    
                    # Process Rows (Reverse: Newest to Oldest)
                    for detail in reversed(details_rows):
                        d_cols = detail.find_elements(By.TAG_NAME, "td")
                        if len(d_cols) < 5: continue
                        
                        date_text = d_cols[1].text.strip() # "Jan 29, 2026"
                        status = d_cols[4].text.strip()    # "P" or "A"
                        
                        try:
                            entry_date = datetime.strptime(date_text, "%b %d, %Y")
                            today_date = datetime.now().date()
                            
                            # LOGIC: DAILY (Yesterday Only)
                            if mode == "DAILY":
                                yesterday = today_date - timedelta(days=1)
                                if entry_date.date() == yesterday:
                                    icon = "✅" if status == "P" else "❌"
                                    # Create nice string: "Java: ✅ P"
                                    yesterday_updates.append(f"<strong>{subj_name}</strong>: {icon} {status}")
                                elif entry_date.date() < yesterday:
                                    break # Stop scanning this subject

                            # LOGIC: WEEKLY (Last 7 Days)
                            elif mode == "WEEKLY":
                                start_date = today_date - timedelta(days=7)
                                if entry_date.date() >= start_date:
                                    weekly_stats["total"] += 1
                                    if status == "P": weekly_stats["attended"] += 1
                                else:
                                    break
                        except: continue
                        
                except Exception as e:
                    print(f"       ⚠️ Skip {i}: {e}")
                    continue

        # ============================================================
        # PART 3: BUILD EMAIL (Combining Old + New)
        # ============================================================
        
        # Calculate Personality (Colors/Quotes)
        try:
            val = float(re.search(r'\d+\.?\d*', final_percent).group())
            personality = get_personality(val)
        except: 
            personality = {"quote": "Update", "status": "Update", "color": "#1976D2", "subject_icon": "📅"}

        subject_line = ""
        html_body = ""

        # --- MODE A: DAILY REPORT ---
        if mode == "DAILY":
            subject_line = f"📅 Daily: {final_percent}"
            
            # Yesterday Section HTML
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
                y_html = "<div style='text-align:center; color:#888; margin-bottom:20px; font-style:italic; font-size:0.9em;'>No classes marked yesterday.</div>"

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
                        {current_table_html}
                    </table>
                </div>

                <div style="background:#fafafa; padding:15px; text-align:center; font-size:0.75em; color:#999;">
                    Beta V2.0 • Daily Report
                </div>
            </div>
            """

        # --- MODE B: WEEKLY REPORT ---
        elif mode == "WEEKLY":
            eff = 0
            if weekly_stats['total'] > 0:
                eff = int((weekly_stats['attended'] / weekly_stats['total']) * 100)
                
            subject_line = f"📊 Weekly Summary: {eff}% Efficiency"
            
            html_body = f"""
            <div style="font-family:'Segoe UI', sans-serif; max-width:500px; margin:auto; border:1px solid #e0e0e0; border-radius:12px; padding:20px;">
                <h2 style="text-align:center; color:#333;">Weekly Summary 📊</h2>
                <div style="background:#f5f5f5; padding:30px; border-radius:10px; text-align:center; margin-bottom:20px;">
                    <div style="font-size:3.5em; font-weight:bold; color:#1976D2;">{eff}%</div>
                    <div style="color:#666; font-weight:bold;">Attendance Efficiency</div>
                    <p style="color:#999; font-size:0.9em;">(Last 7 Days)</p>
                </div>
                <table style="width:100%; text-align:center;">
                    <tr>
                        <td style="font-size:1.2em;">✅ <b>{weekly_stats['attended']}</b> Attended</td>
                        <td style="font-size:1.2em;">❌ <b>{weekly_stats['total'] - weekly_stats['attended']}</b> Missed</td>
                    </tr>
                </table>
            </div>
            """

        send_email_via_api(target_email, subject_line, html_body)

    except Exception as e:
        print(f"    ❌ Error: {e}")

    finally:
        driver.quit()

def main():
    print(f"🚀 STARTING BETA BOT V2.0")
    try:
        response = supabase.table("users").select("*").eq("is_active", True).execute()
        all_users = response.data

        # 🛡️ SAFETY FILTER: ONLY RUN FOR BETA TESTERS
        my_users = [u for u in all_users if u['college_id'] in BETA_TESTERS]

        if not my_users:
            print("❌ No Beta Testers found in the database.")
            return

        print(f"🧪 Running ONLY for: {BETA_TESTERS}")
        for user in my_users:
            check_attendance_beta(user)
            
    except Exception as e:
        print(f"🔥 CRITICAL ERROR: {e}")

if __name__ == "__main__":
    main()
