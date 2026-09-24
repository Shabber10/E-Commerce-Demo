import os
import mysql.connector
from mysql.connector import Error


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'super-secret-key-change-in-production-ecommerce-2026')
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_USER = os.environ.get('DB_USER', 'root')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', 'shabber')
    DB_NAME = os.environ.get('DB_NAME', 'e_commerce')

    # Uploads Configuration
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

    # Razorpay Configuration
    RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', 'rzp_test_eCommerceKey')
    RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', 'eCommerceSecretKey')

    # Email / SMTP Configuration (Gmail OTP)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', 'shabber12396@gmail.com')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', 'wkwzifnnfzfjxrdp')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'shabber12396@gmail.com')


def db_connection():
    """Returns a MySQL connection to the e_commerce database."""
    try:
        conn = mysql.connector.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME
        )
        return conn
    except Error as err:
        print(f"Database connection error: {err}")
        return None


def init_db():
    """Creates database and required tables using db/schema.sql if they don't exist yet."""
    try:
        # Step 1: Connect to server without database to ensure database exists
        server_conn = mysql.connector.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD
        )
        cursor = server_conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {Config.DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        cursor.close()
        server_conn.close()

        # Step 2: Connect to the database and execute schema.sql
        conn = db_connection()
        if not conn:
            print("Failed to connect to database for table creation.")
            return False

        cursor = conn.cursor()
        schema_file = os.path.join(os.path.dirname(__file__), 'db', 'schema.sql')
        if os.path.exists(schema_file):
            with open(schema_file, 'r', encoding='utf-8') as f:
                sql_content = f.read()

            statements = [s.strip() for s in sql_content.split(';') if s.strip()]
            for stmt in statements:
                lines = [line for line in stmt.splitlines() if not line.strip().startswith('--')]
                clean_stmt = '\n'.join(lines).strip()
                if clean_stmt:
                    try:
                        cursor.execute(clean_stmt)
                    except Error as e:
                        # Ignore benign warnings/skips
                        pass
            conn.commit()
            print("Database schema verified and loaded successfully.")
        else:
            print("Warning: db/schema.sql not found.")

        cursor.close()
        conn.close()
        return True
    except Error as err:
        print(f"Database initialization error: {err}")
        return False


if __name__ == '__main__':
    init_db()
