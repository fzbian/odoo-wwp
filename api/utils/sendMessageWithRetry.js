async function verifyMessageSent(client, jid, messageText, timeWindow = 10000) {
    try {
        // Esperar un poco para que el mensaje aparezca en la conversación
        await new Promise(resolve => setTimeout(resolve, 2000));
        
        const chat = await client.getChatById(jid);
        const messages = await chat.fetchMessages({ limit: 10 });
        
        // Buscar el mensaje enviado en los últimos mensajes
        const currentTime = Date.now();
        const sentMessage = messages.find(msg => {
            const messageAge = currentTime - (msg.timestamp * 1000);
            return msg.fromMe && 
                   msg.body === messageText && 
                   messageAge <= timeWindow;
        });
        
        if (sentMessage) {
            console.log('✅ Mensaje verificado en la conversación');
            return true;
        } else {
            console.log('❌ Mensaje no encontrado en la conversación');
            return false;
        }
    } catch (error) {
        console.error('Error verificando mensaje en conversación:', error);
        return false;
    }
}

async function notifyAdmin(client, originalJid, originalMessage, error) {
    try {
        const adminJid = '573206359839@c.us';
        const notification = `� ALERTA: No se pudo enviar mensaje
        
📱 Destinatario: ${originalJid}
💬 Mensaje: "${originalMessage}"
❌ Error: ${error}
⏰ Hora: ${new Date().toLocaleString('es-CO')}`;
        
        await client.sendMessage(adminJid, notification);
        console.log('📨 Notificación enviada al administrador');
    } catch (notifyError) {
        console.error('❌ Error enviando notificación al administrador:', notifyError);
    }
}

module.exports = async function sendMessageWithRetry(client, jid, message) {
    try {
        console.log('📤 Enviando mensaje...');
        
        // Intentar enviar el mensaje
        await client.sendMessage(jid, message);
        
        // Verificar si el mensaje fue enviado
        console.log('� Verificando si el mensaje fue enviado...');
        const isVerified = await verifyMessageSent(client, jid, message);
        
        if (isVerified) {
            console.log('✅ Mensaje enviado y verificado correctamente');
            return true;
        } else {
            console.log('❌ Mensaje no verificado');
            await notifyAdmin(client, jid, message, 'Mensaje no verificado en la conversación');
            return false;
        }
        
    } catch (error) {
        // Ignorar errores específicos de serialización que no afectan el envío
        if (error.message.includes('serialize') || error.message.includes('getMessageModel')) {
            console.log('⚠️ Error de serialización ignorado, verificando mensaje...');
            
            // Verificar si el mensaje fue enviado a pesar del error
            const isVerified = await verifyMessageSent(client, jid, message);
            
            if (isVerified) {
                console.log('✅ Mensaje enviado correctamente (error de serialización ignorado)');
                return true;
            } else {
                console.log('❌ Mensaje no verificado tras error de serialización');
                await notifyAdmin(client, jid, message, 'Error de serialización y mensaje no verificado');
                return false;
            }
        } else {
            // Error real
            console.error('❌ Error real enviando mensaje:', error.message);
            await notifyAdmin(client, jid, message, error.message);
            return false;
        }
    }
};
