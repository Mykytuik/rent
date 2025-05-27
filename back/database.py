import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

# Завантаження змінних із .env
load_dotenv()

class Database:
    def __init__(self):
        # Параметри підключення з .env
        dbname = os.getenv("DB_NAME", "nft_rental_db")
        user = os.getenv("DB_USER", "your_user")
        password = os.getenv("DB_PASSWORD", "your_password")
        host = os.getenv("DB_HOST", "localhost")
        port = os.getenv("DB_PORT", "5432")

        # Створення бази даних, якщо вона не існує
        self._create_database(dbname, user, password, host, port)

        # Підключення до бази даних
        self.conn = psycopg2.connect(
            dbname=dbname,
            user=user,
            password=password,
            host=host,
            port=port
        )
        self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
        self.init_tables()

    def _create_database(self, dbname, user, password, host, port):
        try:
            conn = psycopg2.connect(
                dbname="postgres",
                user=user,
                password=password,
                host=host,
                port=port
            )
            conn.autocommit = True
            cursor = conn.cursor()
            cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{dbname}'")
            exists = cursor.fetchone()
            if not exists:
                cursor.execute(f"CREATE DATABASE {dbname}")
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Error creating database: {e}")
            raise

    def init_tables(self):
        # Таблиця для NFT
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS nfts (
                id SERIAL PRIMARY KEY,
                token_id VARCHAR(255) NOT NULL,
                owner_wallet_address VARCHAR(255) NOT NULL,
                price BIGINT NOT NULL,
                duration INTEGER NOT NULL,
                rental_end_time INTEGER,
                renter_wallet_address VARCHAR(255),
                is_rented BOOLEAN DEFAULT FALSE,
                contract_address VARCHAR(255) NOT NULL
            );
        """)
        # Таблиця для користувачів
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                chat_id BIGINT PRIMARY KEY,
                wallet_address VARCHAR(255)
            );
        """)
        self.conn.commit()

    def add_nft(self, token_id, owner_wallet_address, price, duration, contract_address):
        self.cursor.execute(
            """
            INSERT INTO nfts (token_id, owner_wallet_address, price, duration, contract_address)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING contract_address
            """,
            (token_id, owner_wallet_address, price, duration, contract_address)
        )
        self.conn.commit()
        return self.cursor.fetchone()

    def get_available_nfts(self):
        self.cursor.execute("SELECT * FROM nfts WHERE is_rented = FALSE")
        return self.cursor.fetchall()

    def get_nft_by_token_id(self, token_id):
        self.cursor.execute("SELECT * FROM nfts WHERE token_id = %s AND is_rented = FALSE", (token_id,))
        return self.cursor.fetchone()

    def update_rental(self, token_id, renter_wallet_address, rental_end_time):
        self.cursor.execute(
            """
            UPDATE nfts
            SET is_rented = TRUE, renter_wallet_address = %s, rental_end_time = %s
            WHERE token_id = %s
            """,
            (renter_wallet_address, rental_end_time, token_id)
        )
        self.conn.commit()

    def get_my_nfts(self, wallet_address):
        self.cursor.execute("SELECT * FROM nfts WHERE owner_wallet_address = %s", (wallet_address,))
        owned_nfts = self.cursor.fetchall()
        self.cursor.execute("SELECT * FROM nfts WHERE renter_wallet_address = %s AND is_rented = TRUE", (wallet_address,))
        rented_nfts = self.cursor.fetchall()
        return {"owned_nfts": owned_nfts, "rented_nfts": rented_nfts}

    def save_wallet(self, chat_id, wallet_address):
        self.cursor.execute(
            """
            INSERT INTO users (chat_id, wallet_address)
            VALUES (%s, %s)
            ON CONFLICT (chat_id)
            DO UPDATE SET wallet_address = %s
            """,
            (chat_id, wallet_address, wallet_address)
        )
        self.conn.commit()

    def get_wallet(self, chat_id):
        self.cursor.execute("SELECT wallet_address FROM users WHERE chat_id = %s", (chat_id,))
        result = self.cursor.fetchone()
        return result["wallet_address"] if result else None

    def close(self):
        self.cursor.close()
        self.conn.close()