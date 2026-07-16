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
        user_id = user_data.get("id")

        user_data.update({
            "sku_selesai": 0, "sku_total": 0, "persentase_sku": 0,
            "target_sku_judul": "Yuk, mulai isi SKU-mu!",
            "target_sku_deskripsi": "Pilih poin SKU yang ingin kamu selesaikan.",
            "activities": [], "rank": "-"
        })
        
        # Default parameter progress untuk mencegah error Jinja2
        user_data["sku_selesai"] = 0
        user_data["sku_total"] = 30
        user_data["persentase_sku"] = 0
        user_data["target_sku_judul"] = "Yuk, mulai isi SKU-mu!"
        user_data["target_sku_deskripsi"] = "Pilih poin SKU yang ingin kamu selesaikan."
        user_data["activities"] = []
        user_data["rank"] = "-"

        try:
            # A. Ambil Data Profil Terbaru dari database
            profile_res = api_request("GET", "/profile", headers=headers)
            if profile_res.status_code == 200:
                profile_json = profile_res.json()
                if profile_json.get("status") == "success":
                    user_data = profile_json.get("user", user_data)

            # B. Ambil Peringkat dari Leaderboard
            leaderboard_res = api_request("GET", "/leaderboard", headers=headers)
            if leaderboard_res.status_code == 200:
                lb_json = leaderboard_res.json()
                if lb_json.get("status") == "success":
                    for item in lb_json.get("data", []):
                        if item.get("id") == user_id:
                            user_data["rank"] = item.get("rank")
                            break

            # C. AMBIL PROGRESS SKU RIIL DARI BACKEND FASTAPI
            # Mengambil data progress user berdasarkan level yang sedang diikuti
            level_id = user_data.get("current_sku_level_id") or "11111111-1111-1111-1111-111111111111"
            try:
                # Ambil Master Soal untuk hitung TOTAL (Denominator)
                master_res = api_request("GET", f"/uji-sku/master/{level_id}", headers=headers)
                # Ambil Progress User untuk hitung SELESAI (Numerator)
                progress_res = api_request("GET", f"/uji-sku/progress/{user_id}/{level_id}", headers=headers)
                
                if master_res.status_code == 200 and progress_res.status_code == 200:
                    master_data = master_res.json().get("data", [])
                    progress_data = progress_res.json().get("data", [])
                    
                    total_soal = len(master_data)
                    # Hitung yang statusnya 'Selesai'
                    selesai = len([x for x in progress_data if x.get('status') == 'Selesai'])
                    
                    user_data["sku_selesai"] = selesai
                    user_data["sku_total"] = total_soal
                    user_data["persentase_sku"] = int((selesai / total_soal) * 100) if total_soal > 0 else 0
                    
                    # Cari target soal pertama yang belum selesai
                    for soal in master_data:
                        # Cek di progress apakah sudah selesai
                        prog_item = next((p for p in progress_data if p['uji_sku_id'] == soal['id']), None)
                        if not prog_item or prog_item.get('status') != 'Selesai':
                            user_data["target_sku_judul"] = f"Poin {soal.get('nomor_poin')}: {soal.get('kategori', 'Umum')}"
                            user_data["target_sku_deskripsi"] = soal.get("deskripsi", "Segera selesaikan poin ini.")
                            break

            except Exception as e:
                logger.error(f"Error progres SKU: {e}")

            # D. AMBIL RIWAYAT AKTIVITAS RIIL DARI LOGS BACKEND
            logs_res = api_request("GET", "/info-logs", headers=headers)
            if logs_res.status_code == 200:
                logs_json = logs_res.json()
                if logs_json.get("status") == "success":
                    mapped_activities = []
                    # Ambil maksimal 5 aktivitas terakhir agar dashboard rapi
                    for log in logs_json.get("data", [])[:5]:
                        activity_text = log.get("activity", "")
                        
                        # Parsing status warna timeline berdasarkan isi string aktivitas log
                        status_type = "info"
                        if "Lulus" in activity_text or "berhasil" in activity_text:
                            status_type = "lulus"
                        elif "Revisi" in activity_text or "gagal" in activity_text:
                            status_type = "revisi"

                        # Parsing waktu log buatan Supabase
                        waktu_raw = log.get("created_at", "Baru saja")
                        waktu_clean = waktu_raw.split("T")[0] if "T" in waktu_raw else waktu_raw

                        mapped_activities.append({
                            "judul": "Aktivitas Jurnal",
                            "deskripsi": activity_text,
                            "waktu": waktu_clean,
                            "status": status_type
                        })
                    user_data["activities"] = mapped_activities

            # Simpan data terbaru ke session
            session["user"] = user_data

        except Exception as e:
            logger.error(f"Error fetching dashboard data: {e}")

        return render_template("users/dashboard-user.html", page_title="Dashboard User", user=user_data)

