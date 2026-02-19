import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import firebase_admin
from firebase_admin import credentials, auth, firestore

# Inisialisasi Flask
app = Flask(__name__)
app.secret_key = 'rahasia_rakitin_2026' 

# --- KONFIGURASI FIREBASE ---
try:
    if not firebase_admin._apps:
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
except Exception as e:
    print(f"Error initializing Firebase: {e}")

db = firestore.client()

# --- HELPER FUNCTIONS ---
def get_user_profile(uid):
    try:
        user_ref = db.collection('users').document(uid)
        doc = user_ref.get()
        if doc.exists:
            return doc.to_dict()
    except Exception as e:
        print(f"Error getting user profile: {e}")
    return None

def get_current_user_info():
    if 'user' not in session:
        return None
    return {
        'uid': session.get('user'),
        'name': session.get('name'),
        'email': session.get('email'),
        'role': session.get('role', 'arsitektur') 
    }

def get_role_folder(role):
    if not role:
        return 'arsitektur'
    
    role_bersih = role.lower().strip()
    if role_bersih in ['toko bangunan', 'toko_bangunan']:
        return 'toko_bangunan'
    elif role_bersih == 'arsitekur': # Jika terjadi typo di database
        return 'arsitektur'
        
    return role_bersih.replace(' ', '_')

# ==========================================
# ROUTES: AUTHENTICATION
# ==========================================
@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        try:
            user = auth.get_user_by_email(email)
            user_data = get_user_profile(user.uid)
            
            if user_data:
                session['user'] = user.uid
                session['email'] = user.email
                session['name'] = user_data.get('name', 'User')
                session['role'] = user_data.get('role', 'arsitektur')
                
                flash(f"Selamat datang kembali, {session['name']}!", "success")
                return redirect(url_for('dashboard'))
            else:
                flash("Data profil tidak ditemukan di database.", "error")
        except firebase_admin._auth_utils.UserNotFoundError:
            flash("Email tidak terdaftar.", "error")
        except Exception as e:
            flash(f"Terjadi kesalahan saat login: {str(e)}", "error")
            
    return render_template('login.html', user=None)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('name')
        role = request.form.get('role')

        if not role:
            flash("Silakan pilih kategori profesi Anda.", "error")
            return render_template('register.html', user=None)

        try:
            user = auth.create_user(email=email, password=password, display_name=name)
            db.collection('users').document(user.uid).set({
                'name': name,
                'email': email,
                'role': role,
                'created_at': firestore.SERVER_TIMESTAMP
            })
            flash("Akun berhasil dibuat! Silakan login.", "success")
            return redirect(url_for('login'))
        except Exception as e:
            flash(f"Pendaftaran gagal: {str(e)}", "error")
            
    return render_template('register.html', user=None)

@app.route('/logout')
def logout():
    session.clear()
    flash("Anda telah keluar dari sistem.", "info")
    return redirect(url_for('login'))

# ==========================================
# ROUTES: HALAMAN UTAMA (DYNAMIC ROUTING)
# ==========================================
@app.route('/dashboard')
def dashboard():
    user = get_current_user_info()
    if not user: return redirect(url_for('login'))
    
    folder = get_role_folder(user['role'])
    return render_template(f'{folder}/dashboard.html', user=user)

@app.route('/stok')
def stok_barang():
    user = get_current_user_info()
    if not user: return redirect(url_for('login'))
        
    folder = get_role_folder(user['role'])
    return render_template(f'{folder}/stok.html', user=user)

@app.route('/chat')
def chat():
    user = get_current_user_info()
    if not user: return redirect(url_for('login'))
        
    folder = get_role_folder(user['role'])
    return render_template(f'{folder}/chat.html', user=user)

@app.route('/logs')
def log_aktivitas():
    user = get_current_user_info()
    if not user: return redirect(url_for('login'))
        
    folder = get_role_folder(user['role'])
    return render_template(f'{folder}/logs.html', user=user)

@app.route('/laporan')
def laporan():
    user = get_current_user_info()
    if not user: return redirect(url_for('login'))
    
    folder = get_role_folder(user['role'])
    return render_template(f'{folder}/laporan.html', user=user)

# --- RUTE BARU YANG DITAMBAHKAN ---

@app.route('/desain')
def desain():
    user = get_current_user_info()
    if not user: return redirect(url_for('login'))
    
    folder = get_role_folder(user['role'])
    return render_template(f'{folder}/desain.html', user=user)

@app.route('/logrevisi')
def logrevisi():
    user = get_current_user_info()
    if not user: return redirect(url_for('login'))
    
    folder = get_role_folder(user['role'])
    return render_template(f'{folder}/logrevisi.html', user=user)

# ==========================================
# ROUTES: AKSI & FUNGSI TAMBAHAN
# ==========================================
@app.route('/profil')
def profil():
    user = get_current_user_info()
    if not user: return redirect(url_for('login'))
    flash("Halaman profil sedang dalam pengembangan.", "info")
    return redirect(url_for('dashboard'))

@app.route('/api/tambah_stok', methods=['POST'])
def tambah_stok():
    user = get_current_user_info()
    if not user: return redirect(url_for('login'))
    nama_barang = request.form.get('nama_barang')
    flash(f"{nama_barang} berhasil ditambahkan ke sistem!", "success")
    return redirect(url_for('stok_barang'))

@app.route('/api/update_status', methods=['POST'])
def update_status():
    user = get_current_user_info()
    if not user: 
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    
    data = request.get_json()
    item_id = data.get('id')
    status_baru = data.get('status')
    
    return jsonify({
        "status": "success", 
        "message": f"Status item {item_id} berhasil diubah menjadi {status_baru}"
    })

# ==========================================
# ERROR HANDLER 
# ==========================================
@app.errorhandler(404)
def page_not_found(e):
    user = get_current_user_info()
    if user:
        flash("Halaman yang Anda tuju tidak ditemukan.", "error")
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.errorhandler(500)
def internal_server_error(e):
    flash("Terjadi kesalahan pada server. Silakan coba lagi.", "error")
    user = get_current_user_info()
    if user:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)