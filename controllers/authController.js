const bcrypt = require('bcrypt');
const jwt = require('jsonwebtoken');
const db = require('../config/db');

class AuthController {
    /**
     * Maneja el inicio de sesión del usuario
     * @param {string} email - Correo electrónico del usuario
     * @param {string} password - Contraseña del usuario
     * @param {boolean} remember - Si se debe recordar la sesión
     * @returns {Promise<Object>} - Resultado de la autenticación
     */
    async login(email, password, remember) {
        try {
            if (!email || !password) {
                return { success: false, message: 'Correo y contraseña son requeridos' };
            }

            const [rows] = await db.execute('SELECT * FROM empleados WHERE correo = ?', [email]);
            if (rows.length === 0) {
                return { success: false, message: 'Usuario no encontrado' };
            }
            
            const user = rows[0];
            const isPasswordValid = await bcrypt.compare(password, user.contraseña);
            if (!isPasswordValid) {
                return { success: false, message: 'Contraseña incorrecta' };
            }

            const token = this._generateToken(user, remember);
            return {
                success: true,
                token,
                user: { id: user.id, correo: user.correo, nombre_apellido: user.nombre_apellido }
            };
        } catch (error) {
            console.error('Error en el inicio de sesión:', error);
            return { success: false, message: 'Error en el servidor' };
        }
    }

    /**
     * Genera un token JWT de autenticación
     * @private
     * @param {Object} user - Información del usuario
     * @param {boolean} remember - Si se debe generar un token de larga duración
     * @returns {string} - Token JWT generado
     */
    _generateToken(user, remember) {
        const expiresIn = remember ? '30d' : '24h';
        return jwt.sign({ userId: user.id, correo: user.correo }, 'secreto', { expiresIn });
    }

    /**
     * Cierra la sesión del usuario
     * @returns {Object} - Resultado del cierre de sesión
     */
    logout() {
        return { success: true, message: 'Sesión cerrada exitosamente' };
    }

    /**
     * Solicita reinicio de contraseña
     * @param {string} email - Correo electrónico del usuario
     * @returns {Promise<Object>} - Resultado de la solicitud
     */
    async requestPasswordReset(email) {
        try {
            const [rows] = await db.execute('SELECT * FROM empleados WHERE correo = ?', [email]);
            if (rows.length === 0) {
                return { success: true, message: 'Si el correo existe, recibirás instrucciones para restablecer tu contraseña' };
            }
            return { success: true, message: 'Si el correo existe, recibirás instrucciones para restablecer tu contraseña' };
        } catch (error) {
            console.error('Error al solicitar restablecimiento de contraseña:', error);
            return { success: false, message: 'Error en el servidor' };
        }
    }
}

module.exports = AuthController;