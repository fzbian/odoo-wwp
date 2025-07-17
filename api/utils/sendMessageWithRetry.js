module.exports = async function sendMessageWithRetry(client, jid, message) {
    try {
        await client.sendMessage(jid, message);
        console.log('✅ Mensaje enviado');
        return true;
    } catch (error) {
        console.error('❌ Error enviando mensaje:', error.message);
        return false;
    }
};
