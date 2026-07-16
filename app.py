import os
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

from flask import Flask, request, jsonify, send_from_directory
from flask_pymongo import PyMongo
from flask_cors import CORS
from flask_mail import Mail, Message
import random
from datetime import datetime, timedelta
from recognition.recognizer import recognize
from ai.arcface_service import generate_embedding

from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    jwt_required,
    get_jwt_identity,
    get_jwt
)

from bson import ObjectId
from werkzeug.utils import secure_filename

import bcrypt
import os
import shutil
import numpy as np

# =========================
# INIT APP
# =========================

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ================= EMAIL CONFIG =================

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True

app.config['MAIL_USERNAME'] = 'safekossecurity@gmail.com'
app.config['MAIL_PASSWORD'] = 'psmu lvvi jjih nqjr'

mail = Mail(app)

# =========================
# ENABLE CORS
# =========================

CORS(app)

# =========================
# MONGODB CONFIG
# =========================

app.config["MONGO_URI"] = "mongodb+srv://safekos_db:safekos12@cluster0.sykcsjm.mongodb.net/safekos_db"

mongo = PyMongo(app)

# =========================
# JWT CONFIG
# =========================

app.config["JWT_SECRET_KEY"] = "safekos_secret_key"

jwt = JWTManager(app)

# =========================
# TEST ROUTE
# =========================

@app.route('/')
def home():

    return {
        "message": "SAFEKOS API RUNNING",
        "database": "MongoDB Connected"
    }

# =========================
# TEST DATABASE ROUTE
# =========================

@app.route('/test-db')
def test_db():

    collections = mongo.db.list_collection_names()

    return {
        "success": True,
        "database": mongo.db.name,
        "collections": collections
    }

# =========================
# SERVE UPLOADS
# =========================
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# =========================
# REGISTER
# =========================

@app.route('/api/auth/register', methods=['POST'])
def register():

    try:

        data = request.get_json()

        nama = data.get('nama')
        email = data.get('email')
        password = data.get('password')

        nama_kos = data.get('nama_kos')
        lokasi_kos = data.get('lokasi_kos')
        hp = data.get('hp')

        # =========================
        # VALIDASI
        # =========================

        if not nama or not email or not password or not hp:

            return jsonify({
                "success": False,
                "message": "Data wajib diisi"
            }), 400

        # =========================
        # CHECK EMAIL
        # =========================

        existing_user = mongo.db.users.find_one({
            "email": email
        })

        if existing_user:

            return jsonify({
                "success": False,
                "message": "Email sudah digunakan"
            }), 400

        # =========================
        # HASH PASSWORD
        # =========================

        hashed_password = bcrypt.hashpw(
            password.encode('utf-8'),
            bcrypt.gensalt()
        )

        # =========================
        # CREATE KOS
        # =========================

        kos_data = {
            "nama_kos": nama_kos,
            "lokasi_kos": lokasi_kos
        }

        kos_result = mongo.db.kos.insert_one(
            kos_data
        )

        kos_id = str(kos_result.inserted_id)

        # =========================
        # CREATE USER
        # =========================

        user_data = {
            "nama": nama,
            "email": email,
            "password": hashed_password,

            "hp": hp,

            "role": "pemilik",

            "kos_id": kos_id
        }

        user_result = mongo.db.users.insert_one(
            user_data
        )

        # =========================
        # UPDATE OWNER_ID DI KOS
        # =========================

        mongo.db.kos.update_one(
            {
                "_id": ObjectId(kos_id)
            },
            {
                "$set": {
                    "owner_id": str(user_result.inserted_id)
                }
            }
        )

        return jsonify({
            "success": True,
            "message": "Register berhasil",
            "kos_id": kos_id
        }), 201

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

# =========================
# LOGIN
# =========================

@app.route('/api/auth/login', methods=['POST'])
def login():

    try:

        data = request.get_json()

        email = data.get('email')
        password = data.get('password')
        role = data.get('role')

        # =========================
        # VALIDASI
        # =========================

        if not email or not password:

            return jsonify({
                "success": False,
                "message": "Email dan password wajib diisi"
            }), 400

        # =========================
        # CHECK USER
        # =========================

        user = mongo.db.users.find_one({
            "email": email
        })

        if not user:

            mongo.db.app_logs.insert_one({

                "kos_id": "-",

                "user_id": "-",

                "nama": email,

                "role": "-",

                "aksi": "Login gagal - User tidak ditemukan",

                "waktu": datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            })


            return jsonify({
                "success": False,
                "message": "User tidak ditemukan"
            }), 404

        # =========================
        # CHECK PASSWORD
        # =========================

        password_match = bcrypt.checkpw(
            password.encode('utf-8'),
            user['password']
        )

        if not password_match:


            mongo.db.app_logs.insert_one({

                "kos_id": user["kos_id"],

                "user_id": str(user["_id"]),

                "nama": user["nama"],

                "role": user["role"],

                "aksi": "Login gagal - Password salah",

                "waktu": datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            })


            return jsonify({
                "success": False,
                "message": "Password salah"
            }), 401

        # =========================
        # CHECK ROLE
        # =========================

        if user['role'] != role:


            mongo.db.app_logs.insert_one({

                "kos_id": user["kos_id"],

                "user_id": str(user["_id"]),

                "nama": user["nama"],

                "role": user["role"],

                "aksi": "Login gagal - Role tidak sesuai",

                "waktu": datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            })


            return jsonify({
                "success": False,
                "message": "Role tidak sesuai"
            }), 401

        # =========================
        # CREATE JWT TOKEN
        # =========================

        token = create_access_token(

            identity=str(user['_id']),

            additional_claims={

                "kos_id": user['kos_id'],
                "role": user['role'],
                "nama": user['nama']
            }
        )

        mongo.db.app_logs.insert_one({

            "kos_id": user["kos_id"],

            "user_id": str(user["_id"]),

            "nama": user["nama"],

            "role": user["role"],

            "aksi": "Login berhasil",

            "waktu": datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        })

        return jsonify({
            "success": True,
            "message": "Login berhasil",
            "token": token,
            "user": {
                "nama": user['nama'],
                "email": user['email'],
                "role": user['role']
            }
        }), 200

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500
    
