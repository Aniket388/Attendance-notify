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
from selenium.common.exceptions import StaleElementReferenceException, NoSuchElementException, TimeoutException
from supabase import create_client, Client
from cryptography.fernet import Fernet
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# ====================================================
# 🛡️ BOT V7.1: PRODUCTION POLISH (Leak-Proof)
# ====================================================

# 🔒 SAFETY LOCK
BETA_TESTERS = ["0231csiot122@niet.co.in"]
LOGIN_URL = "https://nietcloud.niet.co.in/login.htm"

# 1. LOAD SECRETS
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()
MASTER_KEY   = os.environ.get("MASTER_KEY", "").strip().encode()
TOKEN_JSON   = os.environ.get("GMAIL_TOKEN_JSON", "").strip()

# 2. INIT GLOBAL CLIENTS
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
cipher = Fernet(MASTER_KEY)
GMAIL_SERVICE = None 

# 🚀 HELPER: Force print logs
def log(msg):
    print(msg, flush=True)

# 🚀 HELPER: Singleton Gmail Service
def get_gmail_service():
    global GMAIL_SERVICE
    if GMAIL_SERVICE: return GMAIL_SERVICE
    
    try:
        creds_data = json.loads(TOKEN_JSON)
        creds = Credentials.from_authorized_user_info(creds_data)
        GMAIL_SERVICE = build('gmail', 'v1', credentials=creds)
        return GMAIL_SERVICE
    except Exception as e:
        log(f"   ❌ Gmail Init Failed: {e}")
        return None

def get_personality(p_val):
    if p_val >= 90: return {"quote": "Absolute Legend! 🏆", "status": "Safe", "color": "#388E3C"}
    elif p_val >= 75: return {"quote": "You are Safe! ✅", "status": "Safe", "color": "#388E3C"}
    elif p_val >= 60: return {"quote": "⚠️ Thin ice!", "status": "Low", "color": "#F57C00"}
    else: return {"quote": "🚨 DANGER ZONE!", "status": "CRITICAL", "color": "#D32F2F"}

def send_email(target_email, subject, html_content):
    service = get_gmail_service()
    if not service: 
        log("   ❌ Email Service Unavailable")
        return False
    
    log(f"   📧 Sending email to {target_email}...")
    try:
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
        log(f"   ❌ Send Failed: {e}")
        return False

def check_attendance_for_user(user):
    user_id = user['college_id']
    target_email = user['target_email']
    log(f"\n🔄 Beta V7.1 Processing: {user_id}")
    
    try:
        college_pass = cipher.decrypt(user['encrypted_pass'].encode()).decode()
    except:
        log("    ❌ Decryption Failed")
        return

    # 🛠️ FIX 2: Calculate Dates ONCE (Performance)
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)

    # BROWSER CONFIG
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument('--ignore-certificate-errors')
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.page_load_strategy = 'eager' 
    
    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 20)
    
    final_percent_str = "N/A"
    final_percent_val = 0.0
    table_html = ""
    yesterday_updates = []

    try:
        # --- LOGIN ---
        driver.get(LOGIN_URL)
        try: driver.switch_to.alert.accept()
        except: pass

        wait.until(EC.visibility_of_element_located((By.ID, "j_username"))).send_keys(user_id)
        driver.find_element(By.ID, "password-1").send_keys(college_pass)
        
        btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        driver.execute_script("arguments[0].click();", btn)
        
        try: driver.switch_to.alert.accept()
        except: pass

        wait.until(EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "Attendance"))
        log("    ✨ Login Success!")

        # --- MAIN DASHBOARD SCRAPE ---
        dash_text = driver.find_element(By.TAG_NAME, "body").text
        
        if p_match := re.search(r'(\d+\.\d+)%', dash_text):
            final_percent_str = p_match.group(0)
            final_percent_val = float(p_match.group(1)) 
            
            try:
                xpath_query = f"//*[contains(text(),'{final_percent_str}')]"
                target = driver.find_element(By.XPATH, xpath_query)
                driver.execute_script("arguments[0].click();", target)
                time.sleep(2)
                
                rows = driver.find_elements(By.TAG_NAME, "tr")
                total_attended = 0
                total_delivered = 0
                
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
            except Exception as e:
                log(f"    ⚠️ Main Table Scrape Warning: {e}")

            # ============================================================
            # 🕵️ DEEP DIVE: LEAK-PROOF TAB STRATEGY
            # ============================================================
            log("    🕵️ Deep Dive: Using Multi-Tab Strategy...")
            
            main_window = driver.current_window_handle
            subject_links = []
            
            try:
                # 🛠️ FIX 3: Slightly safer XPath
                rows = driver.find_elements(By.XPATH, "//table[.//th[text()='Course Name']]//tr[td]")
                
                for row in rows:
                    cols = row.find_elements(By.TAG_NAME, "td")
                    if len(cols) < 3: continue
                    
                    try:
                        anchor = cols[2].find_element(By.TAG_NAME, "a")
                        href = anchor.get_attribute("href")
                        subj_name = cols[1].text.strip()
                        if href and "javascript" not in href:
                            subject_links.append((subj_name, href))
                    except NoSuchElementException: continue
            except: pass

            log(f"    🔗 Found {len(subject_links)} valid subject links.")

            for name, url in subject_links:
                new_tab = None # Track explicitly
                try:
                    # 🛠️ FIX 1: Explicit Handle Tracking
                    driver.execute_script("window.open(arguments[0]);", url)
                    new_tab = driver.window_handles[-1]
                    driver.switch_to.window(new_tab)
                    
                    wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
                    
                    details_rows = driver.find_elements(By.XPATH, "//table[.//th[text()='Date']]//tr[td]")
                    if details_rows:
                        for detail in reversed(details_rows):
                            d_cols = detail.find_elements(By.TAG_NAME, "td")
                            if len(d_cols) >= 5:
                                date_text = d_cols[1].text.strip()
                                status = d_cols[4].text.strip()
                                try:
                                    entry_date = datetime.strptime(date_text, "%b %d, %Y").date()
                                    if entry_date == today: continue
                                    if entry_date == yesterday:
                                        icon = "✅" if status == "P" else "❌"
                                        yesterday_updates.append(f"<strong>{name}</strong>: {icon} {status}")
                                        log(f"       🎯 Found Yesterday: {name} ({status})")
                                        break
                                    if entry_date < yesterday: break
                                except: continue
                                
                except Exception as e:
                    log(f"    ⚠️ Tab Error ({name}): {e}")
                
                finally:
                    # 🛠️ FIX 1: Mandatory Cleanup
                    if new_tab:
                        try:
                            driver.close() # Close ONLY the specific tab
                        except: pass
                    
                    driver.switch_to.window(main_window) # Always return home

            # ============================================================
            # 📧 BUILD EMAIL
            # ============================================================
            personality = get_personality(final_percent_val)
            subject_line = f"📅 Daily: {final_percent_str}"
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
                    <h1>{final_percent_str}</h1>
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
            
            # 🛠️ FIX 4: Explicit Failure Logging
            success = send_email(target_email, subject_line, html_body)
            if not success:
                 log("    ❌ FATAL: Email failed to send.")
    
    except Exception as e:
        log(f"    ❌ Critical Runtime Error: {e}")

    finally:
        driver.quit()

def main():
    log(f"🚀 BOT V7.1 PRODUCTION POLISH STARTED")
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
        log(f"🔥 CRITICAL DB ERROR: {e}")

if __name__ == "__main__":
    main()
