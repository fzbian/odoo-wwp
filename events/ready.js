module.exports = {
    name: "ready",
    async execute(client, state) {
        console.log('Cliente de WhatsApp conectado!');
        state.isReady = true;
        await new Promise(resolve => setTimeout(resolve, 10000));
        console.log('WhatsApp Web debería estar completamente cargado ahora.');
    },
};