# =========================
# LOGIN OTP
# =========================

@app.route('/api/auth/login-otp', methods=['POST'])
def login_otp():

    try:

        data = request.get_json()

        email = data.get('email')
        password = data.get('password')
        role = data.get('role')

        user = mongo.db.users.find_one({
            "email": email
        })

        if not user:
            return jsonify({
                "success": False,
                "message": "User tidak ditemukan"
            }), 404

        password_match = bcrypt.checkpw(
            password.encode('utf-8'),
            user['password']
        )

        if not password_match:
            return jsonify({
                "success": False,
                "message": "Password salah"
            }), 401

        if user['role'] != role:
            return jsonify({
                "success": False,
                "message": "Role tidak sesuai"
            }), 401

        otp = str(random.randint(100000, 999999))
        expired = datetime.utcnow() + timedelta(minutes=5)

        mongo.db.users.update_one(
            {"email": email},
            {
                "$set": {
                    "loginOtp": otp,
                    "loginOtpExpired": expired
                }
            }
        )

        msg = Message(
            'OTP Login SafeKos',
            sender=app.config['MAIL_USERNAME'],
            recipients=[email]
        )

        msg.body = f'''
Kode OTP Login Anda:

{otp}

Kode berlaku selama 5 menit.
'''

        mail.send(msg)

        return jsonify({
            "success": True,
            "message": "OTP login berhasil dikirim",
            "email": email
        }), 200

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500
    
# =========================
# VERIFY LOGIN OTP
# =========================

@app.route('/api/auth/verify-login-otp', methods=['POST'])
def verify_login_otp():

    try:

        data = request.get_json()

        email = data.get('email')
        otp = data.get('otp')

        user = mongo.db.users.find_one({
            "email": email
        })

        if not user:

            return jsonify({
                "success": False,
                "message": "User tidak ditemukan"
            }), 404

        if user.get("loginOtp") != otp:

            return jsonify({
                "success": False,
                "message": "OTP salah"
            }), 400

        if datetime.utcnow() > user.get("loginOtpExpired"):

            return jsonify({
                "success": False,
                "message": "OTP expired"
            }), 400

        token = create_access_token(
            identity=str(user['_id']),
            additional_claims={
                "kos_id": user['kos_id'],
                "role": user['role'],
                "nama": user['nama']
            }
        )

        mongo.db.users.update_one(
            {"email": email},
            {
                "$unset": {
                    "loginOtp": "",
                    "loginOtpExpired": ""
                }
            }
        )

        return jsonify({
            "success": True,
            "message": "Login berhasil",
            "token": token,
            "user": {
                "nama": user['nama'],
                "email": user['email'],
                "role": user['role']
            }
        }), 200

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500
    
# =========================
# RESEND LOGIN OTP
# =========================

@app.route('/api/auth/resend-login-otp', methods=['POST'])
def resend_login_otp():

    try:

        data = request.get_json()

        email = data.get('email')

        user = mongo.db.users.find_one({
            "email": email
        })

        if not user:
            return jsonify({
                "success": False,
                "message": "User tidak ditemukan"
            }), 404

        otp = str(random.randint(100000, 999999))
        expired = datetime.utcnow() + timedelta(minutes=5)

        mongo.db.users.update_one(
            {"email": email},
            {
                "$set": {
                    "loginOtp": otp,
                    "loginOtpExpired": expired
                }
            }
        )

        msg = Message(
            'OTP Login SafeKos',
            sender=app.config['MAIL_USERNAME'],
            recipients=[email]
        )

        msg.body = f'''
Kode OTP Login Anda:

{otp}

Kode berlaku selama 5 menit.
'''

        mail.send(msg)

        return jsonify({
            "success": True,
            "message": "OTP berhasil dikirim ulang"
        }), 200

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route('/forgot-password', methods=['POST'])
def forgot_password():

    try:

        data = request.json

        email = data.get('email')

        # ================= CEK USER =================

        user = mongo.db.users.find_one({
            "email": email
        })

        if not user:

            return jsonify({
                "message": "Email tidak ditemukan"
            }), 404

        # ================= GENERATE OTP =================

        otp = str(random.randint(100000, 999999))

        expired = datetime.utcnow() + timedelta(minutes=5)

        # ================= SIMPAN OTP =================

        mongo.db.users.update_one(

            {"email": email},

            {
                "$set": {
                    "otp": otp,
                    "otpExpired": expired
                }
            }
        )

        # ================= KIRIM EMAIL =================

        msg = Message(

            'OTP Reset Password SafeKos',

            sender=app.config['MAIL_USERNAME'],

            recipients=[email]
        )

        msg.body = f'''
Kode OTP Reset Password Anda:

{otp}

Kode berlaku selama 5 menit.
        '''
        print("EMAIL:", email)
        print("OTP:", otp)
        print("MULAI KIRIM EMAIL")

        mail.send(msg)
        print("EMAIL BERHASIL TERKIRIM")

        return jsonify({
            "message": "Kode OTP berhasil dikirim"
        }), 200

    except Exception as e:

        print(e)

        return jsonify({
            "message": "Server Error"
        }), 500


# =========================
# VERIFY OTP
# =========================

