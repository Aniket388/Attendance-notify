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

# 🎨 PREMIUM DARK UI (Interactive Parallax + Glassmorphism)
HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NIET Attendance Bot</title>
    <style>
        :root {
            --bg-color: #050505;
            --glass-bg: rgba(20, 20, 20, 0.6);
            --glass-border: rgba(255, 255, 255, 0.1);
            --text-main: #ffffff;
            --text-muted: #a1a1aa;
            --accent: #2563eb;
            --accent-glow: rgba(37, 99, 235, 0.5);
        }

        * { box-sizing: border-box; transition: all 0.2s ease-out; }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
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

        /* 🌌 AMBIENT BACKGROUND LAYER */
        .background-layer {
            position: absolute;
            top: 0; left: 0; width: 100%; height: 100%;
            z-index: -1;
            overflow: hidden;
        }

        .orb {
            position: absolute;
            border-radius: 50%;
            filter: blur(100px);
            opacity: 0.6;
            animation: float 10s infinite alternate cubic-bezier(0.45, 0.05, 0.55, 0.95);
        }
        
        /* Brighter Colors & Faster Animation */
        .orb-1 { top: -10%; left: -10%; width: 60vw; height: 60vw; background: #4f46e5; animation-delay: 0s; }
        .orb-2 { bottom: -20%; right: -10%; width: 50vw; height: 50vw; background: #db2777; animation-delay: -2s; }
        .orb-3 { top: 40%; left: 30%; width: 40vw; height: 40vw; background: #0891b2; animation-delay: -4s; opacity: 0.4; }

        @keyframes float {
            0% { transform: translate(0, 0) scale(1); }
            100% { transform: translate(30px, 40px) scale(1.05); }
        }

        /* 🪟 GLASS CARD */
        .container {
            background: var(--glass-bg);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid var(--glass-border);
            padding: 3.5rem 2.5rem;
            border-radius: 24px;
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5);
            width: 90%;
            max-width: 400px;
            text-align: center;
            position: relative;
            z-index: 10;
        }

        /* 🤖 LOGO STYLING */
        h1 { 
            margin: 0 0 0.5rem; 
            font-size: 2.2rem; 
            font-weight: 700;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            text-shadow: 0 2px 10px rgba(0,0,0,0.3);
        }
        
        .logo-emoji { font-size: 1.1em; }

        p { color: var(--text-muted); margin-bottom: 2rem; font-size: 0.95rem; line-height: 1.6; }

        /* ⌨️ INPUT FIELDS */
        .input-group { margin-bottom: 15px; position: relative; }
        
        input {
            width: 100%;
            padding: 16px;
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid var(--glass-border);
            border-radius: 12px;
            color: #fff;
            font-size: 1rem;
            outline: none;
        }
        input:focus {
            border-color: var(--accent);
            background: rgba(0, 0, 0, 0.5);
            box-shadow: 0 0 0 2px var(--accent-glow);
            transform: scale(1.01);
        }
        input::placeholder { color: #666; }

        /* 🚀 BUTTON */
        button {
            width: 100%;
            padding: 16px;
            margin-top: 10px;
            background: linear-gradient(135deg, #2563eb, #1d4ed8);
            color: white;
            border: none;
            border-radius: 12px;
            font-weight: 600;
            font-size: 1.1rem;
            cursor: pointer;
            box-shadow: 0 4px 15px var(--accent-glow);
            position: relative;
            overflow: hidden;
        }
        
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(37, 99, 235, 0.6);
        }
        button:active { transform: scale(0.98); }

        /* 🔔 NOTIFICATIONS */
        .message {
            margin-top: 25px;
            padding: 15px;
            border-radius: 10px;
            font-size: 0.9rem;
            line-height: 1.4;
            animation: slideUp 0.4s ease-out;
        }
        .success { background: rgba(16, 185, 129, 0.2); color: #6ee7b7; border: 1px solid rgba(16, 185, 129, 0.3); }
        .error { background: rgba(239, 68, 68, 0.2); color: #fca5a5; border: 1px solid rgba(239, 68, 68, 0.3); }
        
        @keyframes slideUp { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

        .footer { margin-top: 2.5rem; font-size: 0.75rem; color: #555; font-weight: 500; letter-spacing: 0.5px; text-transform: uppercase; }
        
        a { color: #777; text-decoration: none; border-bottom: 1px dotted #777; }
        a:hover { color: #fff; border-color: #fff; }

        /* 👁️ PASSWORD TOGGLE STYLE */
        .password-wrapper { position: relative; width: 100%; }
        .toggle-icon {
            position: absolute;
            right: 15px;
            top: 50%;
            transform: translateY(-50%);
            cursor: pointer;
            color: #888;
            padding: 5px;
            display: flex;
            align-items: center;
        }
        .toggle-icon:hover { color: #fff; }

    </style>
</head>
<body>

    <div class="background-layer" id="bg-layer">
        <div class="orb orb-1"></div>
        <div class="orb orb-2"></div>
        <div class="orb orb-3"></div>
    </div>

    <div class="container">
        <h1><span class="logo-emoji">🤖</span> NIET Bot</h1>
        <p>Automated attendance tracking. <br> Join 200+ students getting daily reports.</p>
        
        <form method="POST">
            <div class="input-group">
                <input type="text" name="college_id" placeholder="College ID (e.g. @niet.co.in)" required autocomplete="off">
            </div>
            
            <div class="input-group">
                <div class="password-wrapper">
                    <input type="password" id="passwordInput" name="password" placeholder="ERP Password" required style="padding-right: 45px;">
                    <span class="toggle-icon" onclick="togglePassword()">
                        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                            <circle cx="12" cy="12" r="3"></circle>
                        </svg>
                    </span>
                </div>
            </div>

            <div class="input-group">
                <input type="email" name="email" placeholder="Your Personal Email" required autocomplete="off">
            </div>
            <button type="submit">Activate Bot 🚀</button>
        </form>

        {% if message %}
            <div class="message {{ status }}">{{ message }}</div>
        {% endif %}

        <div class="footer">Secure • Encrypted • <a href="https://github.com/Aniket388/Attendance-notify" target="_blank">Open Source</a></div>
    </div>

    <script>
        // 🌌 PARALLAX EFFECT
        document.addEventListener('mousemove', (e) => {
            const layer = document.getElementById('bg-layer');
            const x = (window.innerWidth - e.pageX * 2) / 50;
            const y = (window.innerHeight - e.pageY * 2) / 50;
            layer.style.transform = `translateX(${x}px) translateY(${y}px)`;
        });

        // 👁️ PASSWORD TOGGLE LOGIC
        function togglePassword() {
            const passwordInput = document.getElementById('passwordInput');
            const icon = document.querySelector('.toggle-icon');
            
            if (passwordInput.type === 'password') {
                passwordInput.type = 'text';
                icon.style.color = '#3b82f6'; // Blue when visible
            } else {
                passwordInput.type = 'password';
                icon.style.color = '#888'; // Grey when hidden
            }
        }
    </script>

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
