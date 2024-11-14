const express = require('express');
const { Client, LocalAuth, MessageMedia } = require('whatsapp-web.js');
const fs = require('fs');
const qrcode = require('qrcode-terminal');
const path = require('path');
const { exec } = require('child_process');
const sendMessageWithRetry = require('./api/utils/sendMessageWithRetry');

const app = express();
const PORT = 3000;

app.use(express.json());

const state = {
  isReady: false,
};

let client;

function initializeClient() {
  client = new Client({
    puppeteer: {
      headless: true,
      //executablePath: '/usr/bin/chromium-browser',
      executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-accelerated-2d-canvas',
        '--no-first-run',
        '--no-zygote',
        '--single-process',
        '--disable-gpu',
        '--disable-web-security',
        '--window-size=1280,800',
        '--disable-infobars',
        '--start-maximized',
      ],
    },
    authStrategy: new LocalAuth({
      dataPath: './auth_info',
    }),
  });

  const eventsPath = path.join(__dirname, 'events');
  const eventFiles = fs.readdirSync(eventsPath).filter(file => file.endsWith('.js'));

  for (const file of eventFiles) {
    const filePath = path.join(eventsPath, file);
    const event = require(filePath);
    if (event.once) {
      client.once(event.name, (...args) => event.execute(...args, client, state));
    } else {
      client.on(event.name, (...args) => event.execute(...args, client, state));
    }
  }

  client.on('disconnected', async (reason) => {
    console.log('Cliente desconectado:', reason);
    state.isReady = false;
    await client.initialize();
  });

  client.initialize();
}

initializeClient();

require('./api/send-message')(app, client, state);
require('./api/send-image-message')(app, client, state);
require('./api/generate-and-send-pdf')(app, client, state); // Add this line to include the new endpoint
require('./api/send-message-group')(app, client, state);

app.listen(PORT, () => {
  console.log(`Servidor escuchando en el puerto ${PORT}`);
});
