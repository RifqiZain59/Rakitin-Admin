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
        return 'toko bangunan'
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

    # === LOGIKA KHUSUS TOKO BANGUNAN ===
    if folder == 'toko bangunan':
        stat_total_item = 0
        stat_stok_tersedia = 0
        stat_pesanan_baru = 0
        stat_siap_dikirim = 0
        pesanan_terbaru = []
        
        try:
            # 1. Hitung total jenis item dan jumlah stoknya dari Firestore
            stok_docs = db.collection('stokbarang_toko').stream()
            for doc in stok_docs:
                stat_total_item += 1  # Hitung macam/jenis item
                data = doc.to_dict()
                
                # Hitung TOTAL KUANTITAS (Sum dari seluruh angka 'stok' di database)
                stat_stok_tersedia += data.get('stok', 0)
                
                # CATATAN: Jika Anda ingin angkanya adalah "Jumlah Jenis Barang yang Ready"
                # (misalnya 15 merk barang tersedia), ganti baris atas dengan:
                # if data.get('stok', 0) > 0:
                #    stat_stok_tersedia += 1
            
            # 2. Ambil data list pesanan (akan otomatis 0 bila form pemesanan belum dibuat)
            try:
                pesanan_docs = db.collection('pesanan_toko').order_by('created_at', direction=firestore.Query.DESCENDING).limit(5).stream()
                for doc in pesanan_docs:
                    p_data = doc.to_dict()
                    p_data['id'] = doc.id
                    pesanan_terbaru.append(p_data)
                    
                    status = p_data.get('status', '')
                    if status == 'Menunggu Proses':
                        stat_pesanan_baru += 1
                    elif status == 'Siap Dikirim' or status == 'Sedang Disiapkan':
                        stat_siap_dikirim += 1
            except Exception as e:
                print(f"Collection pesanan belum ada atau error: {e}")
                
        except Exception as e:
            print(f"Error fetching dashboard data: {e}")

        # Kirimkan data ke template HTML
        return render_template(f'{folder}/dashboard.html', 
                               user=user,
                               stat_total_item=stat_total_item,
                               stat_stok_tersedia=stat_stok_tersedia,
                               stat_pesanan_baru=stat_pesanan_baru,
                               stat_siap_dikirim=stat_siap_dikirim,
                               pesanan_terbaru=pesanan_terbaru)
    
    # Render untuk peran/role lain selain Toko Bangunan
    return render_template(f'{folder}/dashboard.html', user=user)

@app.route('/api/tambah_desain', methods=['POST'])
def tambah_desain():
    user = get_current_user_info()
    if not user: 
        return redirect(url_for('login'))
    
    try:
        # Pindahkan import ke dalam fungsi agar pasti terbaca
        import base64 
        import random
        
        nama_proyek = request.form.get('nama_proyek')
        nama_klien = request.form.get('nama_klien')
        kategori = request.form.get('kategori')
        gaya_desain = request.form.get('gaya_desain')
        
        file_gambar = request.files.get('file_gambar')
        file_base64 = ""
        ukuran_str = "0 MB"
        format_file = ".JPG"

        if file_gambar and file_gambar.filename != '':
            # 1. Dapatkan Ekstensi
            filename = file_gambar.filename
            format_file = "." + filename.rsplit('.', 1)[1].upper() if '.' in filename else '.JPG'
            
            # 2. Baca isi file byte
            file_data = file_gambar.read()
            
            # 3. Hitung Ukuran File (Berapa MB)
            size_mb = len(file_data) / (1024 * 1024)
            ukuran_str = f"{size_mb:.2f} MB"
            
            # CEK UKURAN FILE LIMIT FIREBASE (Maks ~800 KB agar aman jadi Base64)
            if len(file_data) > 800000:
                flash("Gagal Upload: Ukuran file terlalu besar! Maksimal gambar adalah 800 KB.", "error")
                return redirect(url_for('desain'))
            
            # 4. Konversi ke Base64 (Data URI)
            encoded_string = base64.b64encode(file_data).decode('utf-8')
            mime_type = file_gambar.mimetype
            file_base64 = f"data:{mime_type};base64,{encoded_string}"

        # Format ID Berkas random
        id_berkas = f"DES-{random.randint(1000, 9999)}-X"

        # Kunci 'status' dan 'jumlah_revisi' telah dihapus dari database
        data_desain = {
            'id_berkas': id_berkas,
            'nama_proyek': nama_proyek,
            'nama_klien': nama_klien,
            'kategori': kategori,
            'gaya_desain': gaya_desain,
            'format': format_file,
            'ukuran': ukuran_str,
            'file_base64': file_base64,
            'nama_arsitek': user['name'],
            'created_by_uid': user['uid'],
            'created_at': firestore.SERVER_TIMESTAMP
        }

        # Simpan ke Firestore
        db.collection('berkas_desain').add(data_desain)
        
        # NOTE: Baris flash() pesan sukses telah DIHAPUS dari sini

    except Exception as e:
        print(f"Error saat menyimpan desain ke Firestore: {e}")
        # Pesan error tetap dipertahankan agar Anda tahu jika server bermasalah
        flash(f"Terjadi kesalahan server saat upload: {str(e)}", "error")
        
    return redirect(url_for('desain'))

