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
# 🟢 DIAGNOSTIC MODE: "WHAT DO YOU SEE?"
# ====================================================
LOGIN_URL = "https://nietcloud.niet.co.in/login.htm"
USER_BOX_ID = "j_username"
PASS_BOX_ID = "password-1"
LOGIN_BTN_SELECTOR = "button[type='submit']"

COLLEGE_USER = os.environ["COLLEGE_USER"]
COLLEGE_PASS = os.environ["COLLEGE_PASS"]

def main():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument('--ignore-certificate-errors')
    # Big window to make sure the bottom isn't hidden
    chrome_options.add_argument("--window-size=1920,1080")
    
    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 40)

    try:
        print("🚀 Opening NIET Cloud...")
        driver.get(LOGIN_URL)
        
        # 1. Login
        wait.until(EC.visibility_of_element_located((By.ID, USER_BOX_ID))).send_keys(COLLEGE_USER)
        driver.find_element(By.ID, PASS_BOX_ID).send_keys(COLLEGE_PASS)
        driver.find_element(By.CSS_SELECTOR, LOGIN_BTN_SELECTOR).click()
        
        # 2. Grab Dashboard Data
        wait.until(EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "Attendance"))
        dash_text = driver.find_element(By.TAG_NAME, "body").text
        p_match = re.search(r'(\d+\.\d+)%', dash_text)
        
        if p_match:
            final_percent = p_match.group(0)
            print(f"✅ Found Percent: {final_percent}")
            
            # 3. Click Sequence
            xpath_query = f"//*[contains(text(),'{final_percent}')]"
            target_element = driver.find_element(By.XPATH, xpath_query)
            
            # Force click the card
            try: driver.execute_script("arguments[0].click();", target_element)
            except: pass
            try: 
                parent = target_element.find_element(By.XPATH, "..")
                driver.execute_script("arguments[0].click();", parent)
            except: pass
            try: 
                grand = target_element.find_element(By.XPATH, "../..")
                driver.execute_script("arguments[0].click();", grand)
            except: pass
            
            # 4. Wait for Table
            print("⏳ Waiting for Detailed Table...")
            wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(),'Course Name')]")))
            
            # 5. DUMP ALL FRACTIONS (This is what you asked for)
            full_text = driver.find_element(By.TAG_NAME, "body").text
            
            print("\n" + "="*40)
            print("👀 ROBOT VISION REPORT")
            print("="*40)
            
            # Use findall to get EVERY match, not just the first one
            all_fractions = re.findall(r'\d+\s*/\s*\d+', full_text)
            
            print(f"Total Matches Found: {len(all_fractions)}")
            print("List of values found:")
            for i, val in enumerate(all_fractions):
                print(f"   [{i}] {val}")
                
            print("="*40)
            
            if all_fractions:
                print(f"👉 The First One (What it used before): {all_fractions[0]}")
                print(f"👉 The Last One (What we want): {all_fractions[-1]}")
            else:
                print("❌ No fractions found!")

    except Exception as e:
        print(f"❌ Error: {e}")
    
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
