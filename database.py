import hashlib
import threading
from datetime import datetime
import mysql.connector
from mysql.connector import pooling, Error
import os

# ============== CONFIGURATION (CLOUD-READY) ==============
DB_CONFIG = {
    'host': os.environ.get('MYSQLHOST', 'localhost'),
    'port': int(os.environ.get('MYSQLPORT', 3306)),
    'user': os.environ.get('MYSQLUSER', 'tankuser'),
    'password': os.environ.get('MYSQLPASSWORD', 'tankpass123'),
    'database': os.environ.get('MYSQLDATABASE', 'tank_battle'),
    'auth_plugin': 'mysql_native_password'
}

POOL_SIZE = 5

class Database:
    def __init__(self):
        self.lock = threading.Lock()
        try:
            self.pool = pooling.MySQLConnectionPool(
                pool_name="tank_pool",
                pool_size=POOL_SIZE,
                pool_reset_session=True,
                **DB_CONFIG
            )
            print("[DB] MySQL connection pool created.")
            self.init_db()
        except Error as e:
            print(f"[DB] FATAL: Could not connect to MySQL: {e}")
            raise

    def _conn(self):
        return self.pool.get_connection()

    def init_db(self):
        with self.lock:
            conn = self._conn()
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS players (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    password_hash VARCHAR(128) NOT NULL,
                    created_at DATETIME NOT NULL,
                    wins INT DEFAULT 0,
                    losses INT DEFAULT 0,
                    total_matches INT DEFAULT 0,
                    INDEX idx_wins (wins DESC)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS matches (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    p1_name VARCHAR(50) NOT NULL,
                    p2_name VARCHAR(50) NOT NULL,
                    p1_score INT NOT NULL,
                    p2_score INT NOT NULL,
                    winner VARCHAR(50) NOT NULL,
                    mode VARCHAR(20) NOT NULL,
                    played_at DATETIME NOT NULL,
                    INDEX idx_played (played_at DESC)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            conn.commit()
            cur.close()
            conn.close()
            print("[DB] Tables verified/created.")

    @staticmethod
    def _hash(password: str) -> str:
        return hashlib.sha256(("salt_2026_" + password).encode()).hexdigest()

    def register_user(self, username, password):
        with self.lock:
            conn = self._conn()
            cur = conn.cursor()
            try:
                cur.execute("""
                    INSERT INTO players (username, password_hash, created_at)
                    VALUES (%s, %s, %s)
                """, (username, self._hash(password), datetime.now()))
                conn.commit()
                print(f"[DB] Registered: {username}")
                return True, self.get_stats(username)
            except mysql.connector.IntegrityError:
                return False, "Username already exists"
            except Error as e:
                return False, f"DB error: {e}"
            finally:
                cur.close()
                conn.close()

    def login_user(self, username, password):
        with self.lock:
            conn = self._conn()
            cur = conn.cursor(dictionary=True)
            try:
                cur.execute("SELECT password_hash FROM players WHERE username = %s", (username,))
                row = cur.fetchone()
                if not row:
                    return False, "User not found"
                if row['password_hash'] != self._hash(password):
                    return False, "Incorrect password"
                print(f"[DB] Login OK: {username}")
                return True, self.get_stats(username)
            finally:
                cur.close()
                conn.close()

    def get_stats(self, username):
        conn = self._conn()
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute("SELECT username, wins, losses, total_matches FROM players WHERE username = %s", (username,))
            row = cur.fetchone()
            if not row: return None
            return {'username': row['username'], 'wins': row['wins'], 'losses': row['losses'], 'total_matches': row['total_matches']}
        finally:
            cur.close()
            conn.close()

    def update_player_stats(self, username, won, draw=False):
        with self.lock:
            conn = self._conn()
            cur = conn.cursor()
            try:
                if draw:
                    cur.execute("UPDATE players SET total_matches = total_matches + 1 WHERE username = %s", (username,))
                elif won:
                    cur.execute("UPDATE players SET wins = wins + 1, total_matches = total_matches + 1 WHERE username = %s", (username,))
                else:
                    cur.execute("UPDATE players SET losses = losses + 1, total_matches = total_matches + 1 WHERE username = %s", (username,))
                conn.commit()
            finally:
                cur.close()
                conn.close()

    def save_match(self, p1_name, p2_name, p1_score, p2_score, winner, mode):
        with self.lock:
            conn = self._conn()
            cur = conn.cursor()
            try:
                cur.execute("""
                    INSERT INTO matches (p1_name, p2_name, p1_score, p2_score, winner, mode, played_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (p1_name, p2_name, p1_score, p2_score, winner, mode, datetime.now()))
                conn.commit()
                print(f"[DB] Match saved: {p1_name} {p1_score}-{p2_score} {p2_name} -> {winner}")
            finally:
                cur.close()
                conn.close()

    def get_leaderboard(self, limit=10):
        conn = self._conn()
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute("""
                SELECT username, wins, losses, total_matches FROM players
                ORDER BY wins DESC, total_matches ASC, losses ASC LIMIT %s
            """, (limit,))
            return cur.fetchall()
        finally:
            cur.close()
            conn.close()