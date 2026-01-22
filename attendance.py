import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ====================================================
# 🕵️‍♂️ ROOT CAUSE DEBUGGER
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
    
    driver = webdriver.Chrome(options=chrome_options)
    # Extremely long wait time to rule out slow internet
    wait = WebDriverWait(driver, 60) 

    try:
        print("🔍 STEP 1: Opening URL...")
        driver.get(LOGIN_URL)
        
        print("🔍 STEP 2: Logging in...")
        wait.until(EC.visibility_of_element_located((By.ID, USER_BOX_ID))).send_keys(COLLEGE_USER)
        driver.find_element(By.ID, PASS_BOX_ID).send_keys(COLLEGE_PASS)
        driver.find_element(By.CSS_SELECTOR, LOGIN_BTN_SELECTOR).click()
        
        print("🔍 STEP 3: Waiting for Dashboard...")
        # We wait specifically for the word "Attendance" to verify we are on the right page
        wait.until(EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "Attendance"))
        print("✅ Dashboard detected!")
        
        # Wait 5 extra seconds for the table to populate
        time.sleep(5)
        
        print("🔍 STEP 4: Dumping Page Data...")
        # This will print what the robot actually sees
        body_text = driver.find_element(By.TAG_NAME, "body").text
        
        print("="*40)
        print("--- ROBOT VISION START ---")
        print(body_text) # <--- THIS IS WHAT WE NEED TO SEE
        print("--- ROBOT VISION END ---")
        print("="*40)
        
        # Test finding the specific row
        print("🔍 STEP 5: Testing Table Search...")
        rows = driver.find_elements(By.TAG_NAME, "tr")
        print(f"📊 Found {len(rows)} table rows.")
        
        if len(rows) > 0:
            print(f"Last Row Text: {rows[-1].text}")
        
    except Exception as e:
        print(f"❌ CRASH: {e}")
    
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
