const sendMessageWithRetry = require('./utils/sendMessageWithRetry');

module.exports = (app, client, state) => {
    app.post('/send-message', async (req, res) => {
        const { number, message } = req.body;

        if (!number || !message) {
            return res.status(400).json({ error: 'Faltan parámetros. Se requiere número y mensaje.' });
        }

        if (!state.isReady) {
            return res.status(503).json({ error: 'Cliente de WhatsApp aún no está listo.' });
        }

        const jid = `${number}@c.us`;
        console.log("JID:", jid);

        const success = await sendMessageWithRetry(client, jid, message);
        if (success) {
            res.status(200).json({ status: 'Mensaje enviado correctamente' });
        } else {
            res.status(500).json({ error: 'Error enviando el mensaje' });
        }
    });
};