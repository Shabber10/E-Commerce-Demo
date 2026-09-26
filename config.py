import os
import re
import sqlite3

from datetime import datetime

try:
    import mysql.connector
    from mysql.connector import Error as MySQLError
except ImportError:
    mysql = None
    MySQLError = Exception

# Auto-load .env file if present in workspace root (without overwriting platform env vars)
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
if os.path.exists(_env_path):
    try:
        with open(_env_path, 'r', encoding='utf-8') as _env_f:
            for _raw_line in _env_f:
                _line = _raw_line.strip()
                if _line and not _line.startswith('#') and '=' in _line:
                    _k, _v = _line.split('=', 1)
                    _k_clean = _k.strip()
                    if _k_clean not in os.environ:
                        os.environ[_k_clean] = _v.strip().strip("'\"")
    except Exception as _env_err:
        print(f"Notice: Could not load .env file: {_env_err}")


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'super-secret-key-change-in-production-ecommerce-2026')

    # Database Engine Selection: 'sqlite' (default, portable, Render friendly) or 'mysql'
    DB_ENGINE = os.environ.get('DB_ENGINE', 'sqlite').lower()
    SQLITE_DB_PATH = os.environ.get('SQLITE_DB_PATH', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'smartcart.db'))

    # MySQL Configuration (fallback / optional)
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_USER = os.environ.get('DB_USER', 'root')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', 'shabber')
    DB_NAME = os.environ.get('DB_NAME', 'e_commerce')

    # Uploads Configuration
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads'))
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

    # Razorpay Configuration (Get your live/test key from https://dashboard.razorpay.com/app/keys)
    RAZORPAY_MID = os.environ.get('RAZORPAY_MID', 'Tfw8efs0GjjqBQ')
    RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', 'rzp_test_TgJilFyDTJEMzP')
    RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', 'eaZjzBw6hEyEckgKRLde6tKP')

    # Store UPI ID for Direct UPI Payments
    STORE_UPI_ID = os.environ.get('STORE_UPI_ID', '9704039617@fam')

    # Email / SMTP Configuration (Gmail OTP)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', 'shabber12396@gmail.com')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', 'wkwzifnnfzfjxrdp')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'shabber12396@gmail.com')


# Ensure upload directory and SQLite database directory exist
try:
    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(Config.SQLITE_DB_PATH)), exist_ok=True)

    # Seed images if custom UPLOAD_FOLDER is configured (e.g. Render persistent disk)
    _seed_uploads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    if os.path.abspath(_seed_uploads_dir) != os.path.abspath(Config.UPLOAD_FOLDER) and os.path.exists(_seed_uploads_dir):
        import shutil
        for _f in os.listdir(_seed_uploads_dir):
            _src = os.path.join(_seed_uploads_dir, _f)
            _dst = os.path.join(Config.UPLOAD_FOLDER, _f)
            if os.path.isfile(_src) and not os.path.exists(_dst):
                try:
                    shutil.copy2(_src, _dst)
                except Exception:
                    pass
except Exception as _dir_err:
    print(f"Notice: Directory initialization error: {_dir_err}")


# =============================================================
# SQLite COMPATIBILITY LAYER FOR FLASK
# Provides standard cursor(dictionary=True) and translates %s -> ?
# =============================================================
class SQLiteCursorWrapper:
    """Wraps sqlite3.Cursor to provide MySQL-compatible %s placeholder and dictionary results."""
    def __init__(self, cursor, dictionary=False):
        self._cursor = cursor
        self.dictionary = dictionary

    def _translate(self, sql):
        if not sql:
            return sql
        # Translate MySQL INSERT IGNORE -> SQLite INSERT OR IGNORE
        sql = sql.replace('INSERT IGNORE INTO', 'INSERT OR IGNORE INTO')
        
        # Translate ON DUPLICATE KEY UPDATE for cart_items and inventory
        if 'cart_items' in sql and 'ON DUPLICATE KEY UPDATE' in sql:
            sql = re.sub(
                r'ON DUPLICATE KEY UPDATE.*',
                'ON CONFLICT(cart_id, product_id) DO UPDATE SET quantity = quantity + excluded.quantity',
                sql,
                flags=re.IGNORECASE
            )
        elif 'inventory' in sql and 'ON DUPLICATE KEY UPDATE' in sql:
            sql = re.sub(
                r'ON DUPLICATE KEY UPDATE.*',
                'ON CONFLICT(product_id) DO UPDATE SET quantity = excluded.quantity',
                sql,
                flags=re.IGNORECASE
            )

        # Replace MySQL GREATEST with SQLite MAX
        sql = re.sub(r'\bGREATEST\b', 'MAX', sql, flags=re.IGNORECASE)

        # Replace MySQL placeholder %s with SQLite placeholder ?
        sql = sql.replace('%s', '?')
        return sql

    def execute(self, sql, params=None):
        tsql = self._translate(sql)
        if params is not None:
            return self._cursor.execute(tsql, tuple(params))
        return self._cursor.execute(tsql)

    def _parse_row(self, row):
        if row is None:
            return None
        d = dict(row) if self.dictionary else row
        if isinstance(d, dict):
            for k, v in list(d.items()):
                if isinstance(v, str) and (k.endswith('_date') or k.endswith('_at') or k == 'created_at' or k == 'updated_at' or k == 'payment_date' or k == 'order_date'):
                    try:
                        # Clean sqlite timestamp string: '2026-09-24 05:17:19'
                        clean_ts = v.replace('T', ' ')[:19]
                        d[k] = datetime.strptime(clean_ts, '%Y-%m-%d %H:%M:%S')
                    except Exception:
                        pass
        return d

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        return self._parse_row(row)

    def fetchall(self):
        rows = self._cursor.fetchall()
        return [self._parse_row(r) for r in rows]

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def close(self):
        try:
            return self._cursor.close()
        except Exception:
            pass


