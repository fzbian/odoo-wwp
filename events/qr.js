const qrcode = require('qrcode-terminal');

module.exports = {
	name: "qr",
	execute(qr, client, state) {
		console.log('Escanea el código QR:');
        qrcode.generate(qr, { small: true });
	},
};