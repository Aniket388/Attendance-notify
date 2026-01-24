import os
import re
import time
import json
import base64
import argparse  # <--- NEW: To read shard ID
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
# 🚀 BOT V5.1: LOAD BALANCED (CARD DEALER MODE)
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
        print("   ❌ Decryption Failed")
        return

    # BROWSER SETUP
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument('--ignore-certificate-errors')
    chrome_options.add_argument("--window-size=1920,1080")
    
    # POP-UP FIX
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.set_capability("unhandledPromptBehavior", "accept")

    # BLOCK IMAGES
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
        
        if current_fails > 0:
            supabase.table("users").update({"fail_count": 0}).eq("college_id", user_id).execute()
            print("   ✨ Login Success! Fail count reset.")

        dash_text = driver.find_element(By.TAG_NAME, "body").text
        
        if p_match := re.search(r'(\d+\.\d+)%', dash_text):
            final_percent = p_match.group(0)
            print(f"   📊 Found: {final_percent}")
            
            # --- SCRAPING LOGIC ---
            try:
                xpath_query = f"//*[contains(text(),'{final_percent}')]"
                target = driver.find_element(By.XPATH, xpath_query)
                driver.execute_script("arguments[0].click();", target)
                try: driver.execute_script("arguments[0].click();", target.find_element(By.XPATH, ".."))
                except: pass
                
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "tr")))
                time.sleep(2)
                
                rows = driver.find_elements(By.TAG_NAME, "tr")
                for row in rows:
                    cols = row.find_elements(By.TAG_NAME, "td")
                    if len(cols) >= 4:
                        subj = cols[1].text.strip()
                        if not subj: continue
                        per = cols[-1].text.strip()
                        bg = "border-bottom:1px solid #eee;"
                        style = ""
                        if "Total" in cols[0].text: 
                            bg = "background-color:#e8f5e9;font-weight:bold;"
                            subj = "TOTAL"
                        if float(per) < 75 and "TOTAL" not in subj: style = "color:#D32F2F;"
                        table_html += f"<tr style='{bg} {style}'><td style='padding:5px;'>{subj}</td><td style='text-align:right;'>{per}%</td></tr>"
            except: pass

            try:
                val = float(re.search(r'\d+\.?\d*', final_percent).group())
                alert, color = ("🚨 LOW", "#D32F2F") if val < 75 else ("✅ SAFE", "#388E3C")
            except: alert, color = ("📅 UPDATE", "#1976D2")

            html_body = f"""
            <div style="font-family:sans-serif;max-width:500px;margin:auto;border:1px solid #ddd;padding:20px;border-radius:10px;">
                <h2 style="color:{color};text-align:center;">{alert}: {final_percent}</h2>
                <table style="width:100%;border-collapse:collapse;">{table_html}</table>
                <p style="text-align:center;color:#aaa;font-size:10px;margin-top:20px;">NIET Bot V5.1 (Load Balanced)</p>
            </div>
            """
            send_email_via_api(target_email, f"{alert}: {final_percent}", html_body)
    
    except Exception as e:
        print(f"   ❌ Login/Scrape Error: {e}")
        new_fail = current_fails + 1
        print(f"   ⚠️ Strike {new_fail}/3")
        
        if new_fail >= 3:
            print("   💀 3 Strikes! Deactivating User.")
            supabase.table("users").update({"fail_count": new_fail, "is_active": False}).eq("college_id", user_id).execute()
            send_email_via_api(target_email, "Bot Deactivated", "<h1>Login Failed 3 Times</h1><p>Please update your password on the website.</p>")
        else:
            supabase.table("users").update({"fail_count": new_fail}).eq("college_id", user_id).execute()

    finally:
        driver.quit()

def main():
    # ⚡ NEW: ARGS FOR WORKER ID
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard_id", type=int, default=0, help="Current Worker ID (0, 1, 2...)")
    parser.add_argument("--total_shards", type=int, default=1, help="Total number of Workers")
    args = parser.parse_args()

    print(f"🚀 BOT V5.1 STARTED: Worker {args.shard_id + 1} of {args.total_shards}")

    try:
        # 1. FETCH ALL ACTIVE USERS
        response = supabase.table("users").select("*").eq("is_active", True).execute()
        all_users = response.data
        
        if not all_users:
            print("   ⚠️ No users found in database.")
            return

        # 2. 🃏 DEAL THE CARDS (Modulo Logic)
        # This keeps users 1, 5, 9... for Worker 1
        # And users 2, 6, 10... for Worker 2, etc.
        my_users = [u for i, u in enumerate(all_users) if i % args.total_shards == args.shard_id]

        print(f"📋 Total Users: {len(all_users)} | My Share: {len(my_users)}")
        
        for user in my_users:
            check_attendance_for_user(user)
            
    except Exception as e:
        print(f"🔥 CRITICAL ERROR: {e}")

if __name__ == "__main__":
    main()
