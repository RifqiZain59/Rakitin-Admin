import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
import firebase_admin
from firebase_admin import credentials, auth, firestore

# Inisialisasi Flask
app = Flask(__name__)
app.secret_key = 'rahasia_rakitin_2026' 

if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

def get_user_profile(uid):
    """Mengambil data profil user dari Firestore"""
    user_ref = db.collection('users').document(uid)
    doc = user_ref.get()
    if doc.exists:
        return doc.to_dict()
    return None

def get_current_user_info():
    """Helper untuk mengambil data user dari session"""
    return {
        'name': session.get('name'),
        'email': session.get('email'),
        'role': session.get('role') # Menambahkan Role ke info user
    }

@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        # Password tidak perlu diambil di sini untuk verifikasi manual 
        # karena kita menggunakan metode sederhana auth.get_user_by_email 
        # (Catatan: Idealnya verifikasi password dilakukan via Client SDK Firebase di frontend 
        # atau endpoint verifyPassword API, tapi untuk struktur ini kita ikuti alur yang ada).
        
        try:
            # Cek apakah user ada di Auth Firebase
            user = auth.get_user_by_email(email)
            
            # Ambil data profil tambahan dari Firestore (termasuk Role)
            user_data = get_user_profile(user.uid)
            
            if user_data:
                # Simpan sesi
                session['user'] = user.uid
                session['email'] = user.email
                session['name'] = user_data.get('name', 'User')
                session['role'] = user_data.get('role', 'user') # Simpan Role ke Session
                
                flash(f"Selamat datang kembali, {session['name']} ({session['role']})!", "success")
                return redirect(url_for('dashboard'))
            else:
                flash("Data profil tidak ditemukan di database.", "error")
        except:
            flash("Email tidak terdaftar atau terjadi kesalahan.", "error")
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('name')
        role = request.form.get('role') # Tangkap input Role dari form

        # Validasi sederhana
        if not role:
            flash("Silakan pilih kategori profesi Anda.", "error")
            return render_template('register.html')

        try:
            # 1. Buat User di Firebase Authentication
            user = auth.create_user(
                email=email,
                password=password,
                display_name=name
            )
            
            # 2. Simpan Data ke Firestore (Termasuk Role)
            db.collection('users').document(user.uid).set({
                'name': name,
                'email': email,
                'role': role, # Simpan role yang dipilih (tukang, kontraktor, dll)
                'created_at': firestore.SERVER_TIMESTAMP
            })
            
            flash("Akun berhasil dibuat! Silakan login.", "success")
            return redirect(url_for('login'))
            
        except Exception as e:
            flash(f"Pendaftaran gagal: {str(e)}", "error")
            
    return render_template('register.html')

# --- HALAMAN UTAMA ---

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    # Render dengan info user (termasuk role)
    return render_template('dashboard.html', user=get_current_user_info())

@app.route('/stok')
def stok_barang():
    if 'user' not in session:
        return redirect(url_for('login'))
        
    return render_template('stok.html', user=get_current_user_info())

@app.route('/chat')
def chat():
    if 'user' not in session:
        return redirect(url_for('login'))
        
    return render_template('chat.html', user=get_current_user_info())

@app.route('/logs')
def log_aktivitas():
    if 'user' not in session:
        return redirect(url_for('login'))
        
    return render_template('logs.html', user=get_current_user_info())

@app.route('/logout')
def logout():
    session.clear()
    flash("Anda telah keluar.", "info")
    return redirect(url_for('login'))

@app.route('/laporan')
def laporan():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    return render_template('laporan.html', user=get_current_user_info())

if __name__ == '__main__':
    app.run(debug=True)