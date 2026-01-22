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
# 🟢 FINAL VERSION: "THE FAMILY TREE" + "TOTAL SELECTOR"
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
    
    try:
        val = float(re.search(r'\d+\.?\d*', percentage_text).group())
        if val < 75:
            color = "#D32F2F" # Red
            alert = "🚨 LOW ATTENDANCE"
        else:
            color = "#388E3C" # Green
            alert = "✅ SAFE ZONE"
    except:
        color = "#1976D2" # Blue
        alert = "📅 DAILY UPDATE"

    msg['Subject'] = f"{alert}: {percentage_text} ({fraction_text})"
    msg['From'] = SENDER_EMAIL
    msg['To'] = TARGET_EMAIL

    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
        <div style="background-color: white; border-top: 5px solid {color}; padding: 20px; border-radius: 5px;">
            <h2 style="color: {color}; margin-top: 0;">{alert}</h2>
            <table style="width: 100%; margin-top: 20px;">
                <tr>
                    <td><strong>Percentage:</strong></td>
                    <td style="font-size: 24px; color: {color};"><strong>{percentage_text}</strong></td>
                </tr>
                <tr>
                    <td><strong>Classes:</strong></td>
                    <td style="font-size: 18px;">{fraction_text}</td>
                </tr>
            </table>
            <hr>
            <p style="font-size: 10px; color: grey;">Bot Logic: {status_msg}</p>
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
    wait = WebDriverWait(driver, 40)

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
        
        p_match = re.search(r'(\d+\.\d+)%', dash_text)
        if p_match:
            final_percent = p_match.group(0)
            print(f"💾 Backup Found: {final_percent}")

            # 3. FAMILY TREE CLICKING 🌳
            try:
                xpath_query = f"//*[contains(text(),'{final_percent}')]"
                target_element = driver.find_element(By.XPATH, xpath_query)
                
                print(f"🖱️ Found Number element. Attempting clicks...")
                try:
                    driver.execute_script("arguments[0].click();", target_element)
                except: pass
                
                time.sleep(1)
                
                try:
                    parent_element = target_element.find_element(By.XPATH, "..")
                    driver.execute_script("arguments[0].click();", parent_element)
                except: pass

                time.sleep(1)

                try:
                    grand_element = target_element.find_element(By.XPATH, "../..")
                    driver.execute_script("arguments[0].click();", grand_element)
                except: pass
                
                # 4. Wait for Detailed Table
                print("⏳ Waiting for detailed table...")
                wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(),'Course Name')]")))
                
                # 5. Scan for Data (THE FIX IS HERE)
                full_text = driver.find_element(By.TAG_NAME, "body").text
                
                # Find ALL matches, not just the first one
                all_fractions = re.findall(r'\d+\s*/\s*\d+', full_text)
                
                if all_fractions:
                    # [-1] grabs the LAST item in the list (The Total at the bottom)
                    final_fraction = all_fractions[-1]
                    log_status = "Success: Total Fraction Found"
                    print(f"🎯 FOUND TOTAL: {final_fraction}")
                else:
                    log_status = "Card Clicked, Table Empty"
                    print("⚠️ Table loaded but fraction pattern not found.")

            except Exception as e:
                log_status = f"Click Sequence Failed: {str(e)[:50]}"
                print(f"⚠️ Navigation Failed: {e}")

        # 6. Send Email
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
