import os
import smtplib
import re
import time
import traceback
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ====================================================
# 🔴 DIAGNOSTIC MODE: PAGE DUMP + ERROR TRACING
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
    # Set a big window size to ensure no data is hidden by "scroll"
    chrome_options.add_argument("--window-size=1920,1080")
    
    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 40)

    try:
        print("🔍 STEP 1: Logging in...")
        driver.get(LOGIN_URL)
        wait.until(EC.visibility_of_element_located((By.ID, USER_BOX_ID))).send_keys(COLLEGE_USER)
        driver.find_element(By.ID, PASS_BOX_ID).send_keys(COLLEGE_PASS)
        driver.find_element(By.CSS_SELECTOR, LOGIN_BTN_SELECTOR).click()
        
        print("🔍 STEP 2: Checking Dashboard...")
        wait.until(EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "Attendance"))
        dash_text = driver.find_element(By.TAG_NAME, "body").text
        
        p_match = re.search(r'(\d+\.\d+)%', dash_text)
        if p_match:
            final_percent = p_match.group(0)
            print(f"   -> Found Percentage: {final_percent}")
            
            # CLICK SEQUENCE
            print("🔍 STEP 3: Clicking 'Family Tree'...")
            xpath_query = f"//*[contains(text(),'{final_percent}')]"
            target_element = driver.find_element(By.XPATH, xpath_query)
            
            # Try clicking parent box
            parent_element = target_element.find_element(By.XPATH, "..")
            driver.execute_script("arguments[0].click();", parent_element)
            print("   -> Click sent.")

            # WAIT FOR TABLE
            print("🔍 STEP 4: Waiting for Detailed Table...")
            wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(),'Course Name')]")))
            print("   -> Table Loaded!")
            
            # PAGE DUMP (This is what you asked for)
            print("\n" + "="*40)
            print("👀 ROBOT VISION START (FULL PAGE TEXT)")
            print("="*40)
            full_text = driver.find_element(By.TAG_NAME, "body").text
            print(full_text)
            print("="*40)
            print("👀 ROBOT VISION END")
            print("="*40 + "\n")
            
            # ANALYZE FRACTIONS
            print("🔍 STEP 5: Analyzing Fractions...")
            # Find all patterns like "0/5", "21/46"
            all_fractions = re.findall(r'\d+\s*/\s*\d+', full_text)
            print(f"   -> List of all fractions found: {all_fractions}")
            
            if all_fractions:
                print(f"   -> First Item: {all_fractions[0]}")
                print(f"   -> Last Item (Should be Total): {all_fractions[-1]}")
            else:
                print("   -> NO FRACTIONS FOUND.")

    except Exception:
        print("\n❌ CRITICAL ERROR FOUND! HERE IS THE TRACEBACK:")
        print("="*60)
        traceback.print_exc()
        print("="*60)
    
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
