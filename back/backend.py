from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
from datetime import datetime
import time
import os
from dotenv import load_dotenv

# Завантаження змінних із .env
load_dotenv()

app = FastAPI()

# Змінні з .env
PLATFORM_ADDRESS = os.getenv("PLATFORM_ADDRESS")
PLATFORM_PUBLIC_KEY = os.getenv("PLATFORM_PUBLIC_KEY")
TELEGRAM_NUMBERS_COLLECTION = os.getenv("TELEGRAM_NUMBERS_COLLECTION")
CALLBACK_URL = os.getenv("CALLBACK_URL")
TONCONNECT_URL = os.getenv("TONCONNECT_URL")
TONAPI_KEY = os.getenv("TONAPI_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Модель для оренди
class RentRequest(BaseModel):
    token_id: str
    wallet_address: str

class OfferRequest(BaseModel):
    token_id: str
    wallet_address: str
    price: int
    duration: int

# Імітація бази даних
class Database:
    def __init__(self):
        self.wallets = {}
        self.nfts = {}

    def save_wallet(self, chat_id, wallet_address):
        self.wallets[chat_id] = wallet_address
        print(f"Saved wallet: chat_id={chat_id}, address={wallet_address}")

    def get_wallet(self, chat_id):
        return self.wallets.get(chat_id)

    def get_available_nfts(self):
        return list(self.nfts.values())

    def get_nft_by_token_id(self, token_id):
        return self.nfts.get(token_id)

    def add_nft(self, token_id, owner_wallet_address, price, duration, contract_address):
        self.nfts[token_id] = {
            "token_id": token_id,
            "owner_wallet_address": owner_wallet_address,
            "price": price,
            "duration": duration,
            "contract_address": contract_address,
            "renter_wallet_address": None,
            "rental_end_time": None
        }
        return {"contract_address": contract_address}

    def update_rental(self, token_id, renter_wallet_address, rental_end_time):
        if token_id in self.nfts:
            self.nfts[token_id]["renter_wallet_address"] = renter_wallet_address
            self.nfts[token_id]["rental_end_time"] = rental_end_time

    def get_my_nfts(self, wallet_address):
        return [nft for nft in self.nfts.values() if nft["owner_wallet_address"] == wallet_address]

# Ініціалізація бази даних
db = Database()

# Генерація лінка для автентифікації через TON Connect
@app.get("/api/generate_auth_link/{chat_id}")
async def generate_auth_link(chat_id: int):
    response = requests.get(f"{TONCONNECT_URL}/generate-auth-link/{chat_id}")
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Failed to generate auth link")
    return response.json()

# Обробка callback після авторизації
@app.get("/api/auth_callback")
async def auth_callback(chat_id: str):
    # Надсилаємо повідомлення в Telegram
    message = "Wallet connected successfully!"
    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    telegram_response = requests.post(
        telegram_url,
        json={"chat_id": chat_id, "text": message}
    )
    if telegram_response.status_code != 200:
        print(f"Failed to send Telegram message: {telegram_response.text}")
        raise HTTPException(status_code=500, detail="Failed to send Telegram message")

    return {"status": "success", "message": "Authorization successful"}

@app.get("/api/nfts")
def get_available_nfts():
    return db.get_available_nfts()

@app.get("/api/get_wallet/{chat_id}")
def get_wallet(chat_id: int):
    wallet_address = db.get_wallet(chat_id)
    return {"wallet_address": wallet_address}

@app.get("/api/user_nfts/{wallet_address}")
def get_user_nfts(wallet_address: str):
    response = requests.get(
        "https://tonapi.io/v2/accounts/{wallet_address}/nfts",
        headers={"Authorization": f"Bearer {TONAPI_KEY}"},
        params={"collection": TELEGRAM_NUMBERS_COLLECTION}
    )
    if response.status_code == 200:
        nfts = response.json().get("nft_items", [])
        return [{"tokenId": nft["address"]} for nft in nfts if nft["collection"]["address"] == TELEGRAM_NUMBERS_COLLECTION]
    return []

@app.post("/api/offer")
def offer_nft(request: OfferRequest):
    contract_address = deploy_smart_contract(
        request.wallet_address,
        request.token_id,
        request.price,
        request.duration
    )
    result = db.add_nft(
        token_id=request.token_id,
        owner_wallet_address=request.wallet_address,
        price=request.price,
        duration=request.duration,
        contract_address=contract_address
    )
    return {"contract_address": result["contract_address"]}

@app.post("/api/rent")
def rent_nft(request: RentRequest):
    nft = db.get_nft_by_token_id(request.token_id)
    if not nft:
        raise HTTPException(status_code=404, detail="NFT not found or already rented")

    rental_result = rent_nft(nft["contract_address"], request.wallet_address, nft["price"])
    if not rental_result["success"]:
        raise HTTPException(status_code=500, detail="Rental failed")

    rental_end_time = int(time.time()) + nft["duration"]
    db.update_rental(request.token_id, request.wallet_address, rental_end_time)

    deeplink = f"tc://?v=2&id={request.wallet_address}"
    renter_signature = sign_deeplink(request.wallet_address, deeplink)
    platform_signature = sign_with_platform(renter_signature)
    code_result = call_get_code(nft["contract_address"], deeplink, renter_signature, platform_signature)

    return {
        "price": nft["price"],
        "rental_end_time": datetime.fromtimestamp(rental_end_time).isoformat(),
        "auth_code": code_result["code"]
    }

@app.get("/api/my_nfts/{wallet_address}")
def my_nfts(wallet_address: str):
    return db.get_my_nfts(wallet_address)

def deploy_smart_contract(wallet_address, token_id, price, duration):
    # Реальна логіка розгортання смарт-контракту через TON SDK
    return f"EQ_{wallet_address}_{token_id}"

def rent_nft(contract_address, wallet_address, price):
    # Реальна логіка оренди через смарт-контракт
    return {"success": True}

def sign_deeplink(wallet_address, deeplink):
    # Реальна логіка підпису через приватний ключ платформи
    return "renter_signature"

def sign_with_platform(renter_signature):
    # Реальна логіка підпису через приватний ключ платформи
    return "platform_signature"

def call_get_code(contract_address, deeplink, renter_signature, platform_signature):
    # Реальна логіка виклику get_code через TON SDK
    return {"code": "auth_code_123"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)