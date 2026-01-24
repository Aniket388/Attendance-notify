from flask import Flask, request, render_template_string
from supabase import create_client
from cryptography.fernet import Fernet
import os

app = Flask(__name__)

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
MASTER_KEY   = os.environ.get("MASTER_KEY")

# 🎨 MODERN DARK UI (Glassmorphism + Moving Aurora)
HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NIET Attendance Bot</title>
    <style>
        :root {
            --bg-color: #0a0a0a;
            --glass-bg: rgba(255, 255, 255, 0.03);
            --glass-border: rgba(255, 255, 255, 0.08);
            --text-main: #ededed;
            --text-muted: #888;
            --accent: #3b82f6;
            --accent-hover: #2563eb;
        }

        * { box-sizing: border-box; transition: all 0.3s ease; }
        
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            overflow: hidden;
            position: relative;
        }

        /* 🌌 MOVING BACKGROUND */
        .orb {
            position: absolute;
            border-radius: 50%;
            filter: blur(80px);
            z-index: -1;
            opacity: 0.4;
            animation: float 20s infinite alternate;
        }
        .orb-1 { top: -10%; left: -10%; width: 50vw; height: 50vw; background: #4c1d95; animation-delay: 0s; }
        .orb-2 { bottom: -10%; right: -10%; width: 40vw; height: 40vw; background: #0f4c75; animation-delay: -5s; }
        .orb-3 { top: 40%; left: 40%; width: 30vw; height: 30vw; background: #be185d; animation-delay: -10s; }

        @keyframes float {
            0% { transform: translate(0, 0) scale(1); }
            100% { transform: translate(30px, 50px) scale(1.1); }
        }

        /* 🪟 GLASS CARD */
        .container {
            background: var(--glass-bg);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid var(--glass-border);
            padding: 3rem;
            border-radius: 24px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
            width: 100%;
            max-width: 420px;
            text-align: center;
            animation: popIn 0.8s cubic-bezier(0.2, 0.8, 0.2, 1);
        }

        @keyframes popIn {
            0% { opacity: 0; transform: translateY(20px) scale(0.95); }
            100% { opacity: 1; transform: translateY(0) scale(1); }
        }

        h1 { margin: 0 0 0.5rem; font-size: 2rem; letter-spacing: -1px; background: linear-gradient(to right, #fff, #aaa); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        p { color: var(--text-muted); margin-bottom: 2rem; font-size: 0.95rem; line-height: 1.5; }

        /* ⌨️ INPUTS */
        input {
            width: 100%;
            padding: 14px 16px;
            margin-bottom: 12px;
            background: rgba(0, 0, 0, 0.2);
            border: 1px solid var(--glass-border);
            border-radius: 12px;
            color: #fff;
            font-size: 1rem;
            outline: none;
        }
        input:focus {
            border-color: var(--accent);
            background: rgba(0, 0, 0, 0.4);
            box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.1);
        }
        input::placeholder { color: #555; }

        /* 🚀 BUTTON */
        button {
            width: 100%;
            padding: 14px;
            margin-top: 10px;
            background: var(--accent);
            color: white;
            border: none;
            border-radius: 12px;
            font-weight: 600;
            font-size: 1rem;
            cursor: pointer;
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
        }
        button:hover {
            background: var(--accent-hover);
            transform: translateY(-2px);
            box-shadow: 0 6px 16px rgba(59, 130, 246, 0.4);
        }
        button:active { transform: translateY(0); }

        /* 🔔 MESSAGES */
        .message {
            margin-top: 20px;
            padding: 12px;
            border-radius: 8px;
            font-size: 0.9rem;
            animation: fadeIn 0.5s ease;
        }
        .success { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.2); }
        .error { background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.2); }
        
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

        .footer { margin-top: 2rem; font-size: 0.75rem; color: #444; }
    </style>
</head>
<body>

    <div class="orb orb-1"></div>
    <div class="orb orb-2"></div>
    <div class="orb orb-3"></div>

    <div class="container">
        <h1>🤖 NIET Bot</h1>
        <p>Automated attendance tracking. <br> Join 200+ students getting daily reports.</p>
        
        <form method="POST">
            <input type="text" name="college_id" placeholder="College ID (e.g. @niet.co.in)" required autocomplete="off">
            <input type="password" name="password" placeholder="ERP Password" required>
            <input type="email" name="email" placeholder="Your Personal Email" required autocomplete="off">
            <button type="submit">Activate Bot 🚀</button>
        </form>

        {% if message %}
            <div class="message {{ status }}">{{ message }}</div>
        {% endif %}

        <div class="footer">Secure • Encrypted • Automated</div>
    </div>

</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def home():
    message = None
    status = ""

    if request.method == 'POST':
        try:
            # 1. Get Data & CLEAN IT
            college_id = request.form.get('college_id', '').strip().lower()
            password = request.form.get('password', '').strip()
            email = request.form.get('email', '').strip()

            # 🛡️ VALIDATION RULE 1: Must be an NIET Email
            if not college_id.endswith("@niet.co.in"):
                 return render_template_string(HTML_PAGE, message="❌ Invalid ID! Please use your official college email (e.g., @niet.co.in)", status="error")

            # 🛡️ VALIDATION RULE 2: No empty passwords
            if not password:
                 return render_template_string(HTML_PAGE, message="❌ Password cannot be empty.", status="error")

            # 2. Setup Tools
            if not SUPABASE_URL or not MASTER_KEY:
                return render_template_string(HTML_PAGE, message="❌ Server Config Error: Missing Secrets", status="error")
            
            supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
            cipher = Fernet(MASTER_KEY.encode())

            # 3. Encrypt Password
            encrypted_pass = cipher.encrypt(password.encode()).decode()

            # 4. Save to Database (Reset fail_count to 0 on new update)
            check = supabase.table("users").select("*").eq("college_id", college_id).execute()
            
            data = {
                "college_id": college_id,
                "encrypted_pass": encrypted_pass,
                "target_email": email,
                "is_active": True,
                "fail_count": 0  # Reset this if they are updating their password!
            }

            if check.data:
                supabase.table("users").update(data).eq("college_id", college_id).execute()
                message = "✅ Welcome Back! Your details are updated."
            else:
                supabase.table("users").insert(data).execute()
                message = "🎉 You're in! Expect an email tomorrow morning."
            
            status = "success"

        except Exception as e:
            message = f"❌ Error: {str(e)}"
            status = "error"

    return render_template_string(HTML_PAGE, message=message, status=status)
