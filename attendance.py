import os
import smtplib
import re
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from supabase import create_client, Client
from cryptography.fernet import Fernet
import traceback

# ====================================================
# 🤖 V2: MULTI-USER MANAGER (FINAL FIX)
# ====================================================

# CONFIGURATION
LOGIN_URL = "https://nietcloud.niet.co.in/login.htm"

# 🛠️ FIX: Force String + Strip invisible spaces
SENDER_EMAIL = str(os.environ.get("EMAIL_USER", "")).strip()
SENDER_PASS  = str(os.environ.get("EMAIL_PASS", "")).strip()

# DATABASE CONNECTION
# We also strip these just in case
SUPABASE_URL = str(os.environ.get("SUPABASE_URL", "")).strip()
SUPABASE_KEY = str(os.environ.get("SUPABASE_KEY", "")).strip()
MASTER_KEY   = str(os.environ.get("MASTER_KEY", "")).strip().encode() # Encode only after stripping

# Initialize Tools
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
cipher = Fernet(MASTER_KEY)

def send_email(target_email, subject_line, html_content):
    print(f"   📧 Preparing email for {target_email}...")
    
    # Force String format
    t_email = str(target_email).strip()
    
    msg = MIMEMultipart("alternative")
    msg['Subject'] = str(subject_line)
    msg['From'] = SENDER_EMAIL
    msg['To'] = t_email
    msg.attach(MIMEText(str(html_content), "html", "utf-8"))

    try:
        print("   🔑 Logging into Gmail...")
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            # Login
            server.login(SENDER_EMAIL, SENDER_PASS)
            
            # Send
            server.sendmail(SENDER_EMAIL, t_email, msg.as_string())
            
        print(f"   ✅ Email sent successfully!")
        return True
    except Exception as e:
        print(f"   ❌ Email Failed: {e}")
        traceback.print_exc()
        return False

def check_attendance_for_user(user):
    college_id = user['college_id']
    target_email = user['target_email']
    
    print(f"\n🔄 Processing User: {college_id}...")
    
    try:
        # Decrypt Password
        college_pass = cipher.decrypt(user['encrypted_pass'].encode()).decode()
    except:
        print("   ❌ Decryption Failed. Wrong Master Key?")
        return

    # Browser Setup
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument('--ignore-certificate-errors')
    chrome_options.add_argument("--window-size=1920,1080")
    
    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 25)

    final_percent = "N/A"
    final_fraction = "N/A"
    table_html = ""
    status_msg = "Error"

    try:
        driver.get(LOGIN_URL)
        
        # Login
        wait.until(EC.visibility_of_element_located((By.ID, "j_username"))).send_keys(college_id)
        driver.find_element(By.ID, "password-1").send_keys(college_pass)
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        
        # Check Dashboard
        wait.until(EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "Attendance"))
        dash_text = driver.find_element(By.TAG_NAME, "body").text
        p_match = re.search(r'(\d+\.\d+)%', dash_text)
        
        if p_match:
            final_percent = p_match.group(0)
            print(f"   📊 Found Percentage: {final_percent}")
            
            # Navigate to Detail
            try:
                xpath_query = f"//*[contains(text(),'{final_percent}')]"
                target = driver.find_element(By.XPATH, xpath_query)
                driver.execute_script("arguments[0].click();", target)
                try: driver.execute_script("arguments[0].click();", target.find_element(By.XPATH, ".."))
                except: pass
                
                # Wait for Table
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "tr")))
                time.sleep(2)
                
                # Scrape
                rows = driver.find_elements(By.TAG_NAME, "tr")
                for row in rows:
                    cols = row.find_elements(By.TAG_NAME, "td")
                    if len(cols) >= 4:
                        subj = cols[1].text.strip()
                        if not subj: continue 
                        
                        cnt = cols[-2].text.strip()
                        per = cols[-1].text.strip()
                        
                        bg = "border-bottom:1px solid #eee;"
                        style = ""
                        if "Total" in cols[0].text or "Total" in subj:
                            bg = "background-color:#e8f5e9;font-weight:bold;border-top:2px solid #aaa;"
                            subj = "GRAND TOTAL"
                        try:
                            if float(per) < 75 and "Total" not in subj: style = "color:#D32F2F;"
                        except: pass
                        
                        table_html += f"<tr style='{bg} {style}'><td style='padding:8px;'>{subj}</td><td style='text-align:center;'>{cnt}</td><td style='text-align:right;'>{per}%</td></tr>"

                # Fraction
                full_text = driver.find_element(By.TAG_NAME, "body").text
                fracs = re.findall(r'\d+\s*/\s*\d+', full_text)
                if fracs: final_fraction = fracs[-1]
                status_msg = "Success"

            except:
                print("   ⚠️ Could not open detailed table (sending summary only)")

            # Prepare Email
            try:
                val = float(re.search(r'\d+\.?\d*', final_percent).group())
                alert, color = ("🚨 LOW ATTENDANCE", "#D32F2F") if val < 75 else ("✅ SAFE ZONE", "#388E3C")
            except:
                alert, color = ("📅 DAILY UPDATE", "#1976D2")

            html_body = f"""
            <html><body style="font-family:sans-serif;background:#f4f4f4;padding:10px;">
            <div style="background:white;max-width:600px;margin:auto;border-top:6px solid {color};padding:20px;border-radius:8px;">
                <h2 style="color:{color};text-align:center;">{alert}</h2>
                <h1 style="color:#333;text-align:center;font-size:40px;">{final_percent}</h1>
                <p style="text-align:center;color:#666;">{final_fraction}</p>
                <hr>
                <table style="width:100%;font-size:13px;border-collapse:collapse;">{table_html}</table>
                <p style="text-align:center;font-size:10px;color:#aaa;margin-top:20px;">NIET Bot V2 • {status_msg}</p>
            </div></body></html>
            """
            
            send_email(target_email, f"{alert}: {final_percent}", html_body)
            
        else:
            print("   ❌ No attendance text found on dashboard.")

    except Exception as e:
        print(f"   ❌ Browser/Login Error: {e}")
    finally:
        driver.quit()

def main():
    print("🚀 BOT STARTED: Fetching Users from Supabase...")
    try:
        response = supabase.table("users").select("*").eq("is_active", True).execute()
        users = response.data
        print(f"📋 Found {len(users)} active users.")

        for user in users:
            check_attendance_for_user(user)
            
    except Exception as e:
        print(f"🔥 CRITICAL FAILURE: {e}")

if __name__ == "__main__":
    main()
