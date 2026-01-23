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
# 🟢 V2 ENGINE: FULL TABLE & MULTI-USER READY
# ====================================================

# CONFIGURATION
LOGIN_URL = "https://nietcloud.niet.co.in/login.htm"
USER_BOX_ID = "j_username"
PASS_BOX_ID = "password-1"
LOGIN_BTN_SELECTOR = "button[type='submit']"

# Credentials from Environment (For now)
COLLEGE_USER = os.environ["COLLEGE_USER"]
COLLEGE_PASS = os.environ["COLLEGE_PASS"]
SENDER_EMAIL = os.environ["EMAIL_USER"]
SENDER_PASS  = os.environ["EMAIL_PASS"]
TARGET_EMAIL = os.environ["TARGET_EMAIL"]

def send_full_report(percentage_text, fraction_text, table_rows_html, status_msg):
    """Sends a beautiful HTML email with the full subject breakdown."""
    msg = MIMEMultipart("alternative")
    
    # Smart Alert System
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

    html_content = f"""
    <html>
      <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f4f4; padding: 10px;">
        <div style="background-color: white; max-width: 600px; margin: auto; border-top: 6px solid {color}; padding: 20px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
            
            <div style="text-align: center; border-bottom: 2px solid #f0f0f0; padding-bottom: 15px; margin-bottom: 20px;">
                <h2 style="color: {color}; margin: 0; font-size: 22px; text-transform: uppercase; letter-spacing: 1px;">{alert}</h2>
                <h1 style="color: #333; font-size: 42px; margin: 10px 0; font-weight: 800;">{percentage_text}</h1>
                <p style="font-size: 16px; color: #666; margin: 0;">Attended: <strong>{fraction_text}</strong> classes</p>
            </div>

            <h3 style="color: #444; font-size: 16px; margin-bottom: 12px; border-left: 4px solid {color}; padding-left: 10px;">📊 Detailed Report</h3>
            <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                <thead style="background-color: #f8f9fa;">
                    <tr>
                        <th style="padding: 12px; border-bottom: 2px solid #ddd; text-align: left; color: #555;">Subject</th>
                        <th style="padding: 12px; border-bottom: 2px solid #ddd; text-align: center; color: #555;">Count</th>
                        <th style="padding: 12px; border-bottom: 2px solid #ddd; text-align: right; color: #555;">%</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows_html}
                </tbody>
            </table>

            <div style="margin-top: 30px; text-align: center; font-size: 11px; color: #aaa; border-top: 1px solid #eee; padding-top: 10px;">
                <p>Status: {status_msg} • NIET Attendance Bot V2</p>
            </div>
        </div>
      </body>
    </html>
    """
    msg.attach(MIMEText(html_content, "html"))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASS)
            server.sendmail(SENDER_EMAIL, TARGET_EMAIL, msg.as_string())
        print("✅ FULL REPORT SENT SUCCESSFULLY!")
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
    wait = WebDriverWait(driver, 50) # 50s Timeout

    final_percent = "N/A"
    final_fraction = "N/A"
    table_html = ""
    log_status = "Init"

    try:
        print("🚀 Opening NIET Cloud...")
        driver.get(LOGIN_URL)
        
        # 1. Login
        wait.until(EC.visibility_of_element_located((By.ID, USER_BOX_ID))).send_keys(COLLEGE_USER)
        driver.find_element(By.ID, PASS_BOX_ID).send_keys(COLLEGE_PASS)
        driver.find_element(By.CSS_SELECTOR, LOGIN_BTN_SELECTOR).click()
        
        # 2. Check Dashboard
        wait.until(EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "Attendance"))
        dash_text = driver.find_element(By.TAG_NAME, "body").text
        p_match = re.search(r'(\d+\.\d+)%', dash_text)
        
        if p_match:
            final_percent = p_match.group(0)
            
            # 3. Open Detailed View
            try:
                # Find any element with the percentage and click it/parents
                xpath_query = f"//*[contains(text(),'{final_percent}')]"
                target = driver.find_element(By.XPATH, xpath_query)
                driver.execute_script("arguments[0].click();", target)
                try: driver.execute_script("arguments[0].click();", target.find_element(By.XPATH, ".."))
                except: pass
                try: driver.execute_script("arguments[0].click();", target.find_element(By.XPATH, "../.."))
                except: pass
                
                # 4. Intelligent Table Wait
                print("⏳ Waiting for table to stabilize...")
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "tr")))
                time.sleep(2) # Initial buffer
                
                # Check for stability (wait until row count stops changing)
                last_count = 0
                for _ in range(5):
                    rows = driver.find_elements(By.TAG_NAME, "tr")
                    if len(rows) == last_count and len(rows) > 5:
                        break
                    last_count = len(rows)
                    time.sleep(1.5)
                
                # 5. Scrape Table Data
                print("📊 Extracting Table Rows...")
                rows = driver.find_elements(By.TAG_NAME, "tr")
                
                for row in rows:
                    cols = row.find_elements(By.TAG_NAME, "td")
                    # Valid rows usually have 4+ columns (Code, Name, ..., Count, %)
                    if len(cols) >= 4:
                        subj_name = cols[1].text.strip()
                        att_count = cols[-2].text.strip()
                        att_perc  = cols[-1].text.strip()
                        
                        # Formatting Logic
                        bg_style = "border-bottom: 1px solid #eee;"
                        row_style = ""
                        
                        # Highlight Total Row
                        if "Total" in cols[0].text or "Total" in subj_name:
                            bg_style = "background-color: #e8f5e9; font-weight: bold; border-top: 2px solid #aaa;"
                            subj_name = "GRAND TOTAL"
                        
                        # Highlight Low Attendance Rows
                        try:
                            if float(att_perc) < 75 and "Total" not in subj_name:
                                row_style = "color: #D32F2F;" # Red Text
                        except: pass

                        table_html += f"""
                        <tr style="{bg_style} {row_style}">
                            <td style="padding: 10px; text-align: left;">{subj_name}</td>
                            <td style="padding: 10px; text-align: center;">{att_count}</td>
                            <td style="padding: 10px; text-align: right;">{att_perc}%</td>
                        </tr>
                        """

                # 6. Extract Final Fraction for Subject Line
                full_text = driver.find_element(By.TAG_NAME, "body").text
                all_fractions = re.findall(r'\d+\s*/\s*\d+', full_text)
                if all_fractions:
                    final_fraction = all_fractions[-1]
                    log_status = "Success: Full Table"

            except Exception as e:
                log_status = f"Nav Error: {str(e)[:50]}"
                print(f"⚠️ Navigation Error: {e}")

        # 7. Send the Upgrade Email
        if final_percent != "N/A":
            send_full_report(final_percent, final_fraction, table_html, log_status)
        else:
            print("❌ Critical: No data found.")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
