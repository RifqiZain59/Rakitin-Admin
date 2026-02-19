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


@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
       
        try:
            user = auth.get_user_by_email(email)
            
            user_data = get_user_profile(user.uid)
            
            if user_data:
                # Simpan sesi
                session['user'] = user.uid
                session['email'] = user.email
                session['name'] = user_data.get('name', 'Admin') # Default ke Admin jika nama kosong
                
                flash(f"Selamat datang kembali, {session['name']}!", "success")
                return redirect(url_for('dashboard'))
            else:
                flash("Data profil tidak ditemukan di database.", "error")
        except:
            flash("Email tidak terdaftar.", "error")
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('name')

        try:
            # 1. Buat User di Firebase Authentication
            user = auth.create_user(
                email=email,
                password=password,
                display_name=name
            )
            
            # 2. Simpan Data ke Firestore
            db.collection('users').document(user.uid).set({
                'name': name,
                'email': email,
                'created_at': firestore.SERVER_TIMESTAMP
            })
            
            flash("Akun berhasil dibuat! Silakan login.", "success")
            return redirect(url_for('login'))
            
        except Exception as e:
            flash(f"Pendaftaran gagal: {str(e)}", "error")
            
    return render_template('register.html')

# --- HALAMAN UTAMA (DIPERBAIKI) ---

@app.route('/dashboard')
def dashboard():
    # 1. Cek Login
    if 'user' not in session:
        return redirect(url_for('login'))
    
    # 2. Siapkan data user untuk template
    user_info = {
        'name': session.get('name'),
        'email': session.get('email')
    }
    
    # 3. Render dengan variable 'user' yang sudah didefinisikan
    return render_template('dashboard.html', user=user_info)

@app.route('/stok')
def stok_barang():
    if 'user' not in session:
        return redirect(url_for('login'))
        
    user_info = {
        'name': session.get('name'),
        'email': session.get('email')
    }
    return render_template('stok.html', user=user_info)

@app.route('/chat')
def chat():
    if 'user' not in session:
        return redirect(url_for('login'))
        
    user_info = {
        'name': session.get('name'),
        'email': session.get('email')
    }
    return render_template('chat.html', user=user_info)

@app.route('/logs')
def log_aktivitas():
    if 'user' not in session:
        return redirect(url_for('login'))
        
    user_info = {
        'name': session.get('name'),
        'email': session.get('email')
    }
    return render_template('logs.html', user=user_info)

@app.route('/logout')
def logout():
    session.clear()
    flash("Anda telah keluar.", "info")
    return redirect(url_for('login'))

@app.route('/laporan')
def laporan():
    if 'user' not in session:
        return redirect(url_for('login'))
        
    user_info = {
        'name': session.get('name'),
        'email': session.get('email')
    }
    
    return render_template('laporan.html', user=user_info)

if __name__ == '__main__':
    app.run(debug=True)