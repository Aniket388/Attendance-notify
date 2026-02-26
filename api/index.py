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

# 🎨 V2.0 PREMIUM TAILWIND UI
HTML_PAGE = """
<!DOCTYPE html>
<html class="dark" lang="en"><head>
<meta charset="utf-8"/>
<meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<title>NIET Daily Attendance Notifier</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&amp;display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=swap" rel="stylesheet"/>
<script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
<script id="tailwind-config">
        tailwind.config = {
          darkMode: "class",
          theme: {
            extend: {
              colors: {
                "primary": "#1978e5",
                "primary-light": "#6d52f6",
                "background-light": "#f6f7f8",
                "background-dark": "#111821",
                "surface-dark": "#1d1933",
                "surface-light": "#ffffff",
              },
              fontFamily: {
                "display": ["Inter", "sans-serif"],
              },
              borderRadius: {"DEFAULT": "0.25rem", "lg": "0.5rem", "xl": "0.75rem", "full": "9999px"},
              animation: {
                'float': 'float 6s ease-in-out infinite',
                'float-delayed': 'float 6s ease-in-out 3s infinite',
                'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
                'shimmer': 'shimmer 2s linear infinite',
                'typewriter': 'typewriter 3s steps(40) 1s forwards',
                'caret': 'caret 1s steps(1) infinite',
                'blob': 'blob 10s infinite',
              },
              keyframes: {
                float: {
                  '0%, 100%': { transform: 'translateY(0)' },
                  '50%': { transform: 'translateY(-20px)' },
                },
                shimmer: {
                  '0%': { backgroundPosition: '-200% 0' },
                  '100%': { backgroundPosition: '200% 0' },
                },
                typewriter: {
                  'to': { left: '100%' }
                },
                caret: {
                  '50%': { borderColor: 'transparent' }
                },
                blob: {
                  '0%': { transform: 'translate(0px, 0px) scale(1)' },
                  '33%': { transform: 'translate(30px, -50px) scale(1.1)' },
                  '66%': { transform: 'translate(-20px, 20px) scale(0.9)' },
                  '100%': { transform: 'translate(0px, 0px) scale(1)' },
                }
              }
            },
          },
        }
      </script>
<style>.glass-panel {
              background: rgba(29, 25, 51, 0.4);
              backdrop-filter: blur(16px);
              -webkit-backdrop-filter: blur(16px);
              border: 1px solid rgba(255, 255, 255, 0.05);
          }
          .glass-panel-heavy {
              background: rgba(17, 24, 33, 0.7);
              backdrop-filter: blur(20px);
              -webkit-backdrop-filter: blur(20px);
              border: 1px solid rgba(25, 120, 229, 0.2);
          }
          .neon-glow {
              box-shadow: 0 0 20px rgba(25, 120, 229, 0.4);
          }.typing-container {
            display: inline-block;
            position: relative;
          }
          .typing-text::after {
            content: '';
            position: absolute;
            right: -4px;
            top: 4px;
            bottom: 4px;
            width: 2px;
            background-color: currentColor;
            animation: caret 1s steps(1) infinite;
          }.mesh-gradient-bg {
              background-color: #0f172a;
              background-image: 
                  radial-gradient(at 0% 0%, rgba(29, 78, 216, 0.15) 0px, transparent 50%),
                  radial-gradient(at 100% 0%, rgba(124, 58, 237, 0.15) 0px, transparent 50%),
                  radial-gradient(at 100% 100%, rgba(29, 78, 216, 0.15) 0px, transparent 50%),
                  radial-gradient(at 0% 100%, rgba(124, 58, 237, 0.15) 0px, transparent 50%);
              background-size: 100% 100%;
              position: relative;
          }
          .blob-container {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            overflow: hidden;
            z-index: -1;
            pointer-events: none;
          }
          .blob {
            position: absolute;
            border-radius: 50%;
            filter: blur(80px);
            opacity: 0.4;
            animation: blob 20s infinite alternate;
          }
      </style>
</head>
<body class="bg-background-light dark:bg-background-dark text-slate-900 dark:text-slate-100 font-display min-h-screen flex flex-col overflow-x-hidden selection:bg-primary selection:text-white mesh-gradient-bg">
<div class="blob-container">
<div class="blob bg-primary/30 w-96 h-96 top-0 -left-20 animate-blob" style="animation-delay: 0s;"></div>
<div class="blob bg-purple-600/30 w-96 h-96 bottom-0 -right-20 animate-blob" style="animation-delay: 2s;"></div>
<div class="blob bg-blue-600/20 w-80 h-80 top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 animate-blob" style="animation-delay: 4s;"></div>
</div>
<header class="sticky top-0 z-50 glass-panel border-b border-white/5">
<div class="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
<div class="flex items-center gap-3">
<div class="w-10 h-10 rounded-lg bg-primary/20 flex items-center justify-center text-primary backdrop-blur-md">
<span class="material-symbols-outlined !text-3xl">school</span>
</div>
<h2 class="text-xl font-bold tracking-tight">Attendance Bot</h2>
</div>
<nav class="hidden md:flex items-center gap-8">
<a class="text-sm font-medium hover:text-primary transition-colors" href="#features">Features</a>
<a class="text-sm font-medium hover:text-primary transition-colors" href="#security">Security</a>
<a class="text-sm font-medium hover:text-primary transition-colors" href="#why-us">Why Us</a>
</nav>
</div>
</header>
<section class="relative pt-12 pb-20 lg:pt-24 lg:pb-32 overflow-hidden">
<div class="max-w-7xl mx-auto px-6 lg:px-8 relative z-10">
<div class="grid lg:grid-cols-2 gap-12 lg:gap-20 items-center">
<div class="flex flex-col gap-6">
<div class="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-primary/10 border border-primary/20 w-fit backdrop-blur-md shadow-lg shadow-primary/5">
<span class="relative flex h-2.5 w-2.5">
<span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
<span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-primary"></span>
</span>
<span class="text-xs font-bold text-primary uppercase tracking-wide">Exclusive for <span class="text-white text-sm mx-1 font-black">NIET</span> Students</span>
</div>
<h1 class="text-5xl lg:text-7xl font-black leading-tight tracking-tight drop-shadow-lg">
                        Daily Attendance <br/>
<span class="text-transparent bg-clip-text bg-gradient-to-r from-primary via-blue-400 to-purple-400">Notifier</span>
</h1>
<div class="h-16 lg:h-20">
<p class="text-lg text-slate-500 dark:text-slate-300 max-w-lg leading-relaxed typing-container drop-shadow-md">
<span class="typing-text">Currently exclusive to <strong class="text-white font-black text-xl">NIET</strong> College. Automated insights delivered straight to your inbox.</span>
</p>
</div>
<div class="flex flex-wrap gap-4 mt-4">
<div class="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400 bg-black/20 px-3 py-1.5 rounded-full backdrop-blur-sm border border-white/5">
<span class="material-symbols-outlined text-primary text-[18px]">check_circle</span>
<span>AES Encryption</span>
</div>
<div class="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400 bg-black/20 px-3 py-1.5 rounded-full backdrop-blur-sm border border-white/5">
<span class="material-symbols-outlined text-primary text-[18px]">check_circle</span>
<span>No Storage Policy</span>
</div>
</div>
</div>
<div class="relative group perspective-1000">
<div class="absolute -inset-1 bg-gradient-to-r from-primary to-purple-600 rounded-2xl blur-xl opacity-30 group-hover:opacity-60 transition duration-1000 group-hover:duration-200 animate-pulse-slow"></div>
<div class="relative glass-panel-heavy rounded-xl p-8 shadow-2xl transition-transform duration-500 hover:rotate-1 border border-white/10">
<div class="mb-8">
<h3 class="text-2xl font-bold mb-2 text-white">Activate Your Bot</h3>
<p class="text-slate-400 text-sm">Enter your credentials securely to start receiving updates.</p>
</div>
<form class="space-y-5" method="POST">
<div>
<label class="block text-sm font-medium mb-2 text-slate-300">College ID</label>
<div class="relative">
<div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
<span class="material-symbols-outlined text-[20px]">badge</span>
</div>
<input name="college_id" required class="w-full bg-black/30 border border-slate-700 rounded-lg py-3 pl-10 pr-4 text-white focus:ring-2 focus:ring-primary focus:border-transparent outline-none transition-all placeholder:text-slate-600 hover:border-slate-600" placeholder="0231csiot...@niet.co.in" type="text"/>
</div>
</div>
<div>
<label class="block text-sm font-medium mb-2 text-slate-300">ERP Password</label>
<div class="relative">
<div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
<span class="material-symbols-outlined text-[20px]">lock</span>
</div>
<input name="password" id="passwordInput" required class="w-full bg-black/30 border border-slate-700 rounded-lg py-3 pl-10 pr-10 text-white focus:ring-2 focus:ring-primary focus:border-transparent outline-none transition-all placeholder:text-slate-600 hover:border-slate-600" placeholder="••••••••" type="password"/>
<button type="button" onclick="togglePassword()" class="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-200 cursor-pointer">
<span class="material-symbols-outlined text-[20px]">visibility</span>
</button>
</div>
</div>
<div>
<label class="block text-sm font-medium mb-2 text-slate-300">Personal Email</label>
<div class="relative">
<div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
<span class="material-symbols-outlined text-[20px]">mail</span>
</div>
<input name="email" required class="w-full bg-black/30 border border-slate-700 rounded-lg py-3 pl-10 pr-4 text-white focus:ring-2 focus:ring-primary focus:border-transparent outline-none transition-all placeholder:text-slate-600 hover:border-slate-600" placeholder="student@gmail.com" type="email"/>
</div>
</div>
<button type="submit" class="relative w-full overflow-hidden bg-primary hover:bg-primary-light text-white font-bold py-3.5 rounded-lg neon-glow transition-all transform active:scale-[0.98] mt-4 flex items-center justify-center gap-2 group shadow-lg shadow-primary/30">
<div class="absolute inset-0 -translate-x-full group-hover:animate-[shimmer_1.5s_infinite] bg-gradient-to-r from-transparent via-white/20 to-transparent z-10"></div>
<span class="material-symbols-outlined relative z-20">rocket_launch</span>
<span class="relative z-20">Activate Bot</span>
</button>

{% if message %}
<div class="mt-5 p-4 rounded-lg text-sm flex items-center gap-3 backdrop-blur-sm 
    {{ 'bg-green-500/20 text-green-400 border border-green-500/30' if status == 'success' else 'bg-red-500/20 text-red-400 border border-red-500/30' }}">
    <span class="material-symbols-outlined">{{ 'check_circle' if status == 'success' else 'error' }}</span>
    {{ message }}
</div>
{% endif %}

<p class="text-xs text-center text-slate-500 mt-4">
                                By activating, you agree to our <a class="underline hover:text-primary transition-colors" href="#">Terms of Service</a>. We do not store your password.
                            </p>
</form>
</div>
</div>
</div>
</div>
</section>
<section class="py-20 relative z-10" id="features">
<div class="max-w-7xl mx-auto px-6">
<div class="text-center mb-16">
<h2 class="text-3xl md:text-4xl font-bold mb-4 text-white">Engineered for Efficiency</h2>
<p class="text-slate-400 max-w-2xl mx-auto backdrop-blur-sm py-2 rounded-lg">Everything you need to stay on top of your academic requirements without the hassle.</p>
</div>
<div class="grid grid-cols-1 md:grid-cols-3 gap-6 auto-rows-[250px]">
<div class="md:col-span-2 row-span-1 glass-panel bg-surface-dark/50 rounded-xl p-8 border border-slate-700/50 flex flex-col justify-between relative overflow-hidden group hover:-translate-y-2 hover:shadow-2xl hover:shadow-primary/10 transition-all duration-300 hover:bg-surface-dark/80">
<div class="absolute top-0 right-0 w-64 h-64 bg-primary/10 rounded-full blur-[60px] -mr-16 -mt-16 transition-all group-hover:bg-primary/20"></div>
<div class="relative z-10">
<div class="h-12 w-12 rounded-lg bg-green-500/20 text-green-500 flex items-center justify-center mb-4 border border-green-500/10">
<span class="material-symbols-outlined text-3xl">mark_email_read</span>
</div>
<h3 class="text-2xl font-bold mb-2 text-white">Automated Daily Emails</h3>
<p class="text-slate-400">Receive a comprehensive report every morning at 8:00 AM. Includes your current percentage, classes attended, and margin for leave.</p>
</div>
<div class="absolute bottom-4 right-4 opacity-20 dark:opacity-10 pointer-events-none group-hover:scale-110 transition-transform duration-500">
<svg fill="none" height="100" viewBox="0 0 200 100" width="200" xmlns="http://www.w3.org/2000/svg">
<path d="M10 80C40 80 50 20 80 20C110 20 120 60 150 60C180 60 190 10 200 10" stroke="currentColor" stroke-linecap="round" stroke-width="4"></path>
</svg>
</div>
</div>
<div class="glass-panel bg-surface-dark/50 rounded-xl p-8 border border-slate-700/50 flex flex-col justify-center items-center text-center group hover:border-primary/50 hover:-translate-y-2 hover:shadow-2xl hover:shadow-primary/10 transition-all duration-300 hover:bg-surface-dark/80">
<div class="h-14 w-14 rounded-full bg-blue-500/20 text-blue-500 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform border border-blue-500/10">
<span class="material-symbols-outlined text-3xl">shield_lock</span>
</div>
<h3 class="text-xl font-bold mb-2 text-white">Secure Login</h3>
<p class="text-sm text-slate-400">AES-256 encryption ensures your credentials are never exposed, even to us.</p>
</div>
<div class="glass-panel bg-surface-dark/50 rounded-xl p-8 border border-slate-700/50 flex flex-col justify-center items-center text-center group hover:border-primary/50 hover:-translate-y-2 hover:shadow-2xl hover:shadow-primary/10 transition-all duration-300 hover:bg-surface-dark/80">
<div class="h-14 w-14 rounded-full bg-purple-500/20 text-purple-500 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform border border-purple-500/10">
<span class="material-symbols-outlined text-3xl">analytics</span>
</div>
<h3 class="text-xl font-bold mb-2 text-white">Risk Analysis</h3>
<p class="text-sm text-slate-400">Color-coded alerts based on attendance thresholds (Red &lt; 75%, Green &gt; 75%).</p>
</div>
<div class="md:col-span-2 glass-panel bg-surface-dark/50 rounded-xl p-8 border border-slate-700/50 flex items-center gap-8 relative overflow-hidden hover:-translate-y-2 hover:shadow-2xl hover:shadow-primary/10 transition-all duration-300 hover:bg-surface-dark/80">
<div class="flex-1 z-10">
<div class="h-12 w-12 rounded-lg bg-orange-500/20 text-orange-500 flex items-center justify-center mb-4 border border-orange-500/10">
<span class="material-symbols-outlined text-3xl">dataset</span>
</div>
<h3 class="text-2xl font-bold mb-2 text-white">Smart Extraction</h3>
<p class="text-slate-400">Our bot parses the complex ERP table structure to isolate subject-wise data, delivering only the numbers that matter.</p>
</div>
<div class="hidden md:block w-1/3 h-full relative">
<div class="absolute inset-0 bg-gradient-to-t from-surface-dark to-transparent opacity-50"></div>
<div class="flex gap-2 items-end h-full pb-4 opacity-50 group-hover:opacity-80 transition-opacity">
<div class="w-4 bg-slate-600 h-[40%] rounded-t-sm group-hover:h-[50%] transition-all duration-700"></div>
<div class="w-4 bg-primary h-[80%] rounded-t-sm group-hover:h-[90%] transition-all duration-500"></div>
<div class="w-4 bg-slate-600 h-[60%] rounded-t-sm group-hover:h-[70%] transition-all duration-1000"></div>
<div class="w-4 bg-slate-600 h-[30%] rounded-t-sm group-hover:h-[40%] transition-all duration-700"></div>
<div class="w-4 bg-primary h-[90%] rounded-t-sm group-hover:h-[95%] transition-all duration-300"></div>
</div>
</div>
</div>
</div>
</div>
</section>
<section class="py-24 relative overflow-hidden z-10" id="why-us">
<div class="max-w-4xl mx-auto px-6 text-center">
<h2 class="text-sm font-bold text-primary uppercase tracking-widest mb-6">The Problem</h2>
<p class="text-3xl md:text-5xl font-extrabold leading-tight text-slate-900 dark:text-white mb-8 drop-shadow-lg">
                The anxiety of <span class="text-slate-400 line-through decoration-red-500 decoration-4">low attendance</span> shouldn't define your semester.
            </p>
<p class="text-xl text-slate-500 dark:text-slate-300 leading-relaxed font-light backdrop-blur-sm p-4 rounded-xl">
                Manually logging into a slow ERP portal every day is tedious. Calculating how many bunks you have left is stressful. We built this tool to make attendance data <span class="text-slate-900 dark:text-white font-semibold">invisible until you need it</span>, and <span class="text-slate-900 dark:text-white font-semibold">loud when you have to act</span>.
            </p>
</div>
</section>
<section class="py-20 border-y border-white/5 bg-black/20 backdrop-blur-sm relative z-10" id="security">
<div class="max-w-7xl mx-auto px-6">
<div class="flex flex-col md:flex-row items-start md:items-center justify-between mb-12 gap-6">
<div>
<h2 class="text-3xl font-bold text-white">Transparent Security</h2>
<p class="text-slate-400 mt-2">Built with a "Privacy First" architecture.</p>
</div>
<a class="text-primary font-medium flex items-center hover:underline" href="https://github.com/Aniket388/Attendance-notify">
                    View Source Code <span class="material-symbols-outlined ml-1 text-sm">open_in_new</span>
</a>
</div>
<div class="grid grid-cols-1 md:grid-cols-3 gap-8">
<div class="p-6 rounded-lg bg-surface-dark border-l-4 border-primary shadow-lg hover:shadow-xl hover:shadow-primary/5 transition-all hover:-translate-y-1">
<div class="mb-4">
<span class="material-symbols-outlined text-4xl text-white">cloud_sync</span>
</div>
<h3 class="text-lg font-bold mb-2 text-white">Serverless Architecture</h3>
<p class="text-sm text-slate-400">Powered by GitHub Actions runners. The bot spins up, checks data, sends the email, and destroys itself. No persistent server holds your session.</p>
</div>
<div class="p-6 rounded-lg bg-surface-dark border-l-4 border-primary shadow-lg hover:shadow-xl hover:shadow-primary/5 transition-all hover:-translate-y-1">
<div class="mb-4">
<span class="material-symbols-outlined text-4xl text-white">no_encryption</span>
</div>
<h3 class="text-lg font-bold mb-2 text-white">Read-Only Access</h3>
<p class="text-sm text-slate-400">The bot only reads your attendance table. It has zero capability to modify data, register for courses, or change profiles.</p>
</div>
<div class="p-6 rounded-lg bg-surface-dark border-l-4 border-primary shadow-lg hover:shadow-xl hover:shadow-primary/5 transition-all hover:-translate-y-1">
<div class="mb-4">
<span class="material-symbols-outlined text-4xl text-white">delete_forever</span>
</div>
<h3 class="text-lg font-bold mb-2 text-white">Ephemeral Data</h3>
<p class="text-sm text-slate-400">Your password is encrypted and stored in Supabase only for authentication. It is never logged in plain text.</p>
</div>
</div>
</div>
</section>
<footer class="bg-black/60 pt-16 pb-8 border-t border-white/5 relative z-10 backdrop-blur-md">
<div class="max-w-7xl mx-auto px-6 text-center">
<p class="text-sm font-semibold text-slate-400 uppercase tracking-widest mb-8">Powered by Modern Tech</p>
<div class="flex flex-wrap justify-center gap-8 md:gap-16 opacity-70 grayscale hover:grayscale-0 transition-all duration-500 mb-16">
<div class="flex flex-col items-center gap-2 group cursor-pointer hover:scale-105 transition-transform">
<span class="material-symbols-outlined text-4xl group-hover:text-blue-500 transition-colors text-white">code</span>
<span class="text-xs font-medium text-slate-300">Python</span>
</div>
<div class="flex flex-col items-center gap-2 group cursor-pointer hover:scale-105 transition-transform">
<span class="material-symbols-outlined text-4xl group-hover:text-green-500 transition-colors text-white">terminal</span>
<span class="text-xs font-medium text-slate-300">Selenium</span>
</div>
<div class="flex flex-col items-center gap-2 group cursor-pointer hover:scale-105 transition-transform">
<span class="material-symbols-outlined text-4xl group-hover:text-emerald-400 transition-colors text-white">database</span>
<span class="text-xs font-medium text-slate-300">Supabase</span>
</div>
<div class="flex flex-col items-center gap-2 group cursor-pointer hover:scale-105 transition-transform">
<span class="material-symbols-outlined text-4xl group-hover:text-red-500 transition-colors text-white">mail</span>
<span class="text-xs font-medium text-slate-300">Gmail API</span>
</div>
<div class="flex flex-col items-center gap-2 group cursor-pointer hover:scale-105 transition-transform">
<span class="material-symbols-outlined text-4xl group-hover:text-purple-500 transition-colors text-white">webhook</span>
<span class="text-xs font-medium text-slate-300">Flask</span>
</div>
</div>
<div class="flex flex-col md:flex-row justify-between items-center border-t border-white/10 pt-8">
<div class="text-sm text-slate-400 mb-4 md:mb-0">
                    Currently exclusive to <strong class="text-white">NIET</strong> College. © 2023 Attendance Bot.
                </div>
</div>
</div>
</footer>

<script>
    function togglePassword() {
        const input = document.getElementById('passwordInput');
        if (input.type === 'password') {
            input.type = 'text';
        } else {
            input.type = 'password';
        }
    }
</script>

</body></html>
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
                message = "Welcome Back! Your details are updated."
            else:
                supabase.table("users").insert(data).execute()
                message = "You're in! Expect an email tomorrow morning."
            
            status = "success"

        except Exception as e:
            message = f"Error: {str(e)}"
            status = "error"

    return render_template_string(HTML_PAGE, message=message, status=status)
