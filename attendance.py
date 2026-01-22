import os
import smtplib
import re # Added for Regex search
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ====================================================
# 🟢 FINAL NIET CONFIGURATION (SMART SEARCH EDITION)
# ====================================================
LOGIN_URL = "https://nietcloud.niet.co.in/login.htm"
USER_BOX_ID = "j_username"
PASS_BOX_ID = "password-1"
LOGIN_BTN_SELECTOR = "button[type='submit']"

# Secrets
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

    try:
        # Clean the text (remove % and extra spaces)
        clean_num = float(re.search(r'\d+\.?\d*', attendance_text).group())
        color = "red" if clean_num < 75 else "green"
        status = "⚠️ LOW ATTENDANCE" if clean_num < 75 else "✅ YOU ARE SAFE"
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
    chrome_options.add_argument('--ignore-certificate-errors')
    chrome_options.add_argument('--allow-running-insecure-content')
    
    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 30) # Increased wait to 30s

    try:
        print("🚀 Opening NIET Cloud...")
        driver.get(LOGIN_URL)
        
        # Login
        wait.until(EC.visibility_of_element_located((By.ID, USER_BOX_ID))).send_keys(COLLEGE_USER)
        driver.find_element(By.ID, PASS_BOX_ID).send_keys(COLLEGE_PASS)
        driver.find_element(By.CSS_SELECTOR, LOGIN_BTN_SELECTOR).click()
        print("🔓 Login Clicked...")
        
        # Wait for the table to actually load
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
        print("⏳ Table detected... scanning for numbers...")

        # 🧠 SMART SEARCH STRATEGY
        # Instead of trusting one XPath, we grab ALL text from the page
        # and look for the pattern "Number%" (e.g. 75.5%)
        
        body_text = driver.find_element(By.TAG_NAME, "body").text
        
        # Regex to find all percentages (like 75.00 or 75.5)
        # We assume the Total is usually the LAST percentage on the page
        matches = re.findall(r'\d+\.\d+', body_text)
        
        if matches:
            # We assume the last number found is the Total Percentage
            # (Because totals are usually at the bottom right)
            final_score = matches[-1] + "%"
            print(f"📊 Found Multiple Numbers: {matches}")
            print(f"🎯 identified Total: {final_score}")
            send_email(final_score)
        else:
            print("❌ Could not find any percentage numbers on the page.")
            print("Debug Dump (First 500 chars):")
            print(body_text[:500])

    except Exception as e:
        print(f"❌ Error: {e}")
    
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
