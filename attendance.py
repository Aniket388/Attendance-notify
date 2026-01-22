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

# ====================================================
# 🟢 FINAL ATTEMPT: THE "CLICKER" METHOD
# ====================================================
LOGIN_URL = "https://nietcloud.niet.co.in/login.htm"
USER_BOX_ID = "j_username"
PASS_BOX_ID = "password-1"
LOGIN_BTN_SELECTOR = "button[type='submit']"

COLLEGE_USER = os.environ["COLLEGE_USER"]
COLLEGE_PASS = os.environ["COLLEGE_PASS"]
SENDER_EMAIL = os.environ["EMAIL_USER"]
SENDER_PASS  = os.environ["EMAIL_PASS"]
TARGET_EMAIL = os.environ["TARGET_EMAIL"]

def send_email(percentage_text, fraction_text, debug_info=""):
    msg = MIMEMultipart("alternative")
    
    # Logic for Subject Line Color
    try:
        val = float(re.search(r'\d+\.?\d*', percentage_text).group())
        if val < 75:
            subject = f"🚨 LOW ATTENDANCE: {percentage_text} ({fraction_text})"
            color = "red"
        else:
            subject = f"✅ SAFE: {percentage_text} ({fraction_text})"
            color = "green"
    except:
        subject = f"📅 ATTENDANCE UPDATE: {percentage_text}"
        color = "blue"

    msg['Subject'] = subject
    msg['From'] = SENDER_EMAIL
    msg['To'] = TARGET_EMAIL

    html = f"""
    <html>
      <body>
        <h2 style="color: {color};">{subject}</h2>
        <p><b>Total Percentage:</b> {percentage_text}</p>
        <p><b>Classes:</b> {fraction_text}</p>
        <hr>
        <p style="font-size: 10px; color: grey;">Debug: {debug_info}</p>
      </body>
    </html>
    """
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(SENDER_EMAIL, SENDER_PASS)
        server.sendmail(SENDER_EMAIL, TARGET_EMAIL, msg.as_string())
    print("✅ Email Sent!")

def main():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument('--ignore-certificate-errors')
    
    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 30)

    try:
        print("🚀 Opening NIET Cloud...")
        driver.get(LOGIN_URL)
        
        # 1. Login
        wait.until(EC.visibility_of_element_located((By.ID, USER_BOX_ID))).send_keys(COLLEGE_USER)
        driver.find_element(By.ID, PASS_BOX_ID).send_keys(COLLEGE_PASS)
        driver.find_element(By.CSS_SELECTOR, LOGIN_BTN_SELECTOR).click()
        print("🔓 Login Clicked...")
        
        # 2. Wait for Dashboard
        wait.until(EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "Attendance"))
        print("✅ Dashboard Loaded.")
        
        # 3. CLICK NAVIGATION (The New Fix)
        # We look for the "Attendance" text on the dashboard and click it.
        try:
            print("🖱️ Trying to click 'Attendance' link...")
            # Try finding the specific link by text
            attendance_link = driver.find_element(By.PARTIAL_LINK_TEXT, "Attendance")
            attendance_link.click()
            print("✅ Clicked Link Text!")
        except Exception as e:
            # Backup: Try clicking the visual card title if it's not a standard link
            print("⚠️ Link not found. Trying XPath click...")
            driver.find_element(By.XPATH, "//*[contains(text(),'Attendance')]").click()

        # 4. Wait for Table to Load
        # We wait for the "Course Name" header to appear, which proves the table loaded
        print("⏳ Waiting for Detailed Table...")
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(),'Course Name')]")))
        
        # 5. SCAN THE PAGE
        body_text = driver.find_element(By.TAG_NAME, "body").text
        
        # Look for "21/46" pattern (digits/digits)
        fraction_match = re.search(r'(\d+)\s*/\s*(\d+)', body_text)
        # Look for "45.65%" pattern
        percent_matches = re.findall(r'(\d+\.\d+)%', body_text)
        
        final_fraction = fraction_match.group(0) if fraction_match else "N/A"
        final_percent = percent_matches[-1] + "%" if percent_matches else "N/A"
        
        print(f"📊 SCAN RESULTS: Fraction={final_fraction}, Percent={final_percent}")
        
        if final_percent != "N/A":
            send_email(final_percent, final_fraction, "Scanned Successfully")
        else:
            print("❌ STILL NO DATA. Dumping Page Text for Debug:")
            print("="*20)
            print(body_text[:1000]) 
            print("="*20)

    except Exception as e:
        print(f"❌ Error: {e}")
    
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
