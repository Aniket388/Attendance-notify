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
# 🟢 FINAL VERSION: "THE STABILITY WAIT" (Solves 0/5 Issue)
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
                    <td><strong>Total Percentage:</strong></td>
                    <td style="font-size: 24px; color: {color};"><strong>{percentage_text}</strong></td>
                </tr>
                <tr>
                    <td><strong>Classes Attended:</strong></td>
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
    chrome_options.add_argument("--window-size=1920,1080")
    
    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 60)

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
        
        # 2. Grab Backup Data
        wait.until(EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "Attendance"))
        dash_text = driver.find_element(By.TAG_NAME, "body").text
        
        p_match = re.search(r'(\d+\.\d+)%', dash_text)
        if p_match:
            final_percent = p_match.group(0)
            print(f"💾 Backup Found: {final_percent}")

            # 3. FAMILY TREE CLICKING
            try:
                xpath_query = f"//*[contains(text(),'{final_percent}')]"
                target_element = driver.find_element(By.XPATH, xpath_query)
                
                # Attempt standard click
                try: driver.execute_script("arguments[0].click();", target_element)
                except: pass
                
                # Attempt parent clicks
                try: 
                    parent = target_element.find_element(By.XPATH, "..")
                    driver.execute_script("arguments[0].click();", parent)
                except: pass
                try: 
                    grand = target_element.find_element(By.XPATH, "../..")
                    driver.execute_script("arguments[0].click();", grand)
                except: pass
                
                # 4. INTELLIGENT WAIT (The Fix) ⏳
                print("⏳ Waiting for table to stabilize...")
                # Wait for at least one row to appear
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "tr")))
                
                # Loop to ensure all rows are loaded
                previous_row_count = 0
                stable_checks = 0
                
                for _ in range(10): # Try for 20 seconds max
                    rows = driver.find_elements(By.TAG_NAME, "tr")
                    current_count = len(rows)
                    print(f"   -> Rows visible: {current_count}")
                    
                    if current_count == previous_row_count and current_count > 5:
                        stable_checks += 1
                        if stable_checks >= 2: # Stable for 4 seconds
                            print("✅ Table Stabilized.")
                            break
                    else:
                        stable_checks = 0 # Reset if count changes
                    
                    previous_row_count = current_count
                    time.sleep(2) # Wait 2 seconds between checks
                
                # 5. Scan for Data
                full_text = driver.find_element(By.TAG_NAME, "body").text
                all_fractions = re.findall(r'\d+\s*/\s*\d+', full_text)
                
                print(f"📊 Fractions Found: {all_fractions}")
                
                if len(all_fractions) > 1:
                    # Logic: If we found multiple fractions, the LAST one is the Total
                    final_fraction = all_fractions[-1] 
                    log_status = f"Success. Found {len(all_fractions)} matches."
                    print(f"🎯 FOUND TOTAL: {final_fraction}")
                elif len(all_fractions) == 1:
                     # Fallback: If only 1 found (e.g. 0/5), force wait and try once more
                    print("⚠️ Only 1 match found. Waiting 5s extra...")
                    time.sleep(5)
                    full_text = driver.find_element(By.TAG_NAME, "body").text
                    all_fractions = re.findall(r'\d+\s*/\s*\d+', full_text)
                    if all_fractions:
                        final_fraction = all_fractions[-1]
                        log_status = "Success (After Extra Wait)"
                    else:
                        log_status = "Only 1 match found (Header?)"

            except Exception as e:
                log_status = f"Nav Error: {str(e)[:50]}"
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
