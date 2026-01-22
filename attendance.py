import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ====================================================
# 🟢 FINAL NIET CONFIGURATION
# ====================================================
LOGIN_URL = "https://nietcloud.niet.co.in/login.htm"

# IDs extracted from your screenshots
USER_BOX_ID = "j_username"
PASS_BOX_ID = "password-1"

# Smart Selector for the button (since it has no ID)
LOGIN_BTN_SELECTOR = "button[type='submit']"

# Smart XPath: "Find the last cell in the last row of the table"
# This grabs the value in the bottom-right corner (Total %)
ATTENDANCE_XPATH = "//tr[last()]/td[last()]" 
# ====================================================

# Load Secrets from GitHub
COLLEGE_USER = os.environ["COLLEGE_USER"]
COLLEGE_PASS = os.environ["COLLEGE_PASS"]
SENDER_EMAIL = os.environ["EMAIL_USER"]
SENDER_PASS  = os.environ["EMAIL_PASS"]
TARGET_EMAIL = os.environ["TARGET_EMAIL"]

def send_email(attendance_text):
    msg = MIMEMultipart("alternative")
    msg['Subject'] = f"NIET Attendance Update: {attendance_text}"
    msg['From'] = SENDER_EMAIL
    msg['To'] = TARGET_EMAIL

    # Color Logic: Red if below 75, Green if above
    try:
        numeric_val = float(attendance_text.replace('%', '').strip())
        color = "red" if numeric_val < 75 else "green"
        status = "⚠️ LOW ATTENDANCE" if numeric_val < 75 else "✅ YOU ARE SAFE"
    except:
        color = "blue"
        status = "Daily Update"

    html = f"""
    <html>
      <body>
        <h3>{status}</h3>
        <p>Current Total Percentage:</p>
        <h1 style="color: {color};">{attendance_text}</h1>
        <hr>
        <p style="font-size: small; color: gray;">Sent from GitHub Actions</p>
      </body>
    </html>
    """
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(SENDER_EMAIL, SENDER_PASS)
        server.sendmail(SENDER_EMAIL, TARGET_EMAIL, msg.as_string())
    print("✅ Email Sent Successfully")

def main():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # ⚠️ CRITICAL FOR NIET: Fixes SSL/Certificate errors
    chrome_options.add_argument('--ignore-certificate-errors')
    chrome_options.add_argument('--allow-running-insecure-content')
    
    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 20) # 20 second timeout

    try:
        print("🚀 Opening NIET Cloud...")
        driver.get(LOGIN_URL)
        
        # 1. Enter Username
        wait.until(EC.visibility_of_element_located((By.ID, USER_BOX_ID))).send_keys(COLLEGE_USER)
        
        # 2. Enter Password
        driver.find_element(By.ID, PASS_BOX_ID).send_keys(COLLEGE_PASS)
        
        # 3. Click Login (Using CSS Selector for type='submit')
        driver.find_element(By.CSS_SELECTOR, LOGIN_BTN_SELECTOR).click()
        print("🔓 Login Clicked...")
        
        # 4. Wait for Dashboard & Grab Attendance
        # We wait for the table row to appear
        print("⏳ Waiting for attendance table...")
        element = wait.until(EC.presence_of_element_located((By.XPATH, ATTENDANCE_XPATH)))
        
        text = element.text
        print(f"📊 Captured Attendance: {text}")
        
        if text:
            send_email(text)
        else:
            print("❌ Found empty text. Check XPath.")

    except Exception as e:
        print(f"❌ Error: {e}")
        # Debug: Print URL to see if login failed
        print(f"Current URL: {driver.current_url}")
    
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
