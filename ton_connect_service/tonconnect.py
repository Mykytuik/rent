from flask import Flask, request, jsonify, send_from_directory
from pytonconnect import TonConnect
from pytonconnect.storage import IStorage
import hashlib
import time
import requests
import uuid
import json
import os
from dotenv import load_dotenv

# Завантаження змінних із .env
load_dotenv()

app = Flask(__name__, static_folder='static')

# Змінні з .env
NGROK_URL = os.getenv("NGROK_URL")
MANIFEST_URL = os.getenv("MANIFEST_URL")
ICON_URL = os.getenv("ICON_URL")

# Кастомне сховище для TonConnect
class CustomStorage(IStorage):
    def __init__(self):
        self.storage = {}

    async def set_item(self, key: str, value: str):
        self.storage[key] = value

    async def get_item(self, key: str, default_value: str = None):
        return self.storage.get(key, default_value)

    async def remove_item(self, key: str):
        self.storage.pop(key, None)

# Зберігання стану вручну
state_storage = {}
connectors = {}

@app.route('/manifest.json')
def manifest():
    print("Serving manifest.json")
    manifest_data = {
        "url": NGROK_URL,
        "name": "NFT Rental Bot",
        "iconUrl": ICON_URL
    }
    return jsonify(manifest_data)

@app.route('/static/<path:path>')
def send_static(path):
    print(f"Serving static file: {path}")
    return send_from_directory('static', path)

@app.route('/generate-auth-link/<int:chat_id>')
async def generate_auth_link(chat_id):
    state = hashlib.sha256(str(time.time()).encode()).hexdigest()[:32]
    state_storage[chat_id] = state

    # Ініціалізація TonConnect для цього chat_id
    connector = TonConnect(manifest_url=MANIFEST_URL, storage=CustomStorage())
    connectors[chat_id] = connector

    # Генерація payload для ton_proof
    proof_payload = hashlib.sha256(str(time.time()).encode()).hexdigest()[:16]

    # Генерація URL для Tonkeeper
    session_id = uuid.uuid4().hex
    request_data = {
        "manifestUrl": MANIFEST_URL,
        "items": [
            {"name": "ton_addr"},
            {"name": "ton_proof", "payload": proof_payload}
        ]
    }
    encoded_request = requests.utils.quote(json.dumps(request_data))
    return_url = f"{NGROK_URL}/auth-callback?chat_id={chat_id}&state={state}"
    connect_url = (
        f"https://app.tonkeeper.com/ton-connect?v=2&id={session_id}&r={encoded_request}&return={requests.utils.quote(return_url)}"
    )

    print(f"Generated auth link: {connect_url}")
    return jsonify({"auth_url": connect_url})

@app.route('/auth-callback', methods=['GET'])
async def auth_callback():
    print("Handling auth-callback")
    chat_id = request.args.get('chat_id')
    state = request.args.get('state')
    ton_proof = request.args.get('ton_proof', None)

    print(f"Received: chat_id={chat_id}, state={state}, ton_proof={ton_proof}")

    stored_state = state_storage.get(int(chat_id))
    if not stored_state or stored_state != state:
        print("Invalid state or chat_id")
        return jsonify({"error": "Invalid state or chat_id"}), 400

    connector = connectors.get(int(chat_id))
    if not connector:
        print("Connector not found for chat_id")
        return jsonify({"error": "Connector not found"}), 500

    # Очікування підключення
    proof = await connector.wait_for_connection()
    if not proof:
        print("Timeout waiting for connection")
        return jsonify({"error": "Timeout waiting for connection"}), 500

    wallet_address = proof.get('address', 'unknown_address')
    print(f"Connected wallet address: {wallet_address}")

    # Виклик бекенду
    print("Calling backend...")
    try:
        backend_data = requests.get(
            f"http://localhost:8000/api/auth_callback?chat_id={chat_id}"
        ).json()
        print(f"Backend response: {backend_data}")
        return jsonify(backend_data)
    except ValueError:
        print(f"Backend response is not valid JSON: {requests.get(f'http://localhost:8000/api/auth_callback?chat_id={chat_id}').text}")
        return jsonify({"error": "Backend response is not valid JSON"}), 500

    # Очищення
    state_storage.pop(int(chat_id), None)
    connectors.pop(int(chat_id), None)

if __name__ == '__main__':
    port = int(os.getenv('PORT', 3000))
    app.run(host='0.0.0.0', port=port)