@app.route('/verify-otp', methods=['POST'])
def verify_otp():

    try:

        data = request.json

        email = data.get('email')
        otp = data.get('otp')

        # =========================
        # VALIDASI
        # =========================

        if not email or not otp:

            return jsonify({
                "success": False,
                "message": "Email dan OTP wajib diisi"
            }), 400

        # =========================
        # CEK USER
        # =========================

        user = mongo.db.users.find_one({
            "email": email
        })

        if not user:

            return jsonify({
                "success": False,
                "message": "User tidak ditemukan"
            }), 404

        # =========================
        # CEK OTP
        # =========================

        saved_otp = user.get('otp')
        otp_expired = user.get('otpExpired')

        if saved_otp != otp:

            return jsonify({
                "success": False,
                "message": "OTP salah"
            }), 400

        # =========================
        # CEK EXPIRED
        # =========================

        if datetime.utcnow() > otp_expired:

            return jsonify({
                "success": False,
                "message": "OTP sudah expired"
            }), 400

        # =========================
        # SUCCESS
        # =========================

        return jsonify({
            "success": True,
            "message": "OTP valid"
        }), 200

    except Exception as e:

        print(e)

        return jsonify({
            "success": False,
            "message": "Server Error"
        }), 500


# =========================
# RESET PASSWORD
# =========================

@app.route('/reset-password', methods=['POST'])
def reset_password():

    try:

        data = request.json

        email = data.get('email')
        new_password = data.get('new_password')

        # =========================
        # VALIDASI
        # =========================

        if not email or not new_password:

            return jsonify({
                "success": False,
                "message": "Data tidak lengkap"
            }), 400

        # =========================
        # CEK USER
        # =========================

        user = mongo.db.users.find_one({
            "email": email
        })

        if not user:

            return jsonify({
                "success": False,
                "message": "User tidak ditemukan"
            }), 404

        # =========================
        # HASH PASSWORD BARU
        # =========================

        hashed_password = bcrypt.hashpw(
            new_password.encode('utf-8'),
            bcrypt.gensalt()
        )

        # =========================
        # UPDATE PASSWORD
        # =========================

        mongo.db.users.update_one(

            {
                "email": email
            },

            {
                "$set": {
                    "password": hashed_password
                },

                "$unset": {
                    "otp": "",
                    "otpExpired": ""
                }
            }
        )

        return jsonify({
            "success": True,
            "message": "Password berhasil direset"
        }), 200

    except Exception as e:

        print(e)

        return jsonify({
            "success": False,
            "message": "Server Error"
        }), 500

# =========================
# REGISTER PENGHUNI
# =========================

@app.route('/api/penghuni/register', methods=['POST'])
@jwt_required()
def create_penghuni():

    try:

        # =========================
        # JWT
        # =========================

        current_user = get_jwt_identity()

        claims = get_jwt()

        kos_id = claims['kos_id']

        role = claims['role']

        # =========================
        # VALIDASI ROLE
        # =========================

        if role != "pemilik":

            return jsonify({

                "success": False,
                "message": "Hanya pemilik yang boleh mendaftarkan penghuni"

            }), 403

        # =========================
        # FORM DATA
        # =========================

        nama = request.form.get('nama')

        email = request.form.get('email')

        password = request.form.get('password')

        kamar = request.form.get('kamar')

        hp = request.form.get('hp')

        # =========================
        # FOTO
        # =========================

        files = request.files.getlist('foto_wajah')

        print("TOTAL FOTO:", len(files))

        # =========================
        # VALIDASI FIELD
        # =========================

        if not nama or not email or not password or not kamar or not hp:

            return jsonify({

                "success": False,
                "message": "Semua field wajib diisi"

            }), 400

        # =========================
        # VALIDASI FOTO
        # =========================

        if len(files) != 3:

            return jsonify({

                "success": False,
                "message": "Foto wajah harus 3"

            }), 400

        # =========================
        # CHECK EMAIL
        # =========================

        existing_user = mongo.db.users.find_one({

            "email": email

        })

        if existing_user:

            return jsonify({

                "success": False,
                "message": "Email sudah digunakan"

            }), 400

        # =========================
        # HASH PASSWORD
        # =========================

        hashed_password = bcrypt.hashpw(

            password.encode('utf-8'),

            bcrypt.gensalt()

        )

        # =========================
        # SIMPAN FOTO
        # =========================

        foto_paths = []

        for file in files:

            filename = secure_filename(file.filename)

            filepath = os.path.join(

                app.config['UPLOAD_FOLDER'],

                filename

            )

            file.save(filepath)

            foto_paths.append(filepath)

        embeddings = []

        for path in foto_paths:

            embedding = generate_embedding(path)

            if embedding is not None:
                embeddings.append(embedding)

        if len(embeddings) == 0:

            return jsonify({

                "success": False,
                "message": "Tidak ada wajah yang terdeteksi"

            }), 400
            
        final_embedding = np.mean(
            embeddings,
            axis=0
        ).tolist()

        # =========================
        # INSERT USERS
        # =========================

        user_data = {

            "nama": nama,

            "email": email,

            "password": hashed_password,

            "role": "penghuni",

            "kos_id": kos_id
        }

        user_result = mongo.db.users.insert_one(
            user_data
        )

        # =========================
        # INSERT PENGHUNI
        # =========================

        penghuni = {

            "user_id": str(user_result.inserted_id),

            "nama": nama,

            "kamar": kamar,

            "hp": hp,

            "foto_wajah": foto_paths,

            "face_embedding": final_embedding,

            "kos_id": kos_id,

            "created_by": current_user
        }

        mongo.db.penghuni.insert_one(
            penghuni
        )

        mongo.db.app_logs.insert_one({

            "kos_id": kos_id,

            "user_id": current_user,

            "nama": claims["nama"],

            "role": role,

            "aksi": f"Menambahkan penghuni {nama}",

            "waktu": datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        })

        # =========================
        # RESPONSE
        # =========================

        return jsonify({

            "success": True,

            "message": "Penghuni berhasil didaftarkan"

        }), 201

    except Exception as e:

        return jsonify({

            "success": False,

            "message": str(e)

        }), 500

# =========================
# PROFILE
# =========================

