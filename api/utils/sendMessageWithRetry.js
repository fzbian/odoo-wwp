module.exports = async function sendMessageWithRetry(client, jid, message, retries = 3) {
    let attempt = 0;
    while (attempt < retries) {
        try {
            await client.sendMessage(jid, message);
            console.log('Mensaje enviado correctamente');
            return true; 
        } catch (error) {
            console.error(`Error enviando el mensaje (Intento ${attempt + 1}):`, error);
            if (error.message.includes('Session closed')) {
                console.log('Reinicializando cliente...');
                await client.initialize();
            }
            attempt++;
            if (attempt >= retries) {
                console.error('Máximo de intentos alcanzado, mensaje no enviado.');
                return false;
            }
            await new Promise(resolve => setTimeout(resolve, 3000)); 
        }
    }
};
