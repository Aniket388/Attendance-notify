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
# 🛡️ BOT V9.2: BULLETPROOF AJAX + MODERN UI EDITION
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

def get_personality(percentage):
    p = float(percentage)
    if p >= 90: return {"quote": "Absolute Legend! 🏆", "status": "Safe", "color": "#388E3C", "subject_icon": "🏆"}
    elif p >= 75: return {"quote": "You are Safe! ✅", "status": "Safe", "color": "#388E3C", "subject_icon": "✅"}
    elif p >= 60: return {"quote": "⚠️ Thin ice!", "status": "Low", "color": "#F57C00", "subject_icon": "⚠️"}
    else: return {"quote": "🚨 DANGER ZONE!", "status": "CRITICAL", "color": "#D32F2F", "subject_icon": "🚨"}

def send_email_via_api(target_email, subject, html_content):
    print(f"   📧 Sending to {target_email}...")
    try:
        creds_data = json.loads(TOKEN_JSON)
        creds = Credentials.from_authorized_user_info(creds_data)
        service = build('gmail', 'v1', credentials=creds)
        msg = MIMEMultipart("alternative")
        msg['Subject'] = subject
        msg['From'] = "me"
        msg['To'] = target_email
        msg.attach(MIMEText(html_content, "html", "utf-8"))
        raw_msg = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(userId="me", body={'raw': raw_msg}).execute()
        print("   ✅ Sent successfully!")
        return True
    except Exception as e:
        print(f"   ❌ API Send Failed: {e}")
        return False

