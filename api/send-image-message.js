const path = require('path');
const { MessageMedia } = require('whatsapp-web.js');
const sendMessageWithRetry = require('./utils/sendMessageWithRetry');

module.exports = (app, client, state) => {
    app.post('/send-image-message', async (req, res) => {
        const { number, message, imageName } = req.body;

        if (!number || !message || !imageName) {
            return res.status(400).json({ error: 'Faltan parámetros. Se requiere número, mensaje y nombre de imagen.' });
        }

        if (!state.isReady) {
            return res.status(503).json({ error: 'Cliente de WhatsApp aún no está listo.' });
        }

        try {
            const jid = `${number}@c.us`;
            console.log("JID:", jid);

            const imagePath = path.join(__dirname, '../images', imageName);
            const media = MessageMedia.fromFilePath(imagePath);

            await client.sendMessage(jid, message, { media });
            res.status(200).json({ status: 'Mensaje con imagen enviado correctamente' });
        } catch (error) {
            console.error('Error enviando el mensaje con imagen:', error);
            res.status(500).json({ error: 'Error enviando el mensaje con imagen' });
        }
    });
};
