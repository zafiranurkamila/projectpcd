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
from core.lzw_compressor import compress_image
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
    temp_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # 2. Baca dengan OpenCV (Warna Asli)
    image = cv2.imread(temp_path, cv2.IMREAD_COLOR)
    if image is None:
        return {"error": "Format gambar tidak didukung atau file rusak"}
        
    # PERBAIKAN KRUSIAL: Hitung ukuran RAW (matriks piksel utuh), bukan ukuran file .png-nya!
    # Standar PCD: Ukuran asli = Tinggi x Lebar x Channel (Bytes)
    original_size = image.shape[0] * image.shape[1] * image.shape[2]
    
    # 3. Proses Kompresi LZW
    start_time = time.time()
    compressed_data = compress_image(image)
    processing_time_ms = (time.time() - start_time) * 1000
    
    # 4. Simpan ke file biner custom (.lzw)
    compressed_filename = file.filename.split('.')[0] + ".lzw"
    compressed_path = os.path.join(COMPRESSED_DIR, compressed_filename)
    
    with open(compressed_path, "wb") as f:
        # Simpan dimensi gambar di awal file (header) agar bisa di-dekompresi
        # Karena berwarna, format shape-nya adalah (height, width, channels)
        f.write(f"{image.shape[0]},{image.shape[1]},{image.shape[2]}\n".encode())
        for code in compressed_data:
            f.write(code.to_bytes(2, byteorder='big'))
            
    compressed_size = os.path.getsize(compressed_path)
    compression_ratio = original_size / compressed_size if compressed_size > 0 else 0
    
    # 5. SIMPAN METADATA KE DATABASE (SESUAI ERD)
    db_archive = models.Archive(
        user_id=user_id,
        original_filename=file.filename,
        stored_filename=compressed_filename,
        file_path=compressed_path,
        original_size=original_size,
        compressed_size=compressed_size,
        compression_ratio=round(compression_ratio, 2),
        processing_time_ms=round(processing_time_ms, 2)
    )
    db.add(db_archive)
    db.commit()
    db.refresh(db_archive)
    
    # Hapus file asli karena ini adalah sistem kompresi
    os.remove(temp_path)
    
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
        
    # 1. BACA FILE BINER TERKOMPRESI (.lzw)
    with open(compressed_path, "rb") as f:
        # Baca header dimensi gambar
        header = f.readline().decode().strip()
        dims = header.split(',')
        if len(dims) == 3:
            original_shape = (int(dims[0]), int(dims[1]), int(dims[2])) # Berwarna (RGB/BGR)
        else:
            original_shape = (int(dims[0]), int(dims[1])) # Fallback grayscale dari file lama
        
        # Baca sisa data LZW
        compressed_data = []
        while True:
            bytes_read = f.read(2)
            if not bytes_read:
                break
            compressed_data.append(int.from_bytes(bytes_read, byteorder='big'))
            
    # 2. DEKOMPRESI MENGGUNAKAN ALGORITMA PCD (Mengembalikan matriks ke semula)
    from core.lzw_compressor import decompress_image
    decompressed_array = decompress_image(compressed_data, original_shape)
    
    # 3. SIMPAN SEMENTARA SEBAGAI GAMBAR UTUH
    temp_dir = "storage/temp_downloads"
    os.makedirs(temp_dir, exist_ok=True)
    restored_filename = f"restored_{archive.original_filename}"
    temp_img_path = os.path.join(temp_dir, restored_filename)
    
    cv2.imwrite(temp_img_path, decompressed_array)
    
    # 4. KIRIM KE BROWSER SEBAGAI FILE UNDUHAN
    return FileResponse(
        path=temp_img_path, 
        filename=restored_filename, 
        media_type="image/bmp"
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
        
    db.delete(archive)
    db.commit()
    return {"status": "success"}

# Endpoint untuk Menghapus SEMUA Arsip (Reset)
@app.delete("/api/archives")
def delete_all_archives(db: Session = Depends(get_db)):
    archives = db.query(models.Archive).all()
    for archive in archives:
        if os.path.exists(archive.file_path):
            os.remove(archive.file_path)
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
