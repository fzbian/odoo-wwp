const sendMessageWithRetry = require('./utils/sendMessageWithRetry');

module.exports = (app, client, state) => {
    app.post('/send-message-group', async (req, res) => {
        const { group_name, message } = req.body;

        if (!group_name || !message) {
            return res.status(400).json({ error: 'Faltan parámetros. Se requiere nombre del grupo y mensaje.' });
        }

        if (!state.isReady) {
            return res.status(503).json({ error: 'Cliente de WhatsApp aún no está listo.' });
        }

        try {
            const chats = await client.getChats();
            const group = chats.find(chat => chat.isGroup && chat.name === group_name);
            if (!group) {
                return res.status(404).json({ error: 'Grupo no encontrado' });
            }

            const success = await sendMessageWithRetry(client, group.id._serialized, message);
            if (success) {
                res.status(200).json({ status: 'Mensaje enviado correctamente al grupo' });
            } else {
                res.status(500).json({ error: 'Error enviando el mensaje al grupo' });
            }
        } catch (error) {
            console.error('Error enviando el mensaje al grupo:', error);
            res.status(500).json({ error: 'Error enviando el mensaje al grupo' });
        }
    });
};