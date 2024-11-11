module.exports = {
    name: "disconnected",
    async execute(client, state, reason) {
        console.log('Cliente desconectado:', reason);
        state.isReady = false;
        await client.initialize();
    },
};