@app.route('/api/edit_desain', methods=['POST'])
def edit_desain():
    user = get_current_user_info()
    if not user: 
        return redirect(url_for('login'))
    
    try:
        import base64
        
        # Menangkap data teks dari form Modal Edit
        item_id = request.form.get('id')
        nama_proyek = request.form.get('nama_proyek')
        nama_klien = request.form.get('nama_klien')
        kategori = request.form.get('kategori')
        gaya_desain = request.form.get('gaya_desain')

        # Data dasar yang akan di-update
        data_update = {
            'nama_proyek': nama_proyek,
            'nama_klien': nama_klien,
            'kategori': kategori,
            'gaya_desain': gaya_desain
        }
        
        # CEK APAKAH ADA FILE BARU YANG DIUPLOAD PADA SAAT EDIT
        file_gambar = request.files.get('file_gambar')
        if file_gambar and file_gambar.filename != '':
            # 1. Dapatkan Ekstensi
            filename = file_gambar.filename
            format_file = "." + filename.rsplit('.', 1)[1].upper() if '.' in filename else '.JPG'
            
            # 2. Baca isi file
            file_data = file_gambar.read()
            size_mb = len(file_data) / (1024 * 1024)
            ukuran_str = f"{size_mb:.2f} MB"
            
            # Cek batas ukuran Firebase (Maks 800 KB)
            if len(file_data) > 800000:
                flash("Gagal Edit: Ukuran file baru terlalu besar! Maksimal 800 KB.", "error")
                return redirect(url_for('desain'))
            
            # 3. Konversi ke Base64
            encoded_string = base64.b64encode(file_data).decode('utf-8')
            mime_type = file_gambar.mimetype
            file_base64 = f"data:{mime_type};base64,{encoded_string}"
            
            # 4. Tambahkan data file baru ini ke dictionary data_update
            data_update['format'] = format_file
            data_update['ukuran'] = ukuran_str
            data_update['file_base64'] = file_base64

        # Proses update dokumen di database berdasarkan item_id
        db.collection('berkas_desain').document(item_id).update(data_update)

    except Exception as e:
        print(f"Error saat mengedit desain: {e}")
        flash(f"Terjadi kesalahan server saat edit: {str(e)}", "error")
        
    return redirect(url_for('desain'))

@app.route('/stok')
def stok_barang():
    user = get_current_user_info()
    if not user: return redirect(url_for('login'))
        
    folder = get_role_folder(user['role'])
    
    # Menarik data dari Firestore
    daftar_barang = []
    try:
        docs = db.collection('stokbarang_toko').order_by('created_at', direction=firestore.Query.DESCENDING).stream()
        for doc in docs:
            item = doc.to_dict()
            item['id'] = doc.id
            daftar_barang.append(item)
    except Exception as e:
        print(f"Error fetching data: {e}")
        
    return render_template(f'{folder}/stok.html', user=user, daftar_barang=daftar_barang)

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

