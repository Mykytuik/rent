const express = require('express');
const { TonConnect } = require('@tonconnect/sdk');
const crypto = require('crypto');
const fetch = require('node-fetch');
const app = express();
const port = 3000;

app.use(express.json());

// Кастомне сховище замість localStorage
const customStorage = {
    getItem: (key) => customStorage[key] || null,
    setItem: (key, value) => { customStorage[key] = value; },
    removeItem: (key) => { delete customStorage[key]; }
};

// Зберігання стану вручну
const stateStorage = {};

const manifestUrl = 'https://4e26-188-241-176-130.ngrok-free.app/manifest.json';
console.log('Initializing TonConnect with manifestUrl:', manifestUrl);

let connector;
async function initializeConnector() {
    try {
        connector = new TonConnect({ manifestUrl, storage: customStorage });
        console.log('TonConnect initialized successfully');
    } catch (error) {
        console.error('Failed to initialize TonConnect:', error);
    }
}
initializeConnector();

app.get('/manifest.json', (req, res) => {
    console.log('Serving manifest.json');
    const manifest = {
        url: 'https://4e26-188-241-176-130.ngrok-free.app',
        name: 'NFT Rental Bot'
    };
    res.json(manifest);
});

app.get('/generate-auth-link/:chat_id', async (req, res) => {
    const chat_id = req.params.chat_id;
    const state = crypto.randomBytes(32).toString('hex');
    stateStorage[chat_id] = state;

    if (!connector) {
        console.error('Connector not initialized');
        return res.status(500).json({ error: 'Connector not initialized' });
    }

    try {
        console.log('Generating auth link for chat_id:', chat_id);
        const returnUrl = `https://4e26-188-241-176-130.ngrok-free.app/auth-callback?chat_id=${chat_id}`;
        console.log('Using returnUrl:', returnUrl);
        const connectUrl = await connector.connect({
            returnUrl: returnUrl,
            state: state,
            items: ['ton_addr', 'ton_proof']
        });
        res.json({ auth_url: connectUrl });
    } catch (error) {
        console.error('Error generating auth link:', error);
        res.status(500).json({ error: 'Failed to generate auth link' });
    }
});

app.get('/auth-callback', async (req, res) => {
    const chat_id = req.query.chat_id;
    const state = req.query.state;
    const ton_proof = req.query['ton_proof'];

    console.log('Handling auth callback for chat_id:', chat_id, 'with state:', state);

    if (!connector) {
        console.error('Connector not initialized');
        return res.status(500).json({ error: 'Connector not initialized' });
    }

    const storedState = stateStorage[chat_id];
    if (!storedState || storedState !== state) {
        console.error('Invalid state or chat_id');
        return res.status(400).json({ error: 'Invalid state or chat_id' });
    }

    try {
        const walletInfo = await connector.restoreConnection();
        if (!walletInfo || !walletInfo.account.address) {
            console.error('Failed to verify wallet connection');
            return res.status(400).json({ error: 'Failed to verify wallet connection' });
        }

        const wallet_address = walletInfo.account.address;
        delete stateStorage[chat_id];

        const backendResponse = await fetch(`http://localhost:8000/api/auth_callback?chat_id=${chat_id}`, {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' }
        });
        if (!backendResponse.ok) {
            console.error('Backend error:', await backendResponse.text());
            return res.status(backendResponse.status).json({ error: 'Backend error' });
        }
        const backendData = await backendResponse.json();
        res.json(backendData);
    } catch (error) {
        console.error('Auth callback error:', error);
        res.status(500).json({ error: 'Internal server error' });
    }
});

app.listen(port, () => {
    console.log(`TON Connect service running on port ${port}`);
});