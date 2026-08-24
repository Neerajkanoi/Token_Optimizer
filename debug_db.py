import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import uuid
import bcrypt

load_dotenv()

POSTGRES_USER = os.getenv("POSTGRES_USER", "admin")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "admin_password")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "gateway_db")
DB_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

engine = create_engine(DB_URL)

try:
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS dashboard_users (
                id VARCHAR PRIMARY KEY,
                email VARCHAR UNIQUE NOT NULL,
                password_hash VARCHAR NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
    print("Table created/verified.")
    
    email = "test@example.com"
    password = "password123"
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO dashboard_users (id, email, password_hash) VALUES (:id, :email, :hashed)"),
            {"id": str(uuid.uuid4()), "email": email, "hashed": hashed}
        )
    print("User inserted successfully.")
except Exception as e:
    print(f"Error: {e}")
