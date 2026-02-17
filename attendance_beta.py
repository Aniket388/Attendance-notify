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
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# ====================================================
# 🕵️ BOT V8.9: THE INVESTIGATOR (NO GUESSING)
# ====================================================

LOGIN_URL = "https://nietcloud.niet.co.in/login.htm"
BETA_TARGET_ID = "0231csiot122@niet.co.in" 

# 1. LOAD SECRETS
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()
MASTER_KEY   = os.environ.get("MASTER_KEY", "").strip().encode()
TOKEN_JSON   = os.environ.get("GMAIL_TOKEN_JSON", "").strip()

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
        time.sleep(3) # Let DOM settle

        # ====================================================
        # 🔬 DIAGNOSTIC PHASE
        # ====================================================
        print("\n--- 🔬 DIAGNOSTICS START ---")
        print(f"🔎 DASHBOARD URL: {driver.current_url}")
        print(f"🔎 DASHBOARD TITLE: {driver.title}")
        
        # TEST 1: Check for frames/iframes
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        frames = driver.find_elements(By.TAG_NAME, "frame")
        print(f"🔎 FOUND {len(iframes)} IFRAMES and {len(frames)} FRAMES")
        
        # TEST 2: Scan for relevant links in Main Content
        print("🔎 SCANNING MAIN CONTENT FOR LINKS...")
        all_links = driver.find_elements(By.TAG_NAME, "a")
        print(f"   ➜ Total <a> tags: {len(all_links)}")
        
        attendance_candidates = []
        for link in all_links:
            href = link.get_attribute("href")
            text = link.text.strip()
            # We look for ANY link that might be attendance related
            if href and ("studentCourseFileNew" in href or "Attendance" in text or "attendance" in href):
                attendance_candidates.append(link)
                print(f"   🎯 CANDIDATE FOUND: Text='{text}' | Href='{href}' | Displayed={link.is_displayed()}")

        # TEST 3: Check inside Frames (if any)
        if len(iframes) > 0 or len(frames) > 0:
            print("🔎 SCANNING FRAMES...")
            # Combine both lists
            all_frames = iframes + frames
            for i, frame in enumerate(all_frames):
                try:
                    print(f"   ➜ Switching to Frame {i}...")
                    driver.switch_to.frame(frame)
                    
                    frame_links = driver.find_elements(By.TAG_NAME, "a")
                    print(f"     Found {len(frame_links)} links in frame.")
                    
                    for link in frame_links:
                        href = link.get_attribute("href")
                        text = link.text.strip()
                        if href and ("studentCourseFileNew" in href or "Attendance" in text):
                            print(f"     🎯 FRAME CANDIDATE: Text='{text}' | Href='{href}'")
                            
                    driver.switch_to.default_content()
                except Exception as e:
                    print(f"     ⚠️ Error scanning frame {i}: {e}")
                    driver.switch_to.default_content()

        print("--- 🔬 DIAGNOSTICS END ---\n")
        
        # If we found a candidate in main content, try to click it just to see
        if attendance_candidates:
            print("   🧪 Attempting to click the first candidate...")
            driver.execute_script("arguments[0].click();", attendance_candidates[0])
            time.sleep(5)
            print(f"   🔎 URL AFTER CLICK: {driver.current_url}")
        else:
            print("   ❌ NO CANDIDATES FOUND TO CLICK.")

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

    print(f"🚀 BOT V8.9 DIAGNOSTIC STARTED")

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
