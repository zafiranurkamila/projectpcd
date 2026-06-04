from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from database import Base
from datetime import datetime, timezone

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    role = Column(String, default="Staff")

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

class Archive(Base):
    __tablename__ = "archives"
    id = Column(Integer, primary_key=True, index=True)
    
    # Nullable=True sementara agar bisa testing upload tanpa harus bikin User/Kategori dulu
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    
    original_filename = Column(String)
    stored_filename = Column(String)
    file_path = Column(String)
    original_size = Column(Integer) # Dalam Bytes
    compressed_size = Column(Integer) # Dalam Bytes
    compression_ratio = Column(Float)
    processing_time_ms = Column(Float)
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