# ==========================================================
# PEMBINA ROUTES
# ==========================================================
# Tambahkan ini di app.py bagian routing pembina
@app.route("/pembina")
def pembina():
    token = session.get("token")
    if session.get("role") != "pembina":
        return redirect(url_for("dashboard"))
    
    pembina_id = session.get("user", {}).get("id")
    headers = {"Authorization": f"Bearer {token}"}
    
    # Inisialisasi data
    data_dashboard = {"antrian_siswa": []}
    data_pembina = {
        "fullname": session.get("user", {}).get("fullname", "Pembina"),
        "sekolah": "-",
        "total_siswa": 0,
        "total_ujian": 0
    }
    
    # 1. Panggil fungsi statistik baru
    stats = get_pembina_dashboard_stats(pembina_id, token)
    data_pembina.update(stats)
    
    # 2. Ambil data sekolah
    try:
        res_pengajuan = api_request("GET", f"/pengajuan-pembina/user/{pembina_id}", headers=headers)
        if res_pengajuan.status_code == 200:
            pengajuan = res_pengajuan.json().get("data", {})
            data_pembina["sekolah"] = pengajuan.get("sekolah", "Pangkalan Tidak Ditemukan")
        
        # 3. Ambil Antrian Siswa
        res_siswa = api_request("GET", f"/uji-sku/pembina/antrian-siswa/{pembina_id}", headers=headers)
        if res_siswa.status_code == 200:
            data_dashboard["antrian_siswa"] = res_siswa.json().get("data", [])
            
    except Exception as e:
        logger.error(f"Error loading dashboard: {e}")
        
    return render_template("pembina/dashboard-penguji.html", 
                           data=data_dashboard, 
                           pembina=data_pembina, 
                           user=session.get("user"))


def get_pembina_dashboard_stats(pembina_id, token):
    """
    Fungsi untuk menghitung statistik pembina secara manual dari data mentah.
    Menghindari perubahan pada backend.
    """
    headers = {"Authorization": f"Bearer {token}"}
    stats = {"total_siswa": 0, "total_ujian": 0}
    
    try:
        # Mengambil semua pengajuan SKU yang pernah ditangani pembina ini
        res = api_request("GET", f"/sku/pembina/antrian/{pembina_id}", headers=headers)
        if res.status_code == 200:
            pengajuan_list = res.json().get("data", [])
            
            # 1. Hitung Siswa Binaan (Unik berdasarkan user_id)
            siswa_unik = {p['user_id'] for p in pengajuan_list}
            stats["total_siswa"] = len(siswa_unik)
            
            # 2. Hitung Ujian Selesai (Status 'approved' dari pengajuan_sku)
            # Berdasarkan file pengajuan_sku_rows.sql, statusnya adalah 'approved'
            total_selesai = len([p for p in pengajuan_list if p.get('status') == 'approved'])
            stats["total_ujian"] = total_selesai
            
    except Exception as e:
        logger.error(f"Gagal menghitung statistik pembina: {e}")
        
    return stats
                           


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
    token = session.get("token")
    if not token:
        return redirect(url_for("login"))
    
    user_data = session.get("user", {})
    user_id = user_data.get("id")
    level_id = user_data.get("current_sku_level_id") or "11111111-1111-1111-1111-111111111111"
    headers = {"Authorization": f"Bearer {token}"}
    
    # Data default
    all_sku_items = []
    
    try:
        # 1. Ambil Master Soal SKU dari API
        master_res = api_request("GET", f"/uji-sku/master/{level_id}", headers=headers)
        # 2. Ambil Progress User dari API
        progress_res = api_request("GET", f"/uji-sku/progress/{user_id}/{level_id}", headers=headers)
        
        if master_res.status_code == 200:
            master_data = master_res.json().get("data", [])
            
            # Buat map progress agar mudah dicari (status berdasarkan uji_sku_id)
            progress_list = progress_res.json().get("data", []) if progress_res.status_code == 200 else []
            progress_map = {p["uji_sku_id"]: p["status"] for p in progress_list}
            
            # Gabungkan master soal dengan status user
            for item in master_data:
                item["status_user"] = progress_map.get(item["id"], "Belum Diuji")
                all_sku_items.append(item)

        # Hitung statistik untuk bar progress
        total_soal = len(all_sku_items)
        selesai = len([x for x in all_sku_items if x["status_user"] == "Selesai"])
        persentase = int((selesai / total_soal) * 100) if total_soal > 0 else 0
        
        user_data["sku_selesai"] = selesai
        user_data["sku_total"] = total_soal
        user_data["persentase_sku"] = persentase

    except Exception as e:
        logger.error(f"Gagal mengambil progress SKU: {e}")

    return render_template("users/progres_sku.html", 
                           page_title="Progres SKU-ku", 
                           user=user_data, 
                           sku_list=all_sku_items)

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