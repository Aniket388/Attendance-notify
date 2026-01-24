# 🤖 NIET Attendance Bot (Automated)

A high-performance, self-healing Python bot that tracks attendance on the NIET Cloud portal.
Built for scale, it uses parallel processing to handle hundreds of students in minutes.

### 🌟 Features
* **Zero Cost:** Runs 100% free on GitHub Actions & Supabase.
* **Smart:** Auto-skips holidays and deactivated users.
* **Fast:** Uses "Matrix Strategy" (4x parallel workers) to check 200+ students in <10 mins.
* **Resilient:** Auto-handles pop-ups, alerts, and server timeouts.
* **Personality:** Sends motivational emails with "Safe/Danger" status and exact class counts.

### 🛠️ Tech Stack
* **Python + Selenium:** For web automation.
* **GitHub Actions:** For daily scheduling (CRON).
* **Supabase (PostgreSQL):** For secure user management.
* **Gmail API:** For sending rich HTML emails.

### ⚠️ Disclaimer
This is an educational project designed to help students track their attendance stats easily.
