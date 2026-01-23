from flask import Flask, request, render_template_string
from supabase import create_client
from cryptography.fernet import Fernet
import os

app = Flask(__name__)

# ==========================================
# ⚙️ CONFIGURATION (Load from Environment)
# ==========================================
# We use os.environ so secrets are safe in Vercel Settings
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
MASTER_KEY   = os.environ.get("MASTER_KEY")

# HTML Template (The User Interface)
HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>NIET Attendance Bot</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: -apple-system, sans-serif; background: #f4f4f9; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .container { background: white; padding: 2rem; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); width: 100%; max-width: 400px; }
        h1 { color: #333; text-align: center; margin-bottom: 0.5rem; }
        p { color: #666; text-align: center; margin-bottom: 1.5rem; font-size: 0.9rem; }
        input { width: 100%; padding: 10px; margin: 8px 0; border: 1px solid #ddd; border-radius: 6px; box-sizing: border-box; }
        button { width: 100%; padding: 12px; background: #0070f3; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: bold; margin-top: 10px; }
        button:hover { background: #0051a2; }
        .message { padding: 10px; margin-top: 15px; border-radius: 6px; text-align: center; font-size: 0.9rem; }
        .success { background: #e6fffa; color: #0070f3; border: 1px solid #b2f5ea; }
        .error { background: #fff5f5; color: #c53030; border: 1px solid #fed7d7; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 NIET Bot</h1>
        <p>Get daily attendance reports in your inbox.</p>
        
        <form method="POST">
            <input type="text" name="college_id" placeholder="College ID (e.g. 0221cse054)" required>
            <input type="password" name="password" placeholder="NIET Password" required>
            <input type="email" name="email" placeholder="Target Email" required>
            <button type="submit">Activate Bot 🚀</button>
        </form>

        {% if message %}
            <div class="message {{ status }}">{{ message }}</div>
        {% endif %}
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
            # 1. Get Data from Form
            college_id = request.form.get('college_id')
            password = request.form.get('password')
            email = request.form.get('email')

            # 2. Setup Tools
            if not SUPABASE_URL or not MASTER_KEY:
                return render_template_string(HTML_PAGE, message="❌ Server Config Error: Missing Secrets", status="error")
            
            supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
            cipher = Fernet(MASTER_KEY.encode())

            # 3. Encrypt Password
            encrypted_pass = cipher.encrypt(password.encode()).decode()

            # 4. Save to Database
            # Check if user exists first to decide Insert or Update
            check = supabase.table("users").select("*").eq("college_id", college_id).execute()
            
            data = {
                "college_id": college_id,
                "encrypted_pass": encrypted_pass,
                "target_email": email,
                "is_active": True
            }

            if check.data:
                supabase.table("users").update(data).eq("college_id", college_id).execute()
                message = "✅ Updated! You are all set."
            else:
                supabase.table("users").insert(data).execute()
                message = "🎉 Success! Welcome aboard."
            
            status = "success"

        except Exception as e:
            message = f"❌ Error: {str(e)}"
            status = "error"

    return render_template_string(HTML_PAGE, message=message, status=status)
