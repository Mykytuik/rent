import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import requests
import asyncio
import os
from dotenv import load_dotenv

# Завантаження змінних із .env
load_dotenv()

# Налаштування логування
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Токен бота та URL бекенду з .env
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BACKEND_URL = os.getenv("BACKEND_URL")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Ласкаво просимо до NFT Rental Bot!\n"
        "/auth - Авторизуватися через Tonkeeper\n"
        "/list - Переглянути доступні NFT\n"
        "/rent - Орендувати NFT\n"
        "/offer - Здати NFT в оренду\n"
        "/my_nfts - Переглянути ваші NFT"
    )

async def auth(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat_id
    response = requests.get(f"{BACKEND_URL}/api/generate_auth_link/{chat_id}")
    if response.status_code != 200:
        await update.message.reply_text("Помилка при створенні лінка автентифікації.")
        return

    auth_url = response.json().get("auth_url")
    await update.message.reply_text(
        f"Авторизуйтесь через Tonkeeper:\n{auth_url}\n"
        "Після авторизації ви отримаєте повідомлення про успішне підключення."
    )

async def list_nfts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat_id
    response = requests.get(f"{BACKEND_URL}/api/nfts")
    if response.status_code != 200:
        await update.message.reply_text("Помилка при отриманні списку NFT.")
        return

    nfts = response.json()
    if not nfts:
        await update.message.reply_text("Немає доступних NFT для оренди.")
        return

    reply = "Доступні NFT для оренди:\n"
    for nft in nfts:
        reply += f"ID: {nft['token_id']}, Ціна: {nft['price']} наноTON, Тривалість: {nft['duration'] // 86400} днів\n"
    await update.message.reply_text(reply)

async def offer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat_id
    wallet_address = requests.get(f"{BACKEND_URL}/api/get_wallet/{chat_id}").json().get("wallet_address")
    if not wallet_address:
        await update.message.reply_text("Спочатку авторизуйтесь через /auth")
        return

    response = requests.get(f"{BACKEND_URL}/api/user_nfts/{wallet_address}")
    if response.status_code != 200:
        await update.message.reply_text("Помилка при отриманні ваших NFT.")
        return

    user_nfts = response.json()
    if not user_nfts:
        await update.message.reply_text("У вас немає NFT з колекції анонімних номерів Telegram.")
        return

    reply = "Ваші NFT:\n"
    for idx, nft in enumerate(user_nfts, 1):
        reply += f"{idx}. ID: {nft['tokenId']}\n"
    reply += "Введіть номер NFT, ціну (наноTON) і тривалість (дні), наприклад: 1 1000000 7"
    await update.message.reply_text(reply)

async def rent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat_id
    wallet_address = requests.get(f"{BACKEND_URL}/api/get_wallet/{chat_id}").json().get("wallet_address")
    if not wallet_address:
        await update.message.reply_text("Спочатку авторизуйтесь через /auth")
        return

    await update.message.reply_text("Введіть ID NFT для оренди:")

async def my_nfts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat_id
    wallet_address = requests.get(f"{BACKEND_URL}/api/get_wallet/{chat_id}").json().get("wallet_address")
    if not wallet_address:
        await update.message.reply_text("Спочатку авторизуйтесь через /auth")
        return

    response = requests.get(f"{BACKEND_URL}/api/my_nfts/{wallet_address}")
    if response.status_code != 200:
        await update.message.reply_text("Помилка при отриманні ваших NFT.")
        return

    data = response.json()
    owned_nfts = data.get("owned_nfts", [])
    rented_nfts = data.get("rented_nfts", [])

    reply = "Ваші NFT:\n"
    if owned_nfts:
        reply += "Здані в оренду вами:\n"
        for nft in owned_nfts:
            status = f"Орендовано до {nft['rental_end_time']}" if nft["is_rented"] else "Доступно"
            reply += f"ID: {nft['token_id']}, {status}, Контракт: {nft['contract_address']}\n"
    if rented_nfts:
        reply += "Орендовані вами:\n"
        for nft in rented_nfts:
            reply += f"ID: {nft['token_id']}, Закінчення: {nft['rental_end_time']}, Контракт: {nft['contract_address']}\n"
    if not owned_nfts and not rented_nfts:
        reply = "У вас немає NFT."
    await update.message.reply_text(reply)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat_id
    text = update.message.text

    if not update.message.reply_to_message:
        return

    wallet_address = requests.get(f"{BACKEND_URL}/api/get_wallet/{chat_id}").json().get("wallet_address")
    if not wallet_address:
        await update.message.reply_text("Спочатку авторизуйтесь через /auth")
        return

    if "Введіть номер NFT" in update.message.reply_to_message.text:
        user_nfts = requests.get(f"{BACKEND_URL}/api/user_nfts/{wallet_address}").json()
        try:
            nft_index, price, duration_days = map(int, text.split())
            duration_sec = duration_days * 86400
            if nft_index < 1 or nft_index > len(user_nfts) or duration_sec < 604800:
                raise ValueError
        except ValueError:
            await update.message.reply_text("Невірний формат, номер NFT або тривалість менше 1 тижня. Спробуйте ще раз.")
            return

        selected_nft = user_nfts[nft_index - 1]
        response = requests.post(f"{BACKEND_URL}/api/offer", json={
            "wallet_address": wallet_address,
            "token_id": selected_nft["tokenId"],
            "price": price,
            "duration": duration_sec
        })

        if response.status_code == 200:
            data = response.json()
            await update.message.reply_text(
                f"NFT {selected_nft['tokenId']} здано в оренду за {price} наноTON на {duration_days} днів.\n"
                f"Адреса контракту: {data['contract_address']}"
            )
        else:
            await update.message.reply_text("Помилка при здачі NFT.")

    if "Введіть ID NFT для оренди" in update.message.reply_to_message.text:
        token_id = text.strip()
        response = requests.post(f"{BACKEND_URL}/api/rent", json={
            "token_id": token_id,
            "wallet_address": wallet_address
        })

        if response.status_code == 200:
            data = response.json()
            await update.message.reply_text(
                f"Ви орендували NFT {token_id} за {data['price']} наноTON.\n"
                f"Оренда до {data['rental_end_time']}.\n"
                f"Код для входу: {data['auth_code']}"
            )
        else:
            await update.message.reply_text(response.json().get("error", "Помилка оренди."))

def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN not set in .env")
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("auth", auth))
    application.add_handler(CommandHandler("list", list_nfts))
    application.add_handler(CommandHandler("offer", offer))
    application.add_handler(CommandHandler("rent", rent))
    application.add_handler(CommandHandler("my_nfts", my_nfts))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()