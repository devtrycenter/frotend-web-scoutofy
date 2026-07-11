# ==========================================================
# IMPORTS
# ==========================================================
import os
import logging
from datetime import timedelta

import requests

from flask import (
    Flask,
    render_template,
    session,
    redirect,
    url_for,
    request,
    jsonify,
    flash
)

from config import get_config

# ==========================================================
# APP SETUP
# ==========================================================
app = Flask(__name__)
app.config.from_object(get_config())

# Peringatan keamanan jika Secret Key masih default di environment production
secret_key = os.getenv("SECRET_KEY", "change_this_secret_key")
if os.getenv("ENV") == "production" and secret_key == "change_this_secret_key":
    logging.warning("SECURITY WARNING: Menggunakan default SECRET_KEY di mode Production!")

app.config.setdefault("SECRET_KEY", secret_key)

# ==========================================================
# KEAMANAN UPLOAD (MAX 30 MB)
# ==========================================================
app.config["MAX_CONTENT_LENGTH"] = 30 * 1024 * 1024  # 30 Megabytes

# ==========================================================
# SESSION CONFIG
# ==========================================================
app.permanent_session_lifetime = timedelta(days=1)

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,       # Mencegah akses cookie via JavaScript (Mitigasi XSS)
    SESSION_COOKIE_SAMESITE="Lax",      # Melindungi dari serangan CSRF dasar
    SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "False").lower() == "true"
)

# ==========================================================
# API CONFIG
# ==========================================================
PRIMARY_API = os.getenv("API_BASE_URL", "https://haisen.my.id/api")

RAW_API_SERVERS = [
    PRIMARY_API,
    "https://haisen.my.id/api",
    "https://trycenter.my.id/api",
    "http://127.0.0.1:5000/api",
    # "http://192.168.56.116:5000/api"
]

# Hapus duplikat secara berurutan agar fallback berjalan efisien
API_SERVERS = list(dict.fromkeys(RAW_API_SERVERS))
REQUEST_TIMEOUT = int(os.getenv("API_TIMEOUT", 10))

# ==========================================================
# LOGGER
# ==========================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("frontend")

# ==========================================================
# API HELPER
# ==========================================================
def api_request(method, endpoint, **kwargs):
    """
    Otomatis mencoba beberapa backend API berdasarkan urutan API_SERVERS.
    """
    last_error = None

    for base_url in API_SERVERS:
        url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"

        try:
            response = requests.request(
                method=method,
                url=url,
                timeout=REQUEST_TIMEOUT,
                **kwargs
            )
            return response
        except requests.exceptions.RequestException as e:
            logger.warning(
                f"API gagal: {url} | {str(e)}"
            )
            last_error = e

    raise last_error

# ==========================================================
# TEMPLATE GLOBALS
# ==========================================================
@app.context_processor
def inject_globals():
    return {
        "APP_NAME": app.config.get("APP_NAME", "Scoutify"),
        "APP_VERSION": app.config.get("APP_VERSION", "1.0.0"),
        "SITE_TITLE": app.config.get("SITE_TITLE", "Jelajahi Rimba")
    }

# ==========================================================
# REQUEST LOGGER
# ==========================================================
@app.before_request
def log_request():
    logger.info(
        f"{request.method} {request.path}"
    )

# ==========================================================
# LANDING
# ==========================================================
@app.route("/")
def landing():
    return render_template("landing/index.html", page_title="Home")

@app.route("/about")
def about():
    return render_template("landing/about.html", page_title="Tentang Kami")

@app.route("/privacy")
def privacy():
    return render_template("landing/privacy.html", page_title="Privasi")

@app.route("/terms")
def terms():
    return render_template("landing/terms.html", page_title="Syarat & Ketentuan")

# ==========================================================
# AUTH
# ==========================================================
@app.route("/login", methods=["GET"])
def login():
    if session.get("token"):
        return redirect(url_for("dashboard"))
    return render_template("auth/login.html", page_title="Login")

