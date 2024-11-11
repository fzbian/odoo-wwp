const { exec } = require('child_process');
const path = require('path');
const fs = require('fs');
const { MessageMedia } = require('whatsapp-web.js');
const sendMessageWithRetry = require('./utils/sendMessageWithRetry');

module.exports = (app, client, state) => {
    app.post('/generate-and-send-pdf', async (req, res) => {
        const { pos_name, group_name } = req.body;

        if (!pos_name || !group_name) {
            return res.status(400).json({ error: 'Faltan parámetros. Se requiere POS_NAME y group_name.' });
        }

        exec(`python generate_pdf.py ${pos_name}`, async (error, stdout, stderr) => {
            if (error) {
                console.error(`Error ejecutando generate_pdf.py: ${error.message}`);
                return res.status(500).json({ error: 'Error generando el PDF' });
            }
            if (stderr) {
                console.error(`Error en generate_pdf.py: ${stderr}`);
                return res.status(500).json({ error: 'Error generando el PDF' });
            }

            const pdfFilename = stdout.trim();
            const pdfPath = path.join(__dirname, '..', pdfFilename);
            const media = MessageMedia.fromFilePath(pdfPath);

            try {
                const chats = await client.getChats();
                const group = chats.find(chat => chat.isGroup && chat.name === group_name);
                if (!group) {
                    return res.status(404).json({ error: 'Grupo no encontrado' });
                }

                await sendMessageWithRetry(client, group.id._serialized, media);
                fs.unlinkSync(pdfPath); // Delete the PDF file after sending the message
                res.status(200).json({ status: 'PDF generado, enviado y eliminado correctamente' });
            } catch (sendError) {
                console.error('Error enviando el PDF:', sendError);
                res.status(500).json({ error: 'Error enviando el PDF' });
            }
        });
    });
};