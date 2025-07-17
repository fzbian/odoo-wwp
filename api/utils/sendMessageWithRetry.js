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

module.exports = async function sendMessageWithRetry(client, jid, message, retries = 3) {
    let attempt = 0;
    while (attempt < retries) {
        attempt++;
        console.log(`📤 Intento ${attempt}/${retries} - Enviando mensaje...`);
        
        try {
            // Intentar enviar el mensaje (puede fallar con error interno)
            await client.sendMessage(jid, message);
        } catch (error) {
            // Ignorar errores específicos de serialización que no afectan el envío
            if (!error.message.includes('serialize') && 
                !error.message.includes('getMessageModel')) {
                console.error(`❌ Error real enviando mensaje:`, error.message);
                
                // Solo reinicializar en casos específicos de desconexión
                if (error.message.includes('Session closed') || error.message.includes('Protocol error')) {
                    console.log('🔄 Reinicializando cliente...');
                    try {
                        await client.initialize();
                        await new Promise(resolve => setTimeout(resolve, 5000));
                    } catch (initError) {
                        console.error('❌ Error reinicializando cliente:', initError);
                    }
                }
                
                // Si es un error real y no el último intento, continuar
                if (attempt < retries) {
                    console.log(`⏳ Esperando 3 segundos antes del siguiente intento...`);
                    await new Promise(resolve => setTimeout(resolve, 3000));
                    continue;
                }
            }
        }
        
        // Siempre verificar si el mensaje fue enviado (independiente del error)
        console.log('🔍 Verificando si el mensaje fue enviado...');
        const isVerified = await verifyMessageSent(client, jid, message);
        
        if (isVerified) {
            console.log('✅ Mensaje confirmado como enviado correctamente');
            return true;
        } else {
            console.log(`⚠️ Mensaje no verificado en intento ${attempt}/${retries}`);
            
            // Si ya alcanzamos el máximo de intentos, salir
            if (attempt >= retries) {
                console.error('🚫 Máximo de intentos alcanzado, mensaje no enviado.');
                return false;
            }
            
            console.log(`⏳ Esperando 3 segundos antes del siguiente intento...`);
            await new Promise(resolve => setTimeout(resolve, 3000));
        }
    }
    return false;
};
