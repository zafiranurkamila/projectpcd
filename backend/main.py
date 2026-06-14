from fastapi import FastAPI, UploadFile, File, Depends
from pydantic import BaseModel
import hashlib
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Form
from pydantic import BaseModel
import hashlib
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session
import shutil
import os
import time
import cv2

# Import custom modules
from core.lzw_compressor import compress_image, pack_codes
import models
from database import engine, get_db

# Otomatis membuat tabel-tabel di SQLite sesuai ERD jika belum ada
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="API Kompresi Arsip PCD")

# Wajib ditambahkan: CORS Middleware agar UI HTML (beda folder/port) bisa nembak ke API ini
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Folder untuk menyimpan data lokal
UPLOAD_DIR = "storage/original"
COMPRESSED_DIR = "storage/compressed"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(COMPRESSED_DIR, exist_ok=True)

@app.post("/upload")
async def upload_image(file: UploadFile = File(...), user_id: int = Form(None), db: Session = Depends(get_db)):
    # 1. Simpan file asli sementara
    # Simpan file PNG asli (tanpa di‑hapus) dan buat path untuk arsip
    original_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(original_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 2. Baca gambar dengan OpenCV (pixel mentah)
    image = cv2.imread(original_path, cv2.IMREAD_COLOR)
    if image is None:
        return {"error": "Format gambar tidak didukung atau file rusak"}
    
    # Hitung ukuran file PNG asli (bytes) untuk metadata lossless
    original_size = os.path.getsize(original_path)
    # Jika diperlukan, dapat juga menghitung ukuran raw pixel (tidak disimpan)
    # raw_pixel_size = image.shape[0] * image.shape[1] * image.shape[2]
    
    # 3. Proses Kompresi LZW
    start_time = time.time()
    compressed_data = compress_image(image)
    processing_time_ms = (time.time() - start_time) * 1000
    
    # 4. Simpan ke file biner custom (.lzw) dengan packing variable‑bit
    compressed_filename = file.filename.split('.')[0] + ".lzw"
    compressed_path = os.path.join(COMPRESSED_DIR, compressed_filename)

    # Tentukan lebar bit minimum untuk menampung kode (minimum 9 bit)
    max_code = max(compressed_data) if compressed_data else 0
    bits = max(9, max_code.bit_length())
    bits = min(bits, 16)  # kode tidak lebih dari 16‑bit
    packed = pack_codes(compressed_data)

    with open(compressed_path, "wb") as f:
        # Header dimensi gambar (2 B per nilai)
        f.write(image.shape[0].to_bytes(2, byteorder='big'))
        f.write(image.shape[1].to_bytes(2, byteorder='big'))
        f.write(image.shape[2].to_bytes(2, byteorder='big'))
        # Simpan lebar bit yang digunakan (1 B)
        f.write(bits.to_bytes(1, byteorder='big'))
        # Tulis kode LZW yang sudah dipack
        f.write(packed)
    
    compressed_size = os.path.getsize(compressed_path)
    compression_ratio = original_size / compressed_size if compressed_size > 0 else 0

    # 5. SIMPAN METADATA KE DATABASE (SESUAI ERD)
    # Hitung SHA‑256 file PNG asli
    with open(original_path, "rb") as f_hash:
        h = hashlib.sha256()
        for chunk in iter(lambda: f_hash.read(8192), b""):
            h.update(chunk)
        original_hash = h.hexdigest()

    db_archive = models.Archive(
        user_id=user_id,
        original_filename=file.filename,
        stored_filename=compressed_filename,
        file_path=compressed_path,
        original_file_path=original_path,
        original_sha256=original_hash,
        original_size=original_size,
        compressed_size=compressed_size,
        compression_ratio=round(compression_ratio, 2),
        processing_time_ms=round(processing_time_ms, 2)
    )
    db.add(db_archive)
    db.commit()
    db.refresh(db_archive)

    # File asli tetap disimpan sebagai arsip; tidak di‑hapus
    return {
        "status": "success",
        "message": "File berhasil dikompresi dan metadata disimpan ke Database",
        "database_record": db_archive
    }

# Endpoint untuk mengambil data Dashboard
@app.get("/api/archives")
def get_archives(user_id: int = None, db: Session = Depends(get_db)):
    if user_id is not None:
        return db.query(models.Archive).filter(models.Archive.user_id == user_id).order_by(models.Archive.id.desc()).all()
    return []

# Endpoint untuk melakukan Dekompresi dan Mengunduh Gambar
@app.get("/download/{archive_id}")
def download_archive(archive_id: int, db: Session = Depends(get_db)):
    archive = db.query(models.Archive).filter(models.Archive.id == archive_id).first()
    if not archive:
        return {"error": "Arsip tidak ditemukan"}
        
    compressed_path = archive.file_path
    if not os.path.exists(compressed_path):
        return {"error": "File kompresi (.lzw) tidak ditemukan di server"}

    # --- STRATEGI LOSSLESS ---
    # Untuk memastikan file yang di-download PERSIS sama (byte-for-byte)
    # dengan file asli yang di-upload, kita lakukan:
    #   1. Dekompresi LZW → pixel array (untuk verifikasi lossless)
    #   2. Bandingkan pixel array hasil dekompresi dengan pixel asli
    #   3. Kembalikan FILE ASLI yang sudah tersimpan (bukan re-encode)
    #      sehingga ukuran file PERSIS sama.

    original_path = archive.original_file_path

    # 1. Dekompresi file .lzw untuk membuktikan bahwa LZW ini Lossless!
    with open(compressed_path, "rb") as f:
        shape_h = int.from_bytes(f.read(2), byteorder='big')
        shape_w = int.from_bytes(f.read(2), byteorder='big')
        shape_c = int.from_bytes(f.read(2), byteorder='big')
        bits = int.from_bytes(f.read(1), byteorder='big')
        packed_data = f.read()

    from core.lzw_compressor import unpack_codes, decompress_image
    compressed_data = unpack_codes(packed_data, bits)
    original_shape = (shape_h, shape_w, shape_c)
    restored_array = decompress_image(compressed_data, original_shape)

    # 2. Verifikasi lossless: bandingkan pixel hasil dekompresi dengan asli
    if os.path.exists(original_path):
        original_image = cv2.imread(original_path, cv2.IMREAD_COLOR)
        import numpy as np
        if original_image is not None and np.array_equal(original_image, restored_array):
            # Pixel data 100% identik → kembalikan file asli agar size PERSIS sama
            return FileResponse(
                path=original_path,
                filename=archive.original_filename,
                media_type="image/png"
            )

    # 3. Fallback: jika file asli hilang, simpan hasil dekompresi sebagai PNG
    restored_filename = "restored_" + archive.original_filename.split('.')[0] + ".png"
    temp_img_path = os.path.join("storage/temp_downloads", restored_filename)
    os.makedirs("storage/temp_downloads", exist_ok=True)
    
    cv2.imwrite(temp_img_path, restored_array)
    
    return FileResponse(
        path=temp_img_path,
        filename=archive.original_filename,
        media_type="image/png"
    )

# Endpoint untuk Menghapus 1 Arsip
@app.delete("/api/archives/{archive_id}")
def delete_archive(archive_id: int, db: Session = Depends(get_db)):
    archive = db.query(models.Archive).filter(models.Archive.id == archive_id).first()
    if not archive:
        return {"error": "Arsip tidak ditemukan"}
    
    # Hapus file fisiknya jika ada
    if os.path.exists(archive.file_path):
        os.remove(archive.file_path)
    if os.path.exists(archive.original_file_path):
        os.remove(archive.original_file_path)
        
    db.delete(archive)
    db.commit()
    return {"status": "success"}

# Endpoint untuk Menghapus SEMUA Arsip (Reset)
@app.delete("/api/archives")
def delete_all_archives(db: Session = Depends(get_db)):
    archives = db.query(models.Archive).all()
    for archive in archives:
        if archive.file_path and os.path.exists(archive.file_path):
            os.remove(archive.file_path)
        if archive.original_file_path and os.path.exists(archive.original_file_path):
            os.remove(archive.original_file_path)
        db.delete(archive)
    db.commit()
    return {"status": "success"}

# --- AUTHENTICATION ENDPOINTS ---

class UserRegister(BaseModel):
    full_name: str
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

def get_password_hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

@app.post("/api/auth/register")
def register_user(user: UserRegister, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.username == user.email).first()
    if db_user:
        return {"status": "error", "message": "Email sudah terdaftar!"}
    
    new_user = models.User(
        username=user.email,
        password_hash=get_password_hash(user.password)
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return {"status": "success", "message": "Registrasi berhasil!", "user": {"id": new_user.id, "email": new_user.username}}

@app.post("/api/auth/login")
def login_user(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.username == user.email).first()
    if not db_user or db_user.password_hash != get_password_hash(user.password):
        return {"status": "error", "message": "Email atau password salah!"}
    
    return {"status": "success", "message": "Login berhasil!", "user": {"id": db_user.id, "email": db_user.username}}
