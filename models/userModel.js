const bcrypt = require('bcrypt');
const db = require('../config/db');

class UserModel {
    /**
     * Busca un usuario por su correo electrónico en la base de datos
     * @param {string} email - Correo electrónico a buscar
     * @returns {Promise<Object|null>} - Usuario encontrado o null
     */
    async findByEmail(email) {
        try {
            const [rows] = await db.execute('SELECT * FROM empleados WHERE correo = ?', [email]);
            return rows.length > 0 ? rows[0] : null;
        } catch (error) {
            console.error('Error al buscar usuario por correo:', error);
            return null;
        }
    }

    /**
     * Verifica si la contraseña es correcta para un usuario
     * @param {number} userId - ID del usuario
     * @param {string} password - Contraseña a verificar
     * @returns {Promise<boolean>} - True si la contraseña es correcta
     */
    async verifyPassword(userId, password) {
        try {
            const [rows] = await db.execute('SELECT contraseña FROM empleados WHERE id = ?', [userId]);
            if (rows.length === 0) return false;
            return await bcrypt.compare(password, rows[0].contraseña);
        } catch (error) {
            console.error('Error al verificar la contraseña:', error);
            return false;
        }
    }

    /**
     * Actualiza la contraseña de un usuario en la base de datos
     * @param {number} userId - ID del usuario
     * @param {string} newPassword - Nueva contraseña
     * @returns {Promise<boolean>} - True si la actualización fue exitosa
     */
    async updatePassword(userId, newPassword) {
        try {
            const hashedPassword = await bcrypt.hash(newPassword, 10);
            const [result] = await db.execute('UPDATE empleados SET contraseña = ? WHERE id = ?', [hashedPassword, userId]);
            return result.affectedRows > 0;
        } catch (error) {
            console.error('Error al actualizar la contraseña:', error);
            return false;
        }
    }
}

module.exports = UserModel;
