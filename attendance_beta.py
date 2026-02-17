import os
import re
import time
import json
import base64
import argparse
import traceback
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from supabase import create_client, Client
from cryptography.fernet import Fernet

# ====================================================
# 🕵️ BOT V8.10: FINAL DIAGNOSTIC (SINGLE COMMIT)
# ====================================================

LOGIN_URL = "https://nietcloud.niet.co.in/login.htm"
BETA_TARGET_ID = "0231csiot122@niet.co.in" 

# 1. LOAD SECRETS
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()
MASTER_KEY   = os.environ.get("MASTER_KEY", "").strip().encode()

# 2. INIT CLIENTS
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
cipher = Fernet(MASTER_KEY)

def check_attendance_for_user(user):
    user_id = user['college_id']
    print(f"\n🔄 Processing: {user_id}")
    
    try:
        college_pass = cipher.decrypt(user['encrypted_pass'].encode()).decode()
    except:
        print("   ❌ Decryption Failed")
        return

    # BROWSER SETUP
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument('--ignore-certificate-errors')
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 30)

    try:
        # 1. LOGIN
        print("   ⏳ Logging in...")
        driver.get(LOGIN_URL)
        
        wait.until(EC.visibility_of_element_located((By.ID, "j_username"))).send_keys(user_id)
        driver.find_element(By.ID, "password-1").send_keys(college_pass)
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        
        try:
            WebDriverWait(driver, 5).until(EC.alert_is_present())
            driver.switch_to.alert.accept()
        except: pass

        print("   ⏳ Waiting for Dashboard (home.htm)...")
        wait.until(EC.url_contains("home.htm"))
        time.sleep(5) # Allow full DOM render

        # ====================================================
        # 🔬 DIAGNOSTIC BLOCK START
        # ====================================================
        print("\n===== DASHBOARD URL =====")
        print(driver.current_url)

        print("\n===== DASHBOARD TITLE =====")
        print(driver.title)

        print("\n===== DASHBOARD HTML PREVIEW (First 8000 chars) =====")
        try:
            print(driver.page_source[:8000])
        except:
            print("Error printing source")

        print("\n===== SEARCHING FOR studentCourseFileNew LINKS =====")
        candidates = driver.find_elements(
            By.XPATH,
            "//a[contains(@href,'studentCourseFileNew')]"
        )

        print("Found:", len(candidates))

        for idx, c in enumerate(candidates):
            print(f"\n--- LINK {idx} OUTER HTML ---")
            try:
                print(c.get_attribute("outerHTML"))
                print("Displayed:", c.is_displayed())
                print("Enabled:", c.is_enabled())
                print("Text Content:", c.text)
            except Exception as e:
                print(f"Error reading link {idx}: {e}")

        if candidates:
            print("\n===== PARENT ELEMENT STRUCTURE =====")
            try:
                parent = candidates[0].find_element(By.XPATH, "..")
                print(parent.get_attribute("outerHTML"))
                
                grandparent = parent.find_element(By.XPATH, "..")
                print("\n--- GRANDPARENT STRUCTURE ---")
                print(grandparent.get_attribute("outerHTML")[:500]) # First 500 chars
            except Exception as e:
                print(f"Error reading parent: {e}")

        print("\n===== SEARCHING FOR 'Academic Functions' MENU =====")
        academic_menu = driver.find_elements(By.XPATH, "//*[contains(text(), 'Academic Functions')]")
        print("Found Menu Items:", len(academic_menu))
        for m in academic_menu:
             # 🔧 FIXED: tagName -> tag_name
             print(f"   Tag: {m.tag_name} | Visible: {m.is_displayed()}")

        print("\n===== DIAGNOSTIC BLOCK END =====")
        # ====================================================

    except Exception as e:
        print(f"   ❌ FATAL ERROR: {e}")
        traceback.print_exc()
        
    finally:
        driver.quit()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard_id", type=int, default=0)
    parser.add_argument("--total_shards", type=int, default=1)
    args = parser.parse_args()

    print(f"🚀 BOT V8.10 DIAGNOSTIC STARTED")

    try:
        response = supabase.table("users").select("*").eq("is_active", True).eq("college_id", BETA_TARGET_ID).execute()
        all_users = response.data
        if not all_users:
            print(f"   ⚠️ Beta User {BETA_TARGET_ID} not found or inactive.")
            return

        print(f"   ✅ Found Beta User. Starting...")
        for user in all_users:
            check_attendance_for_user(user)
            
    except Exception as e:
        print(f"🔥 CRITICAL ERROR: {e}")

if __name__ == "__main__":
    main()