@app.route('/desain')
def desain():
    user = get_current_user_info()
    if not user: return redirect(url_for('login'))
    
    folder = get_role_folder(user['role'])
    
    daftar_desain = []
    if folder == 'arsitektur':
        try:
            # Mengambil data dari koleksi 'berkas_desain'
            docs = db.collection('berkas_desain').order_by('created_at', direction=firestore.Query.DESCENDING).stream()
            for doc in docs:
                item = doc.to_dict()
                item['id'] = doc.id
                daftar_desain.append(item)
        except Exception as e:
            print(f"Error fetching desain: {e}")
            
        return render_template(f'{folder}/desain.html', user=user, daftar_desain=daftar_desain)

    return render_template(f'{folder}/desain.html', user=user)

@app.route('/logrevisi')
def logrevisi():
    user = get_current_user_info()
    if not user: return redirect(url_for('login'))
    
    folder = get_role_folder(user['role'])
    return render_template(f'{folder}/logrevisi.html', user=user)

@app.route('/alat')
def alat():
    user = get_current_user_info()
    if not user: return redirect(url_for('login'))
    
    folder = get_role_folder(user['role'])
    
    # 1. Siapkan list kosong untuk menampung data
    daftar_alat = []
    
    # 2. Tarik data khusus jika user adalah tukang
    if folder == 'tukang':
        try:
            # Mengambil data dari koleksi 'alat_tukang' dan mengurutkan dari yang terbaru
            docs = db.collection('alat_tukang').order_by('created_at', direction=firestore.Query.DESCENDING).stream()
            for doc in docs:
                item = doc.to_dict()
                item['id'] = doc.id # Menyimpan ID dokumen Firestore
                daftar_alat.append(item)
        except Exception as e:
            # Jika terjadi error (misalnya index firebase belum dibuat), data akan ditarik tanpa diurutkan
            print(f"Peringatan: Gagal mengurutkan data (Mungkin butuh Index Firestore). Menarik data tanpa urutan... Error: {e}")
            try:
                docs = db.collection('alat_tukang').stream()
                for doc in docs:
                    item = doc.to_dict()
                    item['id'] = doc.id
                    daftar_alat.append(item)
            except Exception as ex:
                print(f"Error fatal fetching alat: {ex}")
            
    # 3. Kirimkan variabel 'daftar_alat' ke file alat.html
    return render_template(f'{folder}/alat.html', user=user, daftar_alat=daftar_alat)

@app.route('/api/edit_alat', methods=['POST'])
def edit_alat():
    user = get_current_user_info()
    if not user: 
        return redirect(url_for('login'))
    
    try:
        # Menangkap data dari form Modal Edit
        item_id = request.form.get('id')
        nama_alat = request.form.get('nama_alat')
        merk = request.form.get('merk', '-')
        kategori = request.form.get('kategori')
        ketersediaan = request.form.get('ketersediaan')
        kondisi = request.form.get('kondisi')

        # Data yang akan di-update ke Firestore
        data_update = {
            'nama_alat': nama_alat,
            'merk': merk,
            'kategori': kategori,
            'ketersediaan': int(ketersediaan) if ketersediaan else 0,
            'kondisi': kondisi
        }
        
        # Proses update dokumen di database berdasarkan ID
        db.collection('alat_tukang').document(item_id).update(data_update)

    except Exception as e:
        print(f"Error saat mengedit alat: {e}")
        
    return redirect(url_for('alat'))

@app.route('/logpekerjaan')
def logpekerjaan():
    user = get_current_user_info()
    if not user: return redirect(url_for('login'))
    
    folder = get_role_folder(user['role'])
    return render_template(f'{folder}/logpekerjaan.html', user=user)

@app.route('/manajemenproyek')
def manajemenproyek():
    user = get_current_user_info()
    if not user: return redirect(url_for('login'))
    
    folder = get_role_folder(user['role'])
    return render_template(f'{folder}/manajemenproyek.html', user=user)

@app.route('/profil')
def profil():
    user = get_current_user_info()
    if not user: return redirect(url_for('login'))
    flash("Halaman profil sedang dalam pengembangan.", "info")
    return redirect(url_for('dashboard'))

