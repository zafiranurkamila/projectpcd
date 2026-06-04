# pyrefly: ignore [missing-import]
from sqlalchemy import create_engine
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import declarative_base, sessionmaker

# Kita gunakan SQLite dulu agar tidak perlu setup XAMPP/PostgreSQL di awal
SQLALCHEMY_DATABASE_URL = "sqlite:///./arsip.db"

# Setting up database engine
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency untuk digunakan di main.py agar API bisa terhubung ke DB
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