@app.route("/login", methods=["POST"])
def login_post():
    email = request.form.get("email")
    password = request.form.get("password")

    try:
        response = api_request(
            "POST",
            "/login",
            json={"email": email, "password": password}
        )

        if response.status_code == 200:
            data = response.json()
            session.permanent = True
            
            session["token"] = data.get("token")
            
            user_data = data.get("user", {})
            session["user"] = user_data
            
            # Ambil role dari backend, default ke 'user' jika tidak ada
            session["role"] = user_data.get("role", "user")

            flash("Login berhasil", "success")
            return redirect(url_for("dashboard"))

        flash("Email atau password salah", "error")

    except Exception as e:
        logger.error(f"Login Error: {str(e)}")
        flash("Backend tidak dapat dihubungi", "error")

    return redirect(url_for("login"))

@app.route("/register")
def register():
    return render_template("auth/register.html", page_title="Register")

@app.route("/forgot-password")
def forgot_password():
    return render_template("auth/forgot_password.html", page_title="Lupa Password")

@app.route("/logout")
def logout():
    session.clear()
    flash("Berhasil logout", "success")
    return redirect(url_for("landing"))

@app.route("/google-login")
def google_login():
    flash("Login dengan Google sedang dalam pengembangan.", "info")
    return redirect(url_for("login"))

# ==========================================================
# DASHBOARDS (ROLE-BASED ROUTING)
# ==========================================================
@app.route("/dashboard")
def dashboard():
    """
    Central router: Mengarahkan user sesuai dengan role masing-masing.
    """
    token = session.get("token")
    if not token:
        return redirect(url_for("login"))

    role = session.get("role", "user")
    
    # 1. Routing Admin
    if role == "admin":
        return redirect(url_for("admin"))
    
    # 2. Routing Pembina
    elif role == "pembina":
        return redirect(url_for("pembina"))
    
    # 3. Routing User Biasa
    else:
        user_data = session.get("user", {})
        headers = {"Authorization": f"Bearer {token}"}
        
        try:
            profile_res = api_request("GET", "/profile", headers=headers)
            if profile_res.status_code == 200:
                profile_json = profile_res.json()
                if profile_json.get("status") == "success":
                    user_data = profile_json.get("user", user_data)
                    session["user"] = user_data
            
            leaderboard_res = api_request("GET", "/leaderboard", headers=headers)
            user_data["rank"] = "-"
            if leaderboard_res.status_code == 200:
                lb_json = leaderboard_res.json()
                if lb_json.get("status") == "success":
                    for item in lb_json.get("data", []):
                        if item.get("id") == user_data.get("id"):
                            user_data["rank"] = item.get("rank")
                            break

        except Exception as e:
            logger.error(f"Error fetching dashboard data: {e}")

        return render_template("users/dashboard-user.html", page_title="Dashboard User", user=user_data)

# ==========================================================
# PEMBINA ROUTES
# ==========================================================
@app.route("/pembina")
def pembina():
    """
    Dashboard khusus untuk Pembina.
    """
    if session.get("role") != "pembina":
        flash("Akses ditolak. Halaman ini hanya untuk Pembina.", "error")
        return redirect(url_for("dashboard"))
        
    return render_template("pembina/dashboard-penguji.html", page_title="Dashboard Pembina", user=session.get("user"))

# ==========================================================
# ADMIN ROUTES
# ==========================================================
@app.route("/admin")
def admin():
    """
    Dashboard khusus untuk Admin.
    """
    if session.get("role") != "admin":
        flash("Akses ditolak. Halaman ini hanya untuk Admin.", "error")
        return redirect(url_for("dashboard"))
        
    return render_template("admin/dashboard-admin.html", page_title="Admin Dashboard", user=session.get("user"))

# ==========================================================
# USER SUB-ROUTES
# ==========================================================
@app.route("/progres-sku")
def progres_sku():
    if not session.get("token"):
        return redirect(url_for("login"))
    return render_template("users/progres_sku.html", page_title="Progres SKU-ku", user=session.get("user"))

@app.route("/materi")
def materi():
    if not session.get("token"):
        return redirect(url_for("login"))
    return render_template("users/materi.html", page_title="Materi & Belajar", user=session.get("user"))

@app.route("/ai-semaphore")
def ai_semaphore():
    if not session.get("token"):
        return redirect(url_for("login"))
    return render_template("users/ai_semaphore.html", page_title="AI Semaphore", user=session.get("user"))