# ==========================================
# API ROUTES (CRUD FIREBASE)
# ==========================================

# 1. TAMBAH STOK
@app.route('/api/tambah_stok', methods=['POST'])
def tambah_stok():
    user = get_current_user_info()
    if not user: 
        return redirect(url_for('login'))
    
    try:
        nama_barang = request.form.get('nama_barang')
        sku = request.form.get('sku')
        kategori = request.form.get('kategori')
        stok = request.form.get('stok')
        satuan = request.form.get('satuan')

        stok_int = int(stok) if stok else 0

        data_barang = {
            'nama_barang': nama_barang,
            'sku': sku,
            'kategori': kategori,
            'stok': stok_int,
            'satuan': satuan,
            'created_by_uid': user['uid'], 
            'created_by_name': user['name'],
            'created_at': firestore.SERVER_TIMESTAMP
        }

        db.collection('stokbarang_toko').add(data_barang)
        # Baris flash() pesan sukses DIHAPUS agar tidak muncul notifikasi tersimpan
    except Exception as e:
        print(f"Error saat menyimpan barang ke Firestore: {e}")
        # Pesan error tetap dipertahankan untuk berjaga-jaga jika gagal simpan
        flash("Gagal menambahkan barang. Terjadi kesalahan pada server.", "error")
        
    return redirect(url_for('stok_barang'))

# 2. EDIT STOK
@app.route('/api/edit_stok', methods=['POST'])
def edit_stok():
    user = get_current_user_info()
    if not user: 
        return redirect(url_for('login'))
    
    try:
        item_id = request.form.get('id')
        nama_barang = request.form.get('nama_barang')
        
        stok_int = request.form.get('stok')
        stok_int = int(stok_int) if stok_int else 0

        data_update = {
            'nama_barang': nama_barang,
            'sku': request.form.get('sku'),
            'kategori': request.form.get('kategori'),
            'stok': stok_int,
            'satuan': request.form.get('satuan')
        }

        db.collection('stokbarang_toko').document(item_id).update(data_update)
        # Baris flash() pesan sukses DIHAPUS agar tidak muncul notifikasi edit sukses

    except Exception as e:
        print(f"Error saat edit barang di Firestore: {e}")
        # Pesan error tetap dipertahankan
        flash("Gagal memperbarui barang. Terjadi kesalahan server.", "error")
        
    return redirect(url_for('stok_barang'))

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

@app.route('/api/update_status_desain', methods=['POST'])
def update_status_desain():
    if 'user' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    try:
        item_id = request.form.get('id')
        status_baru = request.form.get('status')
        
        # Update status di Firestore
        db.collection('berkas_desain').document(item_id).update({
            'status': status_baru
        })
        
        return jsonify({'success': True, 'message': 'Status berhasil diubah'})
    except Exception as e:
        print(f"Error update status: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    
@app.route('/api/tambah_alat', methods=['POST'])
def tambah_alat():
    user = get_current_user_info()
    if not user: 
        return redirect(url_for('login'))
    
    try:
        nama_alat = request.form.get('nama_alat')
        merk = request.form.get('merk', '-')
        kategori = request.form.get('kategori')
        ketersediaan = request.form.get('ketersediaan')
        kondisi = request.form.get('kondisi')
        
        # Generate Kode Alat otomatis
        import random
        kode_alat = f"ALT-{random.randint(100, 999)}"

        data_alat = {
            'kode': kode_alat,
            'nama_alat': nama_alat,
            'merk': merk,
            'kategori': kategori,
            'ketersediaan': int(ketersediaan) if ketersediaan else 0,
            'kondisi': kondisi,
            'created_by': user['name'],
            'created_by_uid': user['uid'],
            'created_at': firestore.SERVER_TIMESTAMP
        }

        # Simpan ke Firestore
        db.collection('alat_tukang').add(data_alat)

    except Exception as e:
        print(f"Error saat menyimpan alat ke Firestore: {e}")
        
    return redirect(url_for('alat'))

if __name__ == '__main__':
    app.run(debug=True)