class SQLiteConnectionWrapper:
    """Wraps sqlite3.Connection to provide .cursor(dictionary=True)."""
    def __init__(self, conn):
        self._conn = conn

    def cursor(self, dictionary=False):
        return SQLiteCursorWrapper(self._conn.cursor(), dictionary=dictionary)

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        return self._conn.close()


def db_connection():
    """Returns an active database connection (SQLite by default, or MySQL)."""
    if Config.DB_ENGINE == 'sqlite':
        try:
            conn = sqlite3.connect(Config.SQLITE_DB_PATH, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            return SQLiteConnectionWrapper(conn)
        except Exception as err:
            print(f"SQLite database connection error: {err}")
            return None
    else:
        # MySQL connection
        if not mysql:
            print("mysql-connector is not installed, falling back to SQLite.")
            return sqlite3.connect(Config.SQLITE_DB_PATH)
        try:
            conn = mysql.connector.connect(
                host=Config.DB_HOST,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                database=Config.DB_NAME
            )
            return conn
        except MySQLError as err:
            print(f"MySQL connection error: {err}")
            return None


def init_db():
    """Initializes the database schema and sample data on startup."""
    if Config.DB_ENGINE == 'sqlite':
        try:
            schema_file = os.path.join(os.path.dirname(__file__), 'db', 'schema_sqlite.sql')
            if not os.path.exists(schema_file):
                schema_file = os.path.join(os.path.dirname(__file__), 'db', 'schema.sql')

            conn = sqlite3.connect(Config.SQLITE_DB_PATH)
            if os.path.exists(schema_file):
                with open(schema_file, 'r', encoding='utf-8') as f:
                    conn.executescript(f.read())

            # Ensure default admin and demo user accounts have valid, tested bcrypt credentials
            # Admin: shabber10343@gmail.com / Admin@123
            # Customer: customer@example.com / User@123
            admin_hash = '$2b$12$5Zdk7e60xxuD30D/UlXjXOYgWMqHW/obWcRV7TeMbSYb855OuIuBm'
            user_hash = '$2b$12$YRsjEuoqnDpWwno.JcYL4.x.c0e4w4eGCEkg2SR0ipmFApM3B8IwK'
            cur = conn.cursor()
            cur.execute("""
                UPDATE customers 
                SET password_hash = ?
                WHERE LOWER(e_mail) = 'shabber10343@gmail.com'
                  AND (password_hash LIKE '$2b$12$041oYgUq%' OR password_hash != ?)
            """, (admin_hash, admin_hash))
            cur.execute("""
                INSERT OR IGNORE INTO customers (customer_id, first_name, last_name, e_mail, password_hash, role, phone_number, status)
                VALUES (2, 'Demo', 'Customer', 'customer@example.com', ?, 'user', '9876543211', 'active')
            """, (user_hash,))
            cur.execute("INSERT OR IGNORE INTO cart (customer_id) VALUES (1)")
            cur.execute("INSERT OR IGNORE INTO cart (customer_id) VALUES (2)")
            conn.commit()
            conn.close()
            print(f"SQLite database initialized successfully at: {Config.SQLITE_DB_PATH}")
            return True
        except Exception as err:
            print(f"SQLite initialization error: {err}")
            return False
    else:
        # MySQL initialization
        if not mysql:
            return False
        try:
            server_conn = mysql.connector.connect(
                host=Config.DB_HOST,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD
            )
            cursor = server_conn.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {Config.DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
            cursor.close()
            server_conn.close()

            conn = db_connection()
            if not conn:
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
                        except Exception:
                            pass
                conn.commit()
                print("MySQL database schema verified and loaded.")
            cursor.close()
            conn.close()
            return True
        except Exception as err:
            print(f"MySQL initialization error: {err}")
            return False


if __name__ == '__main__':
    init_db()