@app.route('/api/profile', methods=['GET'])
@jwt_required()
def profile():

    try:

        user_id = get_jwt_identity()

        claims = get_jwt()

        kos_id = claims['kos_id']

        user = mongo.db.users.find_one({
            "_id": ObjectId(user_id)
        })

        if not user:

            return jsonify({
                "success": False,
                "message": "User tidak ditemukan"
            }), 404

        kos = mongo.db.kos.find_one({
            "_id": ObjectId(kos_id)
        })

        # =========================
        # DATA DASAR
        # =========================

        data = {

            "nama": user['nama'],
            "email": user['email'],
            "hp": user.get('hp', ''),
            "role": user['role'],

            "kos": {
                "id": str(kos['_id']),
                "nama_kos": kos['nama_kos'],
                "lokasi_kos": kos['lokasi_kos']
            }
        }

        # =========================
        # JIKA PENGHUNI
        # =========================

        if user['role'] == "penghuni":

            penghuni = mongo.db.penghuni.find_one({
                "user_id": str(user['_id'])
            })

            if penghuni:

                data["kamar"] = penghuni.get("kamar", "")

        return jsonify({
            "success": True,
            "data": data
        }), 200

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

 # =========================
# UPDATE PROFILE
# =========================

@app.route('/api/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    try:
        user_id = get_jwt_identity()
        claims = get_jwt()
        kos_id = claims['kos_id']
        data = request.json

        update_user_data = {}
        if "nama" in data: update_user_data["nama"] = data["nama"]
        if "email" in data: update_user_data["email"] = data["email"]
        if "hp" in data: update_user_data["hp"] = data["hp"]

        if update_user_data:
            mongo.db.users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": update_user_data}
            )

        if "lokasi_kos" in data:
            mongo.db.kos.update_one(
                {"_id": ObjectId(kos_id)},
                {"$set": {"lokasi_kos": data["lokasi_kos"]}}
            )

        return jsonify({
            "success": True,
            "message": "Profil berhasil diperbarui"
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

 # =========================
# GET DATA PENGHUNI
# =========================

@app.route('/api/penghuni', methods=['GET'])
@jwt_required()
def get_penghuni():

    try:

        claims = get_jwt()

        kos_id = claims['kos_id']

        role = claims['role']

        # =========================
        # HANYA PEMILIK
        # =========================

        if role != "pemilik":

            return jsonify({
                "success": False,
                "message": "Akses ditolak"
            }), 403

        # =========================
        # AMBIL DATA PENGHUNI
        # =========================

        penghuni_list = mongo.db.penghuni.find({
            "kos_id": kos_id
        })

        results = []

        for penghuni in penghuni_list:

            results.append({

                "id": str(penghuni["_id"]),

                "nama": penghuni.get("nama", ""),

                "kamar": penghuni.get("kamar", ""),

                "hp": penghuni.get("hp", ""),

                "foto": penghuni.get("foto_wajah", [])
            })

        return jsonify({
            "success": True,
            "data": results
        }), 200

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

# =========================
# EDIT PENGHUNI
# =========================

@app.route('/api/penghuni/<id>', methods=['PUT'])
@jwt_required()
def edit_penghuni(id):

    try:

        # =========================
        # AMBIL DATA FORM
        # =========================

        nama = request.form.get('nama')
        kamar = request.form.get('kamar')
        hp = request.form.get('hp')

        print("NAMA:", nama)
        print("KAMAR:", kamar)
        print("HP:", hp)

        # =========================
        # VALIDASI
        # =========================

        if not nama or not kamar or not hp:

            return jsonify({
                "success": False,
                "message": "Data tidak lengkap"
            }), 400

        # =========================
        # CEK PENGHUNI
        # =========================

        penghuni = mongo.db.penghuni.find_one({
            "_id": ObjectId(id)
        })

        if not penghuni:

            return jsonify({
                "success": False,
                "message": "Penghuni tidak ditemukan"
            }), 404
        
        claims = get_jwt()

        user_id = get_jwt_identity()

        # =========================
        # UPDATE DATA
        # =========================

        mongo.db.penghuni.update_one(

            {
                "_id": ObjectId(id)
            },

            {
                "$set": {
                    "nama": nama,
                    "kamar": kamar,
                    "hp": hp
                }
            }
        )

        mongo.db.app_logs.insert_one({

            "kos_id": claims["kos_id"],

            "user_id": user_id,

            "nama": claims["nama"],

            "role": claims["role"],

            "aksi": f"Mengubah data penghuni {penghuni['nama']}",

            "waktu": datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        })

        return jsonify({
            "success": True,
            "message": "Penghuni berhasil diupdate"
        }), 200

    except Exception as e:

        print(e)

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500
    
# =========================
# DELETE PENGHUNI
# =========================

@app.route('/api/penghuni/<id>', methods=['DELETE'])
@jwt_required()
def delete_penghuni(id):

    try:

        penghuni = mongo.db.penghuni.find_one({
            "_id": ObjectId(id)
        })

        if not penghuni:

            return jsonify({
                "success": False,
                "message": "Penghuni tidak ditemukan"
            }), 404
        
        claims = get_jwt()

        user_id = get_jwt_identity()

        # =========================
        # HAPUS USER
        # =========================

        mongo.db.users.delete_one({
            "_id": ObjectId(penghuni['user_id'])
        })

        mongo.db.app_logs.insert_one({

            "kos_id": claims["kos_id"],

            "user_id": user_id,

            "nama": claims["nama"],

            "role": claims["role"],

            "aksi": f"Menghapus penghuni {penghuni['nama']}",

            "waktu": datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        })

        # =========================
        # HAPUS PENGHUNI
        # =========================

        mongo.db.penghuni.delete_one({
            "_id": ObjectId(id)
        })

        return jsonify({
            "success": True,
            "message": "Penghuni berhasil dihapus"
        }), 200

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

# =========================
# TAMBAH KAMERA
# =========================

@app.route('/api/kamera', methods=['POST'])
@jwt_required()
def tambah_kamera():

    try:

        claims = get_jwt()

        kos_id = claims['kos_id']

        current_user = get_jwt_identity()

        data = request.get_json()

        nama_kamera = data.get("nama_kamera")
        ip_kamera = data.get("ip_kamera")

        if not nama_kamera or not ip_kamera:
            return jsonify({
                "success": False,
                "message": "Data tidak lengkap"
            }), 400

        preview_url = f"http://{ip_kamera}/shot.jpg"
        stream_url = f"http://{ip_kamera}/video"

        kamera = {

            "nama_kamera": nama_kamera,

            "preview_url": preview_url,

            "stream_url": stream_url,

            "status": True,

            "zone": [],

            "kos_id": kos_id,

            "created_by": current_user
        }

        result = mongo.db.kamera.insert_one(kamera)

        mongo.db.app_logs.insert_one({

            "kos_id": kos_id,

            "user_id": current_user,

            "nama": claims["nama"],

            "role": claims["role"],

            "aksi": f"Menambahkan kamera {nama_kamera}",

            "waktu": datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        })

        return jsonify({

            "success": True,

            "message": "Kamera berhasil ditambahkan",

            "id": str(result.inserted_id)

        }), 201

    except Exception as e:

        return jsonify({

            "success": False,

            "message": str(e)

        }), 500

@app.route('/api/kamera', methods=['GET'])
@jwt_required()
def get_kamera():

    try:

        claims = get_jwt()
        kos_id = claims['kos_id']

        kamera_list = list(
            mongo.db.kamera.find(
                {"kos_id": kos_id}
            )
        )

        for kamera in kamera_list:
            kamera['_id'] = str(kamera['_id'])

        print("===== DATA KAMERA =====")

        for kamera in kamera_list:
            print(kamera)

        return jsonify({
            "success": True,
            "data": kamera_list
        }), 200

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500
    
@app.route('/api/kamera/<id>/status', methods=['PUT'])
@jwt_required()
def update_status_kamera(id):

    try:

        data = request.get_json()

        status = data.get('status')

        claims = get_jwt()

        current_user = get_jwt_identity()


        kamera = mongo.db.kamera.find_one({
            "_id": ObjectId(id)
        })

        mongo.db.kamera.update_one(
            {"_id": ObjectId(id)},
            {
                "$set": {
                    "status": status
                }
            }
        )

        mongo.db.app_logs.insert_one({

            "kos_id": claims["kos_id"],

            "user_id": current_user,

            "nama": claims["nama"],

            "role": claims["role"],

            "aksi": (
                f"{'Mengaktifkan' if status else 'Menonaktifkan'} "
                f"kamera {kamera['nama_kamera']}"
            ),

            "waktu": datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        })

        return jsonify({
            "success": True,
            "message": "Status kamera berhasil diperbarui"
        }), 200

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route('/api/kamera/<kamera_id>/zona', methods=['PUT'])
@jwt_required()
def update_zona(kamera_id):

    try:

        data = request.get_json()

        zone = data.get("zone", [])

        # ambil data user dari token
        claims = get_jwt()

        user_id = get_jwt_identity()


        # ambil data kamera
        kamera = mongo.db.kamera.find_one({
            "_id": ObjectId(kamera_id)
        })

        result = mongo.db.kamera.update_one(
            {
                "_id": ObjectId(kamera_id)
            },
            {
                "$set": {
                    "zone": zone
                }
            }
        )

        # simpan log aplikasi
        mongo.db.app_logs.insert_one({

            "kos_id": claims["kos_id"],

            "user_id": user_id,

            "nama": claims["nama"],

            "role": claims["role"],

            "aksi": f"Mengubah zona keamanan kamera {kamera['nama_kamera']}",

            "waktu": datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        })

        return jsonify({
            "success": True,
            "message": "Zona berhasil disimpan"
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

# =========================
# EDIT KAMERA
# =========================

@app.route('/api/kamera/<id>', methods=['PUT'])
@jwt_required()
def edit_kamera(id):
    try:
        data = request.get_json()
        nama_kamera = data.get('nama_kamera')
        stream_url = data.get('stream_url')
        
        claims = get_jwt()
        user_id = get_jwt_identity()
        
        kamera = mongo.db.kamera.find_one({"_id": ObjectId(id)})
        if not kamera:
            return jsonify({"success": False, "message": "Kamera tidak ditemukan"}), 404
            
        mongo.db.kamera.update_one(
            {"_id": ObjectId(id)},
            {"$set": {
                "nama_kamera": nama_kamera,
                "stream_url": stream_url
            }}
        )
        
        mongo.db.app_logs.insert_one({
            "kos_id": claims["kos_id"],
            "user_id": user_id,
            "nama": claims["nama"],
            "role": claims["role"],
            "aksi": f"Mengubah data kamera {kamera['nama_kamera']} menjadi {nama_kamera}",
            "waktu": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        return jsonify({"success": True, "message": "Kamera berhasil diupdate"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# =========================
# DELETE KAMERA
# =========================

@app.route('/api/kamera/<id>', methods=['DELETE'])
@jwt_required()
def delete_kamera(id):
    try:
        claims = get_jwt()
        user_id = get_jwt_identity()
        
        kamera = mongo.db.kamera.find_one({"_id": ObjectId(id)})
        if not kamera:
            return jsonify({"success": False, "message": "Kamera tidak ditemukan"}), 404
            
        mongo.db.kamera.delete_one({"_id": ObjectId(id)})
        
        mongo.db.app_logs.insert_one({
            "kos_id": claims["kos_id"],
            "user_id": user_id,
            "nama": claims["nama"],
            "role": claims["role"],
            "aksi": f"Menghapus kamera {kamera['nama_kamera']}",
            "waktu": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        return jsonify({"success": True, "message": "Kamera berhasil dihapus"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# =========================
# LOG APP
# =========================

@app.route('/api/logs', methods=['POST'])
@jwt_required()
def tambah_log():

    try:

        data = request.get_json()

        user_id = get_jwt_identity()

        claims = get_jwt()

        log = {

            "kos_id": claims["kos_id"],

            "user_id": user_id,

            "nama": claims["nama"],

            "role": claims["role"],

            "aksi": data.get("aksi"),

            "waktu": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        mongo.db.app_logs.insert_one(log)

        return jsonify({
            "success": True,
            "message": "Log berhasil ditambahkan"
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500
    

@app.route('/api/auth/logout', methods=['POST'])
@jwt_required()
def logout():

    try:

        claims = get_jwt()


        mongo.db.app_logs.insert_one({

            "kos_id": claims["kos_id"],

            "user_id": get_jwt_identity(),

            "nama": claims["nama"],

            "role": claims["role"],

            "aksi": "Logout",

            "waktu": datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        })


        return jsonify({

            "success": True,

            "message": "Logout berhasil"

        }),200



    except Exception as e:

        return jsonify({

            "success":False,

            "message":str(e)

        }),500
    
# =========================
# LOG ACTIVITY
# =========================
    
@app.route('/api/logs', methods=['GET'])
@jwt_required()
def get_logs():

    try:

        claims = get_jwt()

        kos_id = claims["kos_id"]

        role = claims["role"]


        # =========================
        # CEK ROLE
        # =========================

        if role != "pemilik":

            return jsonify({

                "success": False,

                "message": "Hanya pemilik yang dapat melihat log aplikasi"

            }),403



        logs = list(
            mongo.db.app_logs.find(
                {
                    "kos_id": kos_id
                }
            ).sort(
                "waktu",
                -1
            )
        )


        for log in logs:

            log["_id"] = str(log["_id"])



        return jsonify({

            "success": True,

            "data": logs

        }),200



    except Exception as e:

        return jsonify({

            "success": False,

            "message": str(e)

        }),500

# =========================
# KOS SETTINGS
# =========================

@app.route("/api/settings/<kos_id>", methods=["GET"])
def get_settings(kos_id):
    setting = mongo.db.settings.find_one({"kos_id": kos_id}, {"_id": 0})
    if not setting:
        setting = {
            "kos_id": kos_id,
            "alert_stranger": True,
            "alert_unverified": True,
            "durasi_trigger": "30s"
        }
    return jsonify({
        "success": True,
        "data": setting
    })

@app.route("/api/settings/<kos_id>", methods=["POST"])
def update_settings(kos_id):
    data = request.json
    setting = {
        "kos_id": kos_id,
        "alert_stranger": data.get("alert_stranger", True),
        "alert_unverified": data.get("alert_unverified", True),
        "durasi_trigger": data.get("durasi_trigger", "30s")
    }
    mongo.db.settings.update_one(
        {"kos_id": kos_id},
        {"$set": setting},
        upsert=True
    )
    return jsonify({
        "success": True,
        "message": "Pengaturan berhasil disimpan",
        "data": setting
    })


# =====================================
# GET ACTIVITY LOG
# =====================================

@app.route("/api/activity", methods=["GET"])
@jwt_required()
def get_activity():

    claims = get_jwt()

    kos_id = claims["kos_id"]

    data = list(

        mongo.db.activity_logs.find(

            {
                "kos_id": kos_id
            },

            {
                "_id": 0
            }

        ).sort("created_at", -1)

    )

    return jsonify({

        "success": True,

        "data": data

    })

@app.route("/api/activity", methods=["POST"])
def receive_activity():

    data = request.json

    print("\n=== ACTIVITY DITERIMA ===")
    print(data)
    
    image_url = None
    if "image" in data and data["image"]:
        import base64
        import uuid
        try:
            image_data = base64.b64decode(data["image"])
            filename = f"stranger_{uuid.uuid4().hex}.jpg"
            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                os.makedirs(app.config['UPLOAD_FOLDER'])
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            with open(filepath, "wb") as f:
                f.write(image_data)
            image_url = f"/uploads/{filename}"
        except Exception as e:
            print("Error saving image:", e)

    activity = {

        "track_id": data.get("track_id"),

        "kos_id": data.get("kos_id"),

        "nama": data.get("nama"),

        "kamar" : data.get("kamar"),

        "status": data.get("status"),

        "direction": data.get("direction"),

        "similarity": data.get("similarity"),

        "time": data.get("time"),
        
        "image_url": image_url,

        "created_at": datetime.utcnow()

    }

    mongo.db.activity_logs.insert_one(activity)

    # =========================
    # BUAT NOTIFICATION
    # =========================
    
    kos_id = data.get("kos_id")
    setting = mongo.db.settings.find_one({"kos_id": kos_id})
    if not setting:
        setting = {
            "alert_stranger": True,
            "alert_unverified": True
        }

    status = data.get("status")
    
    buat_notif = True
    if status == "stranger" and not setting.get("alert_stranger", True):
        buat_notif = False
    if status == "unverified" and not setting.get("alert_unverified", True):
        buat_notif = False

    if buat_notif and status != "penghuni":
        if status == "stranger":
            # INTERSEPSI: Cek apakah ada tamu yang menunggu di jam yang sama
            current_time = datetime.utcnow() + timedelta(hours=7) # Local WIB time
            current_hour = current_time.hour
            
            pending_tamus = list(mongo.db.tamu.find({
                "kos_id": kos_id,
                "status": "menunggu"
            }))

            valid_tamu = None
            for t in pending_tamus:
                try:
                    t_jam = t.get("jam", "")
                    if ":" in t_jam:
                        tamu_hour = int(t_jam.split(":")[0])
                        # Cek persis di jam yang sama (tanpa toleransi)
                        if current_hour == tamu_hour:
                            valid_tamu = t
                            break
                except Exception:
                    pass

            if valid_tamu:
                # Buat notifikasi KHUSUS untuk penghuni
                notification_penghuni = {
                    "kos_id": kos_id,
                    "penghuni_id": valid_tamu["penghuni_id"],
                    "tamu_id": str(valid_tamu["_id"]),
                    "title": "Konfirmasi Tamu",
                    "message": "Ada orang terdeteksi. Apakah ini tamu Anda?",
                    "type": "guest_confirmation",
                    "is_read": False,
                    "image_url": image_url,
                    "created_at": datetime.utcnow()
                }
                mongo.db.notifications.insert_one(notification_penghuni)
                return jsonify({"success": True, "message": "Activity disimpan, konfirmasi tamu dikirim ke penghuni"})
            else:
                title = "Orang Tidak Dikenal"
                message = "Orang tidak dikenal terdeteksi"
        else:
            title = "Aktivitas"
            message = "Aktivitas baru terdeteksi"

        notification = {
            "kos_id": kos_id,
            "title": title,
            "message": message,
            "type": status,
            "is_read": False,
            "image_url": image_url,
            "created_at": datetime.utcnow()
        }
        mongo.db.notifications.insert_one(notification)

    return jsonify({
        "success": True,
        "message": "Activity disimpan"
    })

# =====================================
# TAMU REPORTING
# =====================================

@app.route("/api/tamu", methods=["POST"])
@jwt_required()
def add_tamu():
    claims = get_jwt()
    if claims.get("role") != "penghuni":
        return jsonify({"success": False, "message": "Akses ditolak"}), 403
        
    data = request.get_json()
    tamu = {
        "kos_id": claims["kos_id"],
        "penghuni_id": get_jwt_identity(),
        "nama": data.get("nama"),
        "jam": data.get("jam"),
        "status": "menunggu",
        "created_at": datetime.utcnow()
    }
    mongo.db.tamu.insert_one(tamu)
    
    # Notify owner
    notification = {
        "kos_id": claims["kos_id"],
        "title": "Tamu Didaftarkan",
        "message": f"Penghuni mendaftarkan tamu baru bernama {data.get('nama')} untuk jam {data.get('jam')}",
        "type": "tamu_baru",
        "is_read": False,
        "image_url": "",
        "created_at": datetime.utcnow()
    }
    mongo.db.notifications.insert_one(notification)
    
    return jsonify({"success": True, "message": "Tamu berhasil didaftarkan"})

@app.route("/api/tamu", methods=["GET"])
@jwt_required()
def get_tamu():
    claims = get_jwt()
    if claims.get("role") != "penghuni":
        return jsonify({"success": False, "message": "Akses ditolak"}), 403
        
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    data = list(mongo.db.tamu.find({
        "penghuni_id": get_jwt_identity(),
        "created_at": {"$gte": today}
    }).sort("created_at", -1))
    for item in data:
        item["_id"] = str(item["_id"])
        
    return jsonify({"success": True, "data": data})

@app.route("/api/tamu/confirm", methods=["POST"])
@jwt_required()
def confirm_tamu():
    claims = get_jwt()
    data = request.get_json()
    tamu_id = data.get("tamu_id")
    action = data.get("action")
    notif_id = data.get("notif_id")
    
    # Hapus notifikasi konfirmasi
    if notif_id:
        mongo.db.notifications.delete_one({"_id": ObjectId(notif_id)})
        
    tamu = mongo.db.tamu.find_one({"_id": ObjectId(tamu_id)})
    if not tamu:
        return jsonify({"success": False, "message": "Tamu tidak ditemukan"}), 404
        
    if action == "yes":
        mongo.db.tamu.update_one({"_id": ObjectId(tamu_id)}, {"$set": {"status": "selesai"}})
        
        # Insert log aktivitas tamu masuk
        mongo.db.activity_logs.insert_one({
            "kos_id": tamu["kos_id"],
            "track_id": 0,
            "direction": "masuk",
            "status": "tamu",
            "nama": tamu["nama"],
            "kamar": claims.get("kamar", "-"),
            "similarity": 0,
            "time": datetime.now().isoformat()
        })
        return jsonify({"success": True, "message": "Tamu dikonfirmasi"})
        
    elif action == "no":
        mongo.db.tamu.update_one({"_id": ObjectId(tamu_id)}, {"$set": {"status": "ditolak"}})
        # Eskalasi ke pemilik (sebagai stranger)
        notification = {
            "kos_id": tamu["kos_id"],
            "title": "Orang Tidak Dikenal",
            "message": "Orang tidak dikenal terdeteksi (Tamu ditolak)",
            "type": "stranger",
            "is_read": False,
            "image_url": data.get("image_url", ""),
            "created_at": datetime.utcnow()
        }
        mongo.db.notifications.insert_one(notification)
        return jsonify({"success": True, "message": "Tamu ditolak, dilaporkan ke pemilik"})

    return jsonify({"success": False, "message": "Aksi tidak valid"}), 400

# =====================================
# SOS EMERGENCY SYSTEM
# =====================================

@app.route("/api/sos", methods=["POST"])
@jwt_required()
def trigger_sos():
    claims = get_jwt()
    if claims.get("role") != "penghuni":
        return jsonify({"success": False, "message": "Akses ditolak"}), 403
        
    sos = {
        "kos_id": claims["kos_id"],
        "penghuni_id": get_jwt_identity(),
        "nama": claims.get("nama", "Penghuni"),
        "kamar": claims.get("kamar", "-"),
        "status": "active",
        "created_at": datetime.utcnow()
    }
    # Hanya boleh ada 1 SOS aktif per penghuni
    mongo.db.sos_alerts.update_one(
        {"penghuni_id": get_jwt_identity(), "status": "active"},
        {"$set": sos},
        upsert=True
    )
    
    # Masukkan log aktivitas juga
    mongo.db.activity_logs.insert_one({
        "kos_id": claims["kos_id"],
        "track_id": 0,
        "direction": "masuk",
        "status": "darurat",
        "nama": claims.get("nama", "Penghuni"),
        "kamar": claims.get("kamar", "-"),
        "similarity": 1.0,
        "time": datetime.now().isoformat()
    })
    
    # Masukkan notifikasi juga agar muncul di list Notifikasi Pemilik
    mongo.db.notifications.insert_one({
        "kos_id": claims["kos_id"],
        "title": "🚨 DARURAT (SOS)",
        "message": f"Sinyal SOS dari Kamar {claims.get('kamar', '-')} ({claims.get('nama', 'Penghuni')})",
        "type": "panic",
        "is_read": False,
        "image_url": "",
        "created_at": datetime.utcnow()
    })
    
    return jsonify({"success": True, "message": "SOS berhasil dikirim"})

@app.route("/api/sos", methods=["PUT"])
@jwt_required()
def resolve_sos():
    claims = get_jwt()
    if claims.get("role") != "penghuni":
        return jsonify({"success": False, "message": "Akses ditolak"}), 403
        
    mongo.db.sos_alerts.update_many(
        {"penghuni_id": get_jwt_identity(), "status": "active"},
        {"$set": {"status": "resolved", "resolved_at": datetime.utcnow()}}
    )
    return jsonify({"success": True, "message": "SOS berhasil dimatikan"})

@app.route("/api/sos", methods=["GET"])
@jwt_required()
def check_sos():
    claims = get_jwt()
    kos_id = claims["kos_id"]
    
    active_sos = mongo.db.sos_alerts.find_one({
        "kos_id": kos_id,
        "status": "active"
    })
    
    if active_sos:
        return jsonify({
            "success": True,
            "is_active": True,
            "is_sender": active_sos.get("penghuni_id") == get_jwt_identity(),
            "data": {
                "penghuni_id": active_sos["penghuni_id"],
                "nama": active_sos.get("nama", "Seseorang"),
                "kamar": active_sos.get("kamar", "-")
            }
        })
    else:
        return jsonify({
            "success": True,
            "is_active": False
        })

# =====================================
# GET NOTIFICATIONS
# =====================================

@app.route("/api/notifications", methods=["GET"])
@jwt_required()
def get_notifications():
    claims = get_jwt()
    kos_id = claims["kos_id"]
    role = claims.get("role")
    
    # Filter query berdasarkan role
    if role == "pemilik":
        query = {
            "kos_id": kos_id,
            "type": {"$ne": "guest_confirmation"}
        }
    elif role == "penghuni":
        query = {
            "kos_id": kos_id,
            "type": "guest_confirmation",
            "penghuni_id": get_jwt_identity()
        }
    else:
        query = {"kos_id": kos_id}
    
    data = list(
        mongo.db.notifications.find(
            query,
            {"_id": 1, "title": 1, "message": 1, "type": 1, "is_read": 1, "image_url": 1, "created_at": 1, "tamu_id": 1}
        ).sort("created_at", -1)
    )
    
    # Convert ObjectId to string and format datetime
    for item in data:
        item["_id"] = str(item["_id"])
        
        # Sesuaikan dari UTC ke waktu lokal WIB (+7 jam)
        if isinstance(item.get("created_at"), datetime):
            local_time = item["created_at"] + timedelta(hours=7)
            item["created_at"] = local_time.strftime("%H:%M")
        elif isinstance(item.get("created_at"), str):
            # Jika sudah string (data lama), biarkan saja
            pass
        else:
            item["created_at"] = ""
        
    return jsonify({
        "success": True,
        "data": data
    })

# =====================================
# DASHBOARD CHART
# =====================================

@app.route("/api/dashboard/chart", methods=["GET"])
@jwt_required()
def dashboard_chart():

    claims = get_jwt()

    kos_id = claims["kos_id"]

    # Filter hanya data hari ini
    today = datetime.now().date()
    start_of_day = datetime(today.year, today.month, today.day).isoformat()
    
    logs = list(
        mongo.db.activity_logs.find(
            {
                "kos_id": kos_id,
                "time": {"$gte": start_of_day}
            },
            {
                "_id": 0,
                "time": 1,
                "status": 1
            }
        )
    )

    hourly_all = [0] * 24
    hourly_stranger = [0] * 24

    for log in logs:
        try:
            jam = datetime.fromisoformat(log["time"]).hour
            hourly_all[jam] += 1
            if log.get("status", "").lower() == "stranger":
                hourly_stranger[jam] += 1
        except:
            pass

    return jsonify({
        "success": True,
        "data": {
            "all": hourly_all,
            "stranger": hourly_stranger
        }
    })

# ==========================================
# GET CAMERA FOR AI
# ==========================================

@app.route("/api/ai/kamera", methods=["GET"])
def get_camera_ai():

    kamera = mongo.db.kamera.find_one({
        "status": True
    })

    if kamera is None:
        return jsonify({
            "success": False,
            "message": "Tidak ada kamera aktif"
        }), 404

    return jsonify({
        "success": True,
        "data": {
            "stream_url": kamera["stream_url"],
            "nama_kamera": kamera["nama_kamera"],
            "kos_id": kamera["kos_id"],
            "zone": kamera.get("zone", [])
        }
    })

# ==========================================
# GET SECURITY BIG DATA ANALYTICS
# ==========================================

@app.route('/api/analytics/security', methods=['GET'])
def get_security_analytics():

    try:

        db_bigdata = mongo.cx["safekos_bigdata"]
        analytics_col = db_bigdata["news_analytics"]
        
        analytics = analytics_col.find_one({"_id": "latest_analytics"})
        
        if not analytics:
            analytics = mongo.db.news_analytics.find_one({"_id": "latest_analytics"})
            
        if not analytics:
            return jsonify({
                "success": False,
                "message": "Data analitik big data belum tersedia. Harap jalankan scraping terlebih dahulu."
            }), 404
            
        analytics["_id"] = str(analytics["_id"])
        
        return jsonify({
            "success": True,
            "data": analytics
        }), 200

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

# =========================
# RUN SERVER
# =========================

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        use_reloader=False
    )