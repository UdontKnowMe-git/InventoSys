import sqlite3
import psycopg2
import os
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class DatabaseManager:

    def __init__(self, local_db="inventory_final.db"):
        self.local_db = local_db
        self.pg_url = os.getenv("DATABASE_URL")
        self.init_local_db()

    def get_connection(self):
        return sqlite3.connect(self.local_db)

    def init_local_db(self):

        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            stock_qty INTEGER DEFAULT 0,
            unit_cost REAL DEFAULT 0.0,
            retail_price REAL DEFAULT 0.0,
            min_stock INTEGER DEFAULT 10
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            type TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            timestamp TEXT,
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'Employee'
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sync_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT,
            params TEXT,
            timestamp TEXT
        )
        """)

        cursor.execute("SELECT * FROM users WHERE username='admin'")

        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                ("admin", "admin123", "Admin")
            )

        conn.commit()
        conn.close()

# -------------------------------------------------

    def execute_query(self, query, params=(), is_read=False):

        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(query, params)

            if is_read:
                result = cursor.fetchall()

            else:
                conn.commit()
                result = True

                if not query.strip().upper().startswith("SELECT"):
                    self.log_to_queue(query, params)

            conn.close()
            return result

        except Exception as e:
            print("Local DB Error:", e)
            conn.close()
            return None

# -------------------------------------------------

    def log_to_queue(self, query, params):

        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO sync_queue (query, params, timestamp) VALUES (?, ?, ?)",
            (query, json.dumps(params), datetime.now().isoformat())
        )

        conn.commit()
        conn.close()

# -------------------------------------------------

    def fetch_one(self, query, params=()):

        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(query, params)
        row = cursor.fetchone()

        conn.close()
        return row

# -------------------------------------------------
# SYNC SYSTEM
# -------------------------------------------------

    def perform_full_sync(self):

        print("--- STARTING SYNC ---")

        try:
            conn_cloud = psycopg2.connect(self.pg_url)
            conn_cloud.close()
        except Exception as e:
            return False, f"Cannot Connect to Cloud: {e}"

        try:
            self.push_local_to_cloud()
        except Exception as e:
            return False, f"Upload Failed: {e}"

        try:
            self.pull_cloud_to_local()
        except Exception as e:
            return False, f"Download Failed: {e}"

        return True, "Sync Complete! Local DB updated."

# -------------------------------------------------
    def push_local_to_cloud(self):

        conn_local = self.get_connection()
        cur_local = conn_local.cursor()

        cur_local.execute("SELECT id, query, params FROM sync_queue ORDER BY id ASC")
        pending = cur_local.fetchall()

        if not pending:
            conn_local.close()
            print("Nothing to upload.")
            return

        conn_cloud = psycopg2.connect(self.pg_url)
        cur_cloud = conn_cloud.cursor()

        # Ensure cloud tables exist
        self.init_cloud_tables(cur_cloud)
        conn_cloud.commit()

        ids_to_delete = []

        print(f"Uploading {len(pending)} changes...")

        for row_id, query, params_json in pending:

            params = tuple(json.loads(params_json))

            # convert SQLite placeholders to PostgreSQL
            pg_query = query.replace("?", "%s")

            try:

                # Fix only SKU type issue
                if "sku" in pg_query.lower():
                    params = tuple(str(p) for p in params)

                print("Executing:", pg_query, params)

                cur_cloud.execute(pg_query, params)

                conn_cloud.commit()

                ids_to_delete.append(row_id)

            except Exception as e:

                print(f"Error uploading ID {row_id}: {e}")

                conn_cloud.rollback()

        # remove successfully synced queries
        if ids_to_delete:

            placeholders = ",".join("?" * len(ids_to_delete))

            cur_local.execute(
                f"DELETE FROM sync_queue WHERE id IN ({placeholders})",
                ids_to_delete
            )

            conn_local.commit()

        conn_local.close()
        conn_cloud.close()



# -------------------------------------------------

    def pull_cloud_to_local(self):

        print("Downloading from Cloud...")

        conn_cloud = psycopg2.connect(self.pg_url)
        cur_cloud = conn_cloud.cursor()

        cur_cloud.execute("SELECT * FROM products")
        products = cur_cloud.fetchall()

        cur_cloud.execute("SELECT * FROM transactions")
        transactions = cur_cloud.fetchall()

        cur_cloud.execute("SELECT * FROM users")
        users = cur_cloud.fetchall()

        conn_cloud.close()

        conn_local = self.get_connection()
        cur_local = conn_local.cursor()

        cur_local.execute("PRAGMA foreign_keys = OFF")

        cur_local.execute("DELETE FROM products")
        cur_local.execute("DELETE FROM transactions")
        cur_local.execute("DELETE FROM users")

        if products:
            cur_local.executemany(
                "INSERT INTO products VALUES (?,?,?,?,?,?,?)",
                products
            )

        if transactions:
            cur_local.executemany(
                "INSERT INTO transactions VALUES (?,?,?,?,?)",
                transactions
            )

        if users:
            cur_local.executemany(
                "INSERT INTO users VALUES (?,?,?,?)",
                users
            )

        cur_local.execute("PRAGMA foreign_keys = ON")

        conn_local.commit()
        conn_local.close()

        print("Local DB Refreshed.")

# -------------------------------------------------

    def init_cloud_tables(self, cursor):

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            sku TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            stock_qty INTEGER DEFAULT 0,
            unit_cost REAL DEFAULT 0.0,
            retail_price REAL DEFAULT 0.0,
            min_stock INTEGER DEFAULT 10
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id SERIAL PRIMARY KEY,
            product_id INTEGER,
            type TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            timestamp TEXT
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'Employee'
        )
        """)
