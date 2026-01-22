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
# 🟢 CONFIGURATION
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

def get_custom_message(percentage):
    """Returns a custom subject and message based on your score."""
    p = float(percentage)
    
    if p >= 90:
        return "👑 TOP G STATUS", "You are dominating! Feel free to bunk a few classes.", "green"
    elif p >= 80:
        return "✅ SAFE ZONE", "You are totally safe. Keep maintaining this.", "green"
    elif p >= 75:
        return "⚠️ ON THE EDGE", "You are safe, but barely. Don't take risks!", "orange"
    elif p >= 65:
        return "🚨 DANGER ZONE", "You are BELOW 75%! You need to attend classes immediately.", "red"
    else:
        return "💀 CRITICAL FAILURE", "You are in huge trouble. Detained list incoming?", "red"

def send_email(percentage_text, fraction_text):
    msg = MIMEMultipart("alternative")
    
    # Extract just the number (e.g. 45.65) from text
    clean_percent = float(re.search(r'\d+\.?\d*', percentage_text).group())
    
    # Get the smart message
    subject_prefix, body_msg, color = get_custom_message(clean_percent)
    
    msg['Subject'] = f"{subject_prefix}: {percentage_text} ({fraction_text})"
    msg['From'] = SENDER_EMAIL
    msg['To'] = TARGET_EMAIL

    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif;">
        <div style="border: 2px solid {color}; padding: 20px; border-radius: 10px;">
            <h2 style="color: {color};">{subject_prefix}</h2>
            <p style="font-size: 18px;">{body_msg}</p>
            <hr>
            <table style="width: 100%;">
                <tr>
                    <td><strong>Current Attendance:</strong></td>
                    <td style="font-size: 24px; color: {color};"><strong>{percentage_text}</strong></td>
                </tr>
                <tr>
                    <td><strong>Classes Attended:</strong></td>
                    <td style="font-size: 20px;">{fraction_text}</td>
                </tr>
            </table>
            <br>
            <p style="font-size: 12px; color: gray;">
                <i>Bot ran automatically via GitHub Actions 🤖</i>
            </p>
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
    wait = WebDriverWait(driver, 30)

    try:
        print("🚀 Opening NIET Cloud...")
        driver.get(LOGIN_URL)
        
        # Login
        wait.until(EC.visibility_of_element_located((By.ID, USER_BOX_ID))).send_keys(COLLEGE_USER)
        driver.find_element(By.ID, PASS_BOX_ID).send_keys(COLLEGE_PASS)
        driver.find_element(By.CSS_SELECTOR, LOGIN_BTN_SELECTOR).click()
        print("🔓 Login Clicked...")
        
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
        print("⏳ Scanning page data...")

        body_text = driver.find_element(By.TAG_NAME, "body").text
        
        # 1. Find Percentages (e.g., 45.65)
        percent_matches = re.findall(r'\d+\.\d+', body_text)
        
        # 2. Find Fractions (e.g., 21/46)
        # Pattern: digits, forward slash, digits
        fraction_matches = re.findall(r'\d+/\d+', body_text)
        
        if percent_matches and fraction_matches:
            # We assume the LAST item found is the "Total" for both
            final_percent = percent_matches[-1] + "%"
            final_fraction = fraction_matches[-1]
            
            print(f"🎯 Found Data -> Score: {final_percent} | Count: {final_fraction}")
            send_email(final_percent, final_fraction)
        else:
            print("❌ Could not find data patterns.")
            print(f"Debug: Found {len(percent_matches)} percents and {len(fraction_matches)} fractions.")

    except Exception as e:
        print(f"❌ Error: {e}")
    
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
