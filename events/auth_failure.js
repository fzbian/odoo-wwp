const fs = require('fs');

module.exports = {
    name: "auth_failure",
    execute(msg, client, state) {
        console.error('Error de autenticación:', msg);
        try {
            fs.unlinkSync('./auth_info/auth_info.json');
            console.log('Archivo de autenticación eliminado correctamente.');
        } catch (err) {
            console.error('Error al eliminar el archivo de autenticación:', err);
        }
    },
};
