const { exec } = require('child_process');
const path = require('path');
const fs = require('fs');
const { MessageMedia } = require('whatsapp-web.js');
const sendMessageWithRetry = require('./utils/sendMessageWithRetry');

module.exports = (app, client, state) => {
    app.post('/generate-and-send-pdf', async (req, res) => {
        const { pos_name, number } = req.body;

        if (!pos_name || !number) {
            return res.status(400).json({ error: 'Faltan parámetros. Se requiere POS_NAME y número.' });
        }

        if (!state.isReady) {
            return res.status(503).json({ error: 'Cliente de WhatsApp aún no está listo.' });
        }

        exec(`python3 generate_pdf.py ${pos_name}`, async (error, stdout, stderr) => {
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
                const jid = `${number}@c.us`;
                console.log("Enviando PDF al número:", jid);

                await sendMessageWithRetry(client, jid, media);
                fs.unlinkSync(pdfPath); // Delete the PDF file after sending the message
                res.status(200).json({ status: 'PDF generado, enviado y eliminado correctamente' });
            } catch (sendError) {
                console.error('Error enviando el PDF:', sendError);
                res.status(500).json({ error: 'Error enviando el PDF' });
            }
        });
    });
};

