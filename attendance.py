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
# 🟢 FINAL STRATEGY: "THE LINK HUNTER"
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
                    <strong>Bot Logic:</strong> {status_msg}<br>
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
    wait = WebDriverWait(driver, 60)

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
        
        # 2. Grab Backup Data
        wait.until(EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "Attendance"))
        dash_text = driver.find_element(By.TAG_NAME, "body").text
        if re.search(r'\d+\.\d+%', dash_text):
            final_percent = re.findall(r'(\d+\.\d+)%', dash_text)[-1] + "%"
            print(f"💾 Backup Percentage: {final_percent}")

        # 3. LINK HUNTER STRATEGY 🏹
        # Instead of clicking text, we find the ACTUAL link to the detailed page.
        print("🔍 Scanning for detailed view link...")
        
        # Find all links on the page
        all_links = driver.find_elements(By.TAG_NAME, "a")
        target_url = ""
        
        for link in all_links:
            href = link.get_attribute("href")
            # We look for the specific file name we saw in your screenshot
            if href and "studentCourseFileNew.htm" in href:
                target_url = href
                print(f"🎯 FOUND SECRET LINK: {target_url}")
                break
        
        if target_url:
            print("🚀 Navigating to Secret Link...")
            driver.get(target_url)
            
            # Wait for the table
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
            time.sleep(5) # Allow data to populate
            
            full_text = driver.find_element(By.TAG_NAME, "body").text
            
            # Find 21/46
            frac_match = re.search(r'(\d+)\s*/\s*(\d+)', full_text)
            if frac_match:
                final_fraction = frac_match.group(0)
                log_status = "Detailed Data Found via Link Hunter"
                print(f"✅ FOUND FRACTION: {final_fraction}")
            else:
                log_status = "Link Opened, Table Empty"
                print("⚠️ Link opened, but table data missing.")
        
        else:
            log_status = "Detailed Link Not Found on Dashboard"
            print("❌ Could not find 'studentCourseFileNew' link on dashboard.")

        # 4. Send Email
        if final_percent != "N/A":
            send_email(final_percent, final_fraction, log_status)
        else:
            print("❌ Critical: No data found.")

    except Exception as e:
        print(f"❌ Error: {e}")
    
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
