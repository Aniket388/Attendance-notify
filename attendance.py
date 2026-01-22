import os
import smtplib
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ====================================================
# 🟢 FINAL CONFIGURATION (THE TELEPORTER)
# ====================================================
LOGIN_URL = "https://nietcloud.niet.co.in/login.htm"
# This is the secret link to the detailed table seen in your screenshots
ATTENDANCE_URL = "https://nietcloud.niet.co.in/studentCourseFileNew.htm?shwA=%2700A%27"

USER_BOX_ID = "j_username"
PASS_BOX_ID = "password-1"
LOGIN_BTN_SELECTOR = "button[type='submit']"

# Secrets
COLLEGE_USER = os.environ["COLLEGE_USER"]
COLLEGE_PASS = os.environ["COLLEGE_PASS"]
SENDER_EMAIL = os.environ["EMAIL_USER"]
SENDER_PASS  = os.environ["EMAIL_PASS"]
TARGET_EMAIL = os.environ["TARGET_EMAIL"]

def get_custom_message(percentage):
    try:
        p = float(percentage)
    except:
        return "📅 DAILY UPDATE", "Here is your latest attendance report.", "blue"

    if p >= 90:
        return "👑 TOP G STATUS", "You are dominating! Feel free to bunk a few classes.", "green"
    elif p >= 80:
        return "✅ SAFE ZONE", "You are totally safe. Keep maintaining this.", "green"
    elif p >= 75:
        return "⚠️ ON THE EDGE", "You are safe, but barely. Don't take risks!", "#FFBF00" # Amber
    elif p >= 65:
        return "🚨 DANGER ZONE", "You are BELOW 75%! You need to attend classes immediately.", "red"
    else:
        return "💀 CRITICAL FAILURE", "You are in huge trouble. Detained list incoming?", "darkred"

def send_email(percentage_text, fraction_text, debug_info=""):
    msg = MIMEMultipart("alternative")
    
    try:
        clean_percent = re.search(r'\d+\.?\d*', percentage_text).group()
    except:
        clean_percent = 0

    subject_prefix, body_msg, color = get_custom_message(clean_percent)
    
    msg['Subject'] = f"{subject_prefix}: {percentage_text} ({fraction_text})"
    msg['From'] = SENDER_EMAIL
    msg['To'] = TARGET_EMAIL

    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
        <div style="background-color: white; border-left: 6px solid {color}; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <h2 style="color: {color}; margin-top: 0;">{subject_prefix}</h2>
            <p style="font-size: 16px; color: #333;">{body_msg}</p>
            <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
            <table style="width: 100%;">
                <tr>
                    <td style="padding: 5px;"><strong>Total Percentage:</strong></td>
                    <td style="font-size: 24px; color: {color}; font-weight: bold;">{percentage_text}</td>
                </tr>
                <tr>
                    <td style="padding: 5px;"><strong>Classes Attended:</strong></td>
                    <td style="font-size: 18px; color: #555;">{fraction_text}</td>
                </tr>
            </table>
            <br>
            <p style="font-size: 10px; color: #999;">Bot Log: {debug_info}</p>
        </div>
      </body>
    </html>
    """
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(SENDER_EMAIL, SENDER_PASS)
        server.sendmail(SENDER_EMAIL, TARGET_EMAIL, msg.as_string())
    print("✅ Custom Email Sent Successfully")

def main():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument('--ignore-certificate-errors')
    
    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 40) 

    try:
        print("🚀 Opening NIET Cloud...")
        driver.get(LOGIN_URL)
        
        # 1. Login
        wait.until(EC.visibility_of_element_located((By.ID, USER_BOX_ID))).send_keys(COLLEGE_USER)
        driver.find_element(By.ID, PASS_BOX_ID).send_keys(COLLEGE_PASS)
        driver.find_element(By.CSS_SELECTOR, LOGIN_BTN_SELECTOR).click()
        print("🔓 Login Clicked...")
        
        # 2. Wait for Dashboard to ensure login worked
        wait.until(EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "Attendance"))
        print("✅ Dashboard loaded.")

        # 3. TELEPORT: Jump straight to the detailed page! ⚡
        print("🚀 Navigating to Detailed Attendance Table...")
        driver.get(ATTENDANCE_URL)
        
        # 4. Wait for the big table
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
        print("⏳ Detailed Table detected. Scanning...")

        # 5. Reverse Scan (The Fail-Safe Logic)
        all_rows = driver.find_elements(By.TAG_NAME, "tr")
        target_row_text = ""
        found_data = False
        
        for row in reversed(all_rows):
            text = row.text.strip()
            # Look for line with fraction AND percentage (e.g. "21/46" and "45.65")
            if "/" in text and "%" in text:
                target_row_text = text
                found_data = True
                print(f"🎯 FOUND TARGET ROW: {target_row_text}")
                break
        
        if found_data:
            # Extract Percentage (45.65)
            p_matches = re.findall(r'\d+\.\d+', target_row_text)
            final_percent = p_matches[-1] + "%" if p_matches else "Unknown"
            
            # Extract Fraction (21/46)
            f_matches = re.findall(r'\d+\s*/\s*\d+', target_row_text)
            final_fraction = f_matches[-1] if f_matches else "N/A"
            
            print(f"📊 Ready to send: {final_percent} | {final_fraction}")
            send_email(final_percent, final_fraction, "Row Found: " + target_row_text[:20])
            
        else:
            print("❌ Scan failed. Detailed page loaded but no 'Number/Number' found.")
            # Fallback: Just grab the percentage if we can't find the fraction
            body_text = driver.find_element(By.TAG_NAME, "body").text
            p_matches = re.findall(r'\d+\.\d+', body_text)
            if p_matches:
                print("⚠️ Fallback: Sending percentage only.")
                send_email(p_matches[-1] + "%", "N/A (Table Hidden)", "Fallback Mode")

    except Exception as e:
        print(f"❌ Critical Error: {e}")
    
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