@app.route("/leaderboard")
def leaderboard():
    if not session.get("token"):
        return redirect(url_for("login"))
    return render_template("users/leaderboard.html", page_title="Leaderboard", user=session.get("user"))

@app.route("/uji-sku")
def uji_sku():
    if not session.get("token"):
        return redirect(url_for("login"))
    return render_template("users/form_uji_sku.html", page_title="Ajukan Ujian SKU", user=session.get("user"))

@app.route("/profile")
def profile():
    if not session.get("token"):
        return redirect(url_for("login"))
    return render_template("users/profile.html", page_title="Profile", user=session.get("user"))

# ==========================================================
# API PROXY UNTUK FRONTEND (FETCH DARI JAVASCRIPT)
# ==========================================================
@app.route('/api/<path:endpoint>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def proxy_api(endpoint):
    """
    Menangkap semua fetch('/api/...') dari JavaScript di browser 
    dan meneruskannya ke Backend FastAPI menggunakan sistem auto-fallback.
    """
    try:
        # Ambil data JSON yang dikirim dari Javascript
        json_data = request.get_json(silent=True)
        
        # Kirim ke backend menggunakan helper yang sudah ada
        response = api_request(request.method, f"/{endpoint}", json=json_data)
        
        # Kembalikan hasilnya ke Javascript di browser
        try:
            return jsonify(response.json()), response.status_code
        except ValueError:
            return response.text, response.status_code

    except Exception as e:
        logger.error(f"API Proxy Error pada endpoint /{endpoint}: {str(e)}")
        return jsonify({
            "status": "error", 
            "message": "Backend tidak dapat dihubungi, coba lagi nanti."
        }), 500

# ==========================================================
# HEALTH CHECK
# ==========================================================
@app.route("/status")
def status():
    backend_status = []
    for server in API_SERVERS:
        try:
            response = requests.get(f"{server}/status", timeout=5)
            backend_status.append({"server": server, "online": response.status_code == 200})
        except:
            backend_status.append({"server": server, "online": False})

    return jsonify({
        "status": "success",
        "service": "Scoutify Frontend",
        "version": app.config.get("APP_VERSION", "1.0.0"),
        "backends": backend_status
    })

# ==========================================================
# ERROR HANDLER
# ==========================================================
@app.errorhandler(404)
def not_found(error):
    return render_template("errors/404.html"), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template("errors/500.html"), 500

@app.errorhandler(413)
def request_entity_too_large(error):
    # Dijalankan saat file melebihi MAX_CONTENT_LENGTH (30 MB)
    flash("Ukuran file terlalu besar! Maksimal upload adalah 30MB.", "error")
    # Redirect kembali ke halaman sebelumnya atau ke dashboard
    return redirect(request.referrer or url_for('dashboard'))

# ==========================================================
# SECURITY HEADERS
# ==========================================================
@app.after_request
def security_headers(response):
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    
    # HSTS: Mencegah serangan Man-in-the-Middle dengan memaksa HTTPS (Hanya aktif di production)
    if os.getenv("ENV") == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    
    # Content-Security-Policy Dasar
    response.headers["Content-Security-Policy"] = "default-src 'self' https: data: 'unsafe-inline' 'unsafe-eval';"
    
    return response

# ==========================================================
# MAIN
# ==========================================================
if __name__ == "__main__":
    env = os.getenv("ENV", "development")
    debug_mode = app.config.get("DEBUG", env != "production")
    
    # Menentukan port Frontend menjadi 5001 sesuai permintaan
    port = int(os.getenv("PORT", 5001))

    print("=" * 60)
    print("SCOUTIFY FRONTEND")
    print("=" * 60)
    print(f"ENV      : {env}")
    print(f"APP URL  : {os.getenv('APP_URL', f'http://localhost:{port}')}")
    print("API LIST :")
    for idx, api in enumerate(API_SERVERS, 1):
        print(f"  {idx}. {api}")
    print("HOST     : 0.0.0.0")
    print(f"PORT     : {port}")
    print(f"MAX FILE : 30 MB")
    print("=" * 60)

    app.run(host="0.0.0.0", port=port, debug=debug_mode)