def check_attendance_for_user(user):
    user_id = user['college_id']
    target_email = user['target_email']
    
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
    
    final_percent = "N/A"
    parsed_subjects = [] # 🆕 Store data here first before building HTML
    
    yesterday_obj = datetime.now() - timedelta(days=1)
    yesterday_str = yesterday_obj.strftime("%b %d,%Y")

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

        # 2. CLICK DASHBOARD WIDGET (Hardened)
        print("   🧭 Scanning Dashboard for Attendance Block...")
        
        # We wait for the specific structure of the dashboard to load
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(1) # Minor stabilization for dynamic dashboard widgets
        
        dash_text = driver.find_element(By.TAG_NAME, "body").text
        
        if p_match := re.search(r'(\d+\.\d+)%', dash_text):
            final_percent = p_match.group(0)
            print(f"   📊 Found Overall Percentage: {final_percent}")
            
            try:
                # 🛡️ BULLETPROOF FIX 1: Anchor click to Attendance section
                xpath_query = f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'attendance')]/ancestor::*//*[contains(text(),'{final_percent}')]"
                target = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_query)))
                driver.execute_script("arguments[0].click();", target)
            except:
                print("   ⚠️ Strict widget locator failed. Falling back to text match...")
                xpath_query = f"//*[contains(text(),'{final_percent}')]"
                target = driver.find_element(By.XPATH, xpath_query)
                driver.execute_script("arguments[0].click();", target)
                
            try: driver.execute_script("arguments[0].click();", target.find_element(By.XPATH, ".."))
            except: pass
        else:
            print("   ❌ Could not find percentage on dashboard.")
            return

        # 3. WAIT FOR MAIN ATTENDANCE TABLE
        print("   ⏳ Waiting for Summary Table...")
        main_table_xpath = "//table[contains(., 'Course Name')]"
        wait.until(EC.presence_of_element_located((By.XPATH, main_table_xpath)))
        time.sleep(1) # Let DOM settle
        
        # 4. START SCRAPING (AJAX Flow)
        target_table = driver.find_element(By.XPATH, main_table_xpath)
        initial_rows = target_table.find_elements(By.TAG_NAME, "tr")
        row_count = len(initial_rows)
        
        print(f"   📋 Scanning {row_count} subjects...")

        grand_total_row = None

        for i in range(row_count):
            try:
                # Re-find main table to avoid stale elements
                current_table = driver.find_element(By.XPATH, main_table_xpath)
                current_rows = current_table.find_elements(By.TAG_NAME, "tr")
                
                if i >= len(current_rows): break
                row = current_rows[i]
                cols = row.find_elements(By.TAG_NAME, "td")
                
                if len(cols) < 4: continue
                subj_name = cols[1].text.strip()
                if not subj_name: continue
                
                count_text = cols[-2].text.strip()
                per = cols[-1].text.strip()

                if "Total" in cols[0].text:
                    grand_total_row = {"name": "GRAND TOTAL", "percent": per, "count": count_text}
                    continue

                # Default yesterday status
                y_status = "No Class"

                # ==========================================
                # 🛡️ THE BULLETPROOF AJAX EXTRACTOR
                # ==========================================
                try:
                    link_element = cols[-2].find_element(By.TAG_NAME, "a")
                    driver.execute_script("arguments[0].click();", link_element)
                    
                    # Prevent regex/XPath failure on weird characters in subject name
                    clean_subj = subj_name.split()[0][:10] if subj_name else ""
                    
                    # Wait for specific header to avoid race conditions with old tables
                    detail_header_xpath = f"//*[contains(text(), 'Attendance Details') and contains(text(), '{clean_subj}')]"
                    
                    try:
                        wait.until(EC.presence_of_element_located((By.XPATH, detail_header_xpath)))
                    except:
                        # Fallback if text matching is too strict
                        detail_header_xpath = "//*[contains(text(), 'Attendance Details')]"
                        wait.until(EC.presence_of_element_located((By.XPATH, detail_header_xpath)))
                    
                    # Anchor table directly to the header
                    detail_table_xpath = f"({detail_header_xpath}/following::table)[1]"
                    
                    try:
                        detail_table = driver.find_element(By.XPATH, detail_table_xpath)
                    except:
                        # Final fallback if structure is bizarre
                        all_tables = driver.find_elements(By.TAG_NAME, "table")
                        detail_table = all_tables[-1]
                        
                    detail_rows = detail_table.find_elements(By.TAG_NAME, "tr")
                    
                    daily_statuses = []
                    
                    for d_row in reversed(detail_rows):
                        d_cols = d_row.find_elements(By.TAG_NAME, "td")
                        if len(d_cols) < 5: continue
                        
                        d_date_str = d_cols[1].text.strip()
                        d_stat = d_cols[4].text.strip() 
                        
                        if d_date_str == yesterday_str:
                            if d_stat == "P": daily_statuses.append("P")
                            else: daily_statuses.append("A")
                        
                        try:
                            current_row_date = datetime.strptime(d_date_str, "%b %d,%Y")
                            if current_row_date.date() < yesterday_obj.date(): break
                        except: pass
                        
                    if not daily_statuses: y_status = "No Class"
                    elif all(s == "P" for s in daily_statuses): y_status = "Present"
                    else: y_status = "Absent"
                        
                except Exception as e:
                    print(f"   ⚠️ Details scrape failed for {subj_name}")
                    y_status = "Error"
                
                # 🆕 Append clean data to our list
                parsed_subjects.append({
                    "name": subj_name,
                    "percent": per,
                    "count": count_text,
                    "yesterday": y_status
                })
            
            except Exception as row_e: continue

        # ==========================================
        # 🎨 BUILD MODERN HTML EMAIL
        # ==========================================
        try:
            val = float(re.search(r'\d+\.?\d*', final_percent).group())
            personality = get_personality(val)
        except: 
            personality = {"quote": "Update", "status": "Update", "color": "#1976D2", "subject_icon": "📅"}

        table_html = ""
        for subj in parsed_subjects:
            # Color Logic
            p_val = float(subj['percent']) if subj['percent'].replace('.','',1).isdigit() else 100
            p_color = "#d32f2f" if p_val < 75 else "#202124"
            p_weight = "bold" if p_val < 75 else "600"

            # Badge Logic
            if subj['yesterday'] == "Present":
                badge = "<span style='background-color:#e6f4ea; color:#137333; padding:4px 10px; border-radius:12px; font-size:0.75em; font-weight:700; letter-spacing:0.3px; text-transform:uppercase;'>Present</span>"
            elif subj['yesterday'] == "Absent":
                badge = "<span style='background-color:#fce8e6; color:#c5221f; padding:4px 10px; border-radius:12px; font-size:0.75em; font-weight:700; letter-spacing:0.3px; text-transform:uppercase;'>Absent</span>"
            else:
                badge = "<span style='color:#bdc1c6; font-size:1.2em; font-weight:bold;'>-</span>"

            table_html += f"""
            <tr style="border-bottom: 1px solid #f1f3f4;">
                <td style="padding: 14px 16px; font-size: 0.9em; color: #3c4043; line-height: 1.4;">{subj['name']}</td>
                <td style="padding: 14px 16px; text-align: right; white-space: nowrap;">
                    <div style="font-size: 0.95em; color: {p_color}; font-weight: {p_weight};">{subj['percent']}%</div>
                    <div style="font-size: 0.75em; color: #80868b; margin-top: 2px;">{subj['count']}</div>
                </td>
                <td style="padding: 14px 16px; text-align: right; white-space: nowrap; width: 80px;">
                    {badge}
                </td>
            </tr>
            """

        # Add Grand Total Row if it exists
        if grand_total_row:
            table_html += f"""
            <tr style="background-color: #f8f9fa;">
                <td style="padding: 16px; font-size: 0.9em; color: #202124; font-weight: 700;">{grand_total_row['name']}</td>
                <td style="padding: 16px; text-align: right; font-size: 0.95em; color: #202124; font-weight: 700;" colspan="2">
                    {grand_total_row['percent']}% <span style="font-size:0.8em; color:#5f6368; font-weight:normal;">({grand_total_row['count']})</span>
                </td>
            </tr>
            """

        subject_line = f"{personality['subject_icon']} Attendance: {final_percent}"
        
        # Unified Modern Card Template
        html_body = f"""
        <div style="background-color: #f4f6f8; padding: 20px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
            <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.05); border: 1px solid #e8eaed;">
                
                <div style="background-color: {personality['color']}; padding: 32px 20px; text-align: center;">
                    <h1 style="margin: 0; font-size: 3.2em; font-weight: 800; color: #ffffff; letter-spacing: -1px;">{final_percent}</h1>
                    <p style="margin: 8px 0 0 0; font-size: 1.1em; color: rgba(255,255,255,0.9); font-weight: 500; text-transform: uppercase; letter-spacing: 1px;">{personality['status']}</p>
                </div>

                <table style="width: 100%; border-collapse: collapse; margin-top: 10px;">
                    <thead>
                        <tr style="border-bottom: 2px solid #e8eaed;">
                            <th style="padding: 12px 16px; text-align: left; font-size: 0.75em; text-transform: uppercase; color: #5f6368; font-weight: 600; letter-spacing: 0.5px;">Subject</th>
                            <th style="padding: 12px 16px; text-align: right; font-size: 0.75em; text-transform: uppercase; color: #5f6368; font-weight: 600; letter-spacing: 0.5px;">Status</th>
                            <th style="padding: 12px 16px; text-align: right; font-size: 0.75em; text-transform: uppercase; color: #5f6368; font-weight: 600; letter-spacing: 0.5px;">Yesterday</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_html}
                    </tbody>
                </table>

                <div style="padding: 24px 20px; text-align: center; background-color: #ffffff; border-top: 1px solid #e8eaed;">
                    <p style="margin: 0; color: #5f6368; font-style: italic; font-size: 0.95em;">"{personality['quote']}"</p>
                </div>
                
                <div style="background-color: #f8f9fa; padding: 12px; text-align: center; font-size: 0.7em; color: #9aa0a6; border-top: 1px solid #e8eaed;">
                    NIET Attendance Bot • Modern Edition
                </div>
            </div>
        </div>
        """
        
        send_email_via_api(target_email, subject_line, html_body)

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

    print(f"🚀 BOT V9.2 STARTED")

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
