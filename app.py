from flask import Flask, request, jsonify, send_from_directory
from flask_jwt_extended import JWTManager, create_access_token
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
import mysql.connector
from datetime import datetime, date
import os

# ---------------------------------
# Configuración General
# ---------------------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = 'tu_clave_secreta'
app.config['JWT_SECRET_KEY'] = 'clave_secreta_para_jwt'
jwt = JWTManager(app)

# ✅ Permitir conexión con el frontend de Vercel
CORS(app, resources={r"/*": {"origins": "*"}})

# ---------------------------------
# Configuración Base De Datos
# ---------------------------------
DB_CONFIG = {
    'host': 'b8pc3slm7fgcnjecxus4-mysql.services.clever-cloud.com',
    'user': 'upkqktlavomcoxb6',
    'password': 'P1xHzrC2xEJnRYwkOBNP',
    'database': 'b8pc3slm7fgcnjecxus4'
}

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

# ---------------------------------
# Ruta de Verificación del Servicio
# ---------------------------------
@app.route('/status', methods=['GET'])
def status():
    return jsonify({
        "status": "ok",
        "message": "API HiperCerámica CK funcionando correctamente ✅",
        "version": "1.1",
        "timestamp": datetime.now().isoformat()
    }), 200

# ---------------------------------
# Inicio de Sesión
# ---------------------------------
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM empleados WHERE correo = %s", (data['correo'],))
    user = cursor.fetchone()
    db.close()

    if user and check_password_hash(user[4], data['contraseña']):
        access_token = create_access_token(identity=user[0])
        rol_id = user[7]
        rol = {1: "administrador", 2: "empleado", 3: "bodeguero"}.get(rol_id, "desconocido")

        return jsonify({
            "access_token": access_token,
            "nombre": user[1],
            "correo": user[3],
            "telefono": user[5],
            "rol_id": rol_id,
            "rol": rol,
            "redirect": "main.html"
        })

    return jsonify({"message": "Credenciales incorrectas"}), 401

# ---------------------------------
# Registro de Empleados
# ---------------------------------
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    required = ('nombre_apellido', 'cedula', 'correo', 'contraseña')
    if not data or not all(k in data for k in required):
        return jsonify({"message": "Faltan campos obligatorios"}), 400

    hashed = generate_password_hash(data['contraseña'])[:255]
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO empleados (nombre_apellido, cedula, correo, contraseña, telefono, direccion, rol_id, fecha_registro)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        data['nombre_apellido'], data['cedula'], data['correo'], hashed,
        data.get('telefono', ''), data.get('direccion', ''),
        data.get('rol_id', 2), datetime.now().date()
    ))
    db.commit()
    db.close()
    return jsonify({"message": "Empleado registrado"}), 201

# ---------------------------------
# Inventario
# ---------------------------------
@app.route('/api/inventario', methods=['POST'])
def agregar_producto():
    data = request.json
    campos = ('nombre', 'codigo', 'categoria', 'marca', 'proveedor', 'precio', 'stock', 'calidad')
    if not all(k in data for k in campos):
        return jsonify({"message": "Faltan campos del producto"}), 400

    stock = int(data['stock'])
    stock_minimo = 50
    estado_stock = 'Bajo' if stock < stock_minimo else 'Bueno'

    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO inventario 
        (nombre, codigo, categoria, marca, proveedor, precio, stock, stock_minimo, estado_stock, calidad, fecha_registro)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        data['nombre'], data['codigo'], data['categoria'], data['marca'],
        data['proveedor'], data['precio'], data['stock'], stock_minimo,
        estado_stock, data['calidad'], datetime.now()
    ))
    db.commit()
    db.close()
    return jsonify({"message": "Producto agregado exitosamente"}), 201


@app.route('/api/inventario', methods=['GET'])
def obtener_productos():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM inventario ORDER BY fecha_registro DESC")
    productos = cursor.fetchall()
    db.close()
    return jsonify(productos)

# ---------------------------------
# Dashboard / Reportes
# ---------------------------------

@app.route("/api/ventas/dia", methods=["GET"])
def ventas_dia():
    """Obtiene las ventas totales del día especificado o el actual"""
    try:
        fecha = request.args.get("fecha", date.today())
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT IFNULL(SUM(total), 0) AS total_dia
            FROM ventas
            WHERE DATE(fecha_venta) = %s
        """, (fecha,))
        resultado = cursor.fetchone()
        db.close()
        return jsonify({"total_dia": resultado["total_dia"]}), 200
    except Exception as e:
        print("❌ Error en /api/ventas/dia:", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/ventas/mes", methods=["GET"])
def ventas_mes():
    """Obtiene las ventas totales del mes y año indicados"""
    try:
        mes = request.args.get("mes", datetime.now().month)
        anio = request.args.get("anio", datetime.now().year)
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT IFNULL(SUM(total), 0) AS total_mes
            FROM ventas
            WHERE MONTH(fecha_venta) = %s AND YEAR(fecha_venta) = %s
        """, (mes, anio))
        resultado = cursor.fetchone()
        db.close()
        return jsonify({"total_mes": resultado["total_mes"]}), 200
    except Exception as e:
        print("❌ Error en /api/ventas/mes:", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/inventario/bajo", methods=["GET"])
def productos_bajo_inventario():
    """Devuelve los productos con stock menor al mínimo"""
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, nombre, codigo, stock, stock_minimo, estado_stock
            FROM inventario
            WHERE stock < stock_minimo
        """)
        productos = cursor.fetchall()
        db.close()
        return jsonify(productos), 200
    except Exception as e:
        print("❌ Error en /api/inventario/bajo:", e)
        return jsonify({"error": str(e)}), 500



# ---------------------------------
# Archivos estáticos
# ---------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VIEWS_DIR = os.path.join(BASE_DIR, 'views')
PUBLIC_DIR = os.path.join(BASE_DIR, 'public')

@app.route('/')
def home():
    return jsonify({
        "message": "Bienvenido a la API de HiperCerámica CK",
        "status": "running"
    })

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(VIEWS_DIR, filename)

@app.route('/views/<path:filename>')
def serve_views(filename):
    return send_from_directory(VIEWS_DIR, filename)

@app.route('/public/<path:filename>')
def serve_public(filename):
    return send_from_directory(PUBLIC_DIR, filename)

# ---------------------------------
# MAIN
# ---------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
