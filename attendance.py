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
# 🟢 FINAL STRATEGY: "CLICK THE NUMBER"
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

def send_email(percentage_text, fraction_text, status_msg):
    msg = MIMEMultipart("alternative")
    
    # Smart Color Coding
    try:
        val = float(re.search(r'\d+\.?\d*', percentage_text).group())
        if val < 75:
            color = "#D32F2F" # Red
            alert = "🚨 LOW ATTENDANCE"
            advice = "You are in the DANGER ZONE. Attend classes immediately!"
        else:
            color = "#388E3C" # Green
            alert = "✅ SAFE ZONE"
            advice = "Good job! You are maintaining a safe attendance record."
    except:
        color = "#1976D2" # Blue
        alert = "📅 DAILY UPDATE"
        advice = "Here is your latest attendance status."

    msg['Subject'] = f"{alert}: {percentage_text} ({fraction_text})"
    msg['From'] = SENDER_EMAIL
    msg['To'] = TARGET_EMAIL

    html = f"""
    <html>
      <body style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background-color: white; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <div style="background-color: {color}; padding: 20px; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 24px;">{alert}</h1>
            </div>
            <div style="padding: 30px;">
                <p style="font-size: 16px; color: #555; margin-bottom: 25px;">{advice}</p>
                
                <div style="display: flex; justify-content: space-between; margin-bottom: 20px; border-bottom: 1px solid #eee; padding-bottom: 15px;">
                    <span style="font-weight: bold; color: #333; font-size: 18px;">Total Percentage</span>
                    <span style="font-weight: bold; color: {color}; font-size: 24px;">{percentage_text}</span>
                </div>
                
                <div style="display: flex; justify-content: space-between; margin-bottom: 20px;">
                    <span style="font-weight: bold; color: #333; font-size: 18px;">Classes Attended</span>
                    <span style="font-weight: bold; color: #555; font-size: 18px;">{fraction_text}</span>
                </div>
                
                <div style="background-color: #f9f9f9; padding: 15px; border-radius: 5px; margin-top: 30px; font-size: 12px; color: #888;">
                    <strong>Debug Status:</strong> {status_msg}<br>
                    Running automatically via GitHub Actions 🤖
                </div>
            </div>
        </div>
      </body>
    </html>
    """
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASS)
            server.sendmail(SENDER_EMAIL, TARGET_EMAIL, msg.as_string())
        print("✅ EMAIL SENT SUCCESSFULLY!")
    except Exception as e:
        print(f"❌ EMAIL FAILED: {e}")

def main():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument('--ignore-certificate-errors')
    
    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 60) # Increased timeout to 60s

    # Placeholders
    final_percent = "N/A"
    final_fraction = "N/A"
    log_status = "Init"

    try:
        print("🚀 Opening NIET Cloud...")
        driver.get(LOGIN_URL)
        
        # 1. Login
        wait.until(EC.visibility_of_element_located((By.ID, USER_BOX_ID))).send_keys(COLLEGE_USER)
        driver.find_element(By.ID, PASS_BOX_ID).send_keys(COLLEGE_PASS)
        driver.find_element(By.CSS_SELECTOR, LOGIN_BTN_SELECTOR).click()
        print("🔓 Login Clicked...")
        
        # 2. Wait for Dashboard & Grab Backup Data
        print("⏳ Waiting for Dashboard...")
        wait.until(EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "Attendance"))
        
        # Grab the percentage immediately (Backup)
        dashboard_text = driver.find_element(By.TAG_NAME, "body").text
        dash_matches = re.findall(r'(\d+\.\d+)%', dashboard_text)
        if dash_matches:
            final_percent = dash_matches[-1] + "%"
            log_status = "Dashboard Only (Detailed View Click Failed)"
            print(f"💾 Backup Percentage Found: {final_percent}")

        # 3. CLICK THE NUMBER (The New Fix)
        # We look for the element that actually contains "45.65%" (or whatever the number is)
        # Clicking the number usually opens the detailed view.
        try:
            print("🖱️ Searching for clickable percentage card...")
            # XPath: Find any element containing a percentage sign '%'
            # We iterate to find the one that looks like the main attendance card
            clickable_elements = driver.find_elements(By.XPATH, "//*[contains(text(),'%')]")
            
            clicked = False
            for el in clickable_elements:
                # If element has numbers and %, click it!
                if re.search(r'\d+\.\d+%', el.text):
                    print(f"🖱️ Clicking element with text: {el.text}")
                    driver.execute_script("arguments[0].click();", el)
                    clicked = True
                    break
            
            if not clicked:
                # Backup click: Try clicking text "Attendance"
                print("⚠️ Percentage click failed. Clicking 'Attendance' text...")
                driver.find_element(By.PARTIAL_LINK_TEXT, "Attendance").click()

            # 4. Wait for Detailed Table (21/46)
            print("⏳ Click successful. Waiting for Detailed Table...")
            time.sleep(10) # Wait for animation/load
            
            # Switch to detailed frame if it exists (Just in case)
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            if iframes:
                driver.switch_to.frame(0)
                print("🔄 Switched to iframe.")

            # Scan for fraction (21/46)
            full_page_text = driver.find_element(By.TAG_NAME, "body").text
            fraction_match = re.search(r'(\d+)\s*/\s*(\d+)', full_page_text)
            
            if fraction_match:
                final_fraction = fraction_match.group(0) # e.g., "21/46"
                log_status = "Success (Detailed Data Found)"
                print(f"🎯 FOUND DETAILED DATA: {final_fraction}")
            else:
                print("⚠️ Page loaded, but 'Number/Number' pattern not found.")
                print(f"Page Dump: {full_page_text[:200]}") # Debug print

        except Exception as e:
            print(f"⚠️ Navigation Error: {e}")

        # 5. Send Email
        if final_percent != "N/A":
            send_email(final_percent, final_fraction, log_status)
        else:
            print("❌ CRITICAL: No data found at all.")

    except Exception as e:
        print(f"❌ Script Crash: {e}")
    
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
