from flask import Flask, request, jsonify, send_from_directory, make_response
from flask_jwt_extended import JWTManager, create_access_token, jwt_required
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from datetime import datetime, date, time, timedelta, timezone
import os
import pytz
from fpdf import FPDF
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tu_clave_secreta'
app.config['JWT_SECRET_KEY'] = 'clave_secreta_para_jwt'
jwt = JWTManager(app)

# ---------------------------------
# Configuracion Base De Datos
# ---------------------------------
DB_CONFIG = {
    'host': 'b8pc3slm7fgcnjecxus4-mysql.services.clever-cloud.com',
    'user': 'upkqktlavomcoxb6',
    'password': 'P1xHzrC2xEJnRYwkOBNP',
    'database': 'b8pc3slm7fgcnjecxus4'
}

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)
db = get_db_connection()
cursor = db.cursor()
db.commit()
db.close()

# --------------------------
# Apartado Inicio De Sesion
# --------------------------
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
        if rol_id == 1:
            rol = "administrador"
        elif rol_id == 2:
            rol = "empleado"
        elif rol_id == 3:
            rol = "bodeguero"
        else:
            rol = "desconocido"
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

# ----------------------------------
# Apartado Registar Inicio De Sesion
# ----------------------------------
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

# ----------------------------------
# Todo Sobre El Apartado Inventario
# ----------------------------------
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

@app.route('/api/inventario/buscar', methods=['GET'])
def buscar_producto():
    termino = request.args.get('q', '')
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    query = "SELECT * FROM inventario WHERE nombre LIKE %s OR codigo LIKE %s"
    cursor.execute(query, (f"%{termino}%", f"%{termino}%"))
    productos = cursor.fetchall()
    db.close()
    return jsonify(productos)

@app.route('/api/inventario/<codigo>', methods=['PUT'])
def modificar_producto(codigo):
    data = request.json
    campos = ('nombre', 'categoria', 'marca', 'proveedor', 'precio', 'stock', 'calidad')
    if not all(k in data for k in campos):
        return jsonify({"message": "Faltan campos del producto"}), 400
    stock_raw = data.get('stock', 0)
    try:
        stock = int(stock_raw) if stock_raw not in (None, "") else 0
    except ValueError:
        stock = 0
    precio_raw = data.get('precio', 0)
    try:
        precio = float(precio_raw) if precio_raw not in (None, "") else 0.0
    except ValueError:
        precio = 0.0
    stock_minimo = 50
    estado_stock = 'Bajo' if stock < stock_minimo else 'Bueno'
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("""
        UPDATE inventario
        SET nombre=%s, categoria=%s, marca=%s, proveedor=%s, precio=%s,
            stock=%s, stock_minimo=%s, estado_stock=%s, calidad=%s
        WHERE codigo=%s
    """, (
        data['nombre'], data['categoria'], data['marca'], data['proveedor'],
        precio, stock, stock_minimo, estado_stock, data['calidad'], codigo
    ))
    db.commit()
    db.close()
    if cursor.rowcount == 0:
        return jsonify({"message": "Producto no encontrado"}), 404
    return jsonify({"message": "Producto modificado correctamente"}), 200

@app.route('/api/inventario/<codigo>', methods=['DELETE'])
def eliminar_producto(codigo):
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("DELETE FROM inventario WHERE codigo = %s", (codigo,))
    db.commit()
    db.close()
    if cursor.rowcount == 0:
        return jsonify({"message": "Producto no encontrado"}), 404
    return jsonify({"message": "Producto eliminado correctamente"}), 200

@app.route('/api/inventario/bajo', methods=['GET'])
def obtener_productos_stock_bajo():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM inventario WHERE stock <= stock_minimo ORDER BY fecha_registro DESC")
    productos_bajo = cursor.fetchall()
    db.close()
    return jsonify(productos_bajo)

# --------------------------------
# Todo Sobre El Apartado Empleados
# --------------------------------
@app.route('/api/empleados', methods=['GET'])
def get_empleados():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, nombre_apellido, cedula, correo, telefono, rol_id, fecha_registro 
        FROM empleados
    """)
    empleados = cursor.fetchall()
    db.close()
    for emp in empleados:
        emp['rol'] = 'Administrador' if emp['rol_id'] == 1 else 'Empleado'
        emp['estado'] = 'Activo'
        partes = emp['nombre_apellido'].split(" ", 1)
        emp['nombre'] = partes[0]
        emp['apellido'] = partes[1] if len(partes) > 1 else ""
    return jsonify(empleados)

@app.route('/api/empleados', methods=['POST'])
def crear_empleado():
    data = request.json
    required = ('nombre_apellido', 'correo', 'contraseña')
    if not data or not all(k in data for k in required):
        return jsonify({"message": "Faltan campos obligatorios"}), 400
    hashed = generate_password_hash(data['contraseña'])[:255]
    rol_id = data.get('rol_id', 2)
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO empleados (nombre_apellido, cedula, correo, contraseña, telefono, direccion, rol_id, fecha_registro)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        data['nombre_apellido'], data.get('cedula', ''),
        data['correo'], hashed,
        data.get('telefono', ''), data.get('direccion', ''),
        rol_id, datetime.now().date()
    ))
    db.commit()
    nuevo_id = cursor.lastrowid 
    db.close()
    return jsonify({"message": "Empleado registrado", "id": nuevo_id}), 201

@app.route('/api/empleados', methods=['GET'])
def listar_empleados():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id, nombre_apellido, cedula, correo, telefono, direccion, rol_id FROM empleados")
    empleados = cursor.fetchall()
    db.close()
    for emp in empleados:
        emp['rol'] = 'Administrador' if emp['rol_id'] == 1 else 'Empleado'
        partes = emp['nombre_apellido'].split(" ", 1)
        emp['nombre'] = partes[0]
        emp['apellido'] = partes[1] if len(partes) > 1 else ""
        emp['estado'] = 'Activo'
    return jsonify(empleados)

@app.route('/api/empleados/<int:id>', methods=['PUT'])
def modificar_empleado_api(id):
    data = request.json
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("""
        UPDATE empleados
        SET nombre_apellido=%s, cedula=%s, correo=%s, telefono=%s, direccion=%s, rol_id=%s
        WHERE id=%s
    """, (
        data.get('nombre_apellido'),
        data.get('cedula', ''),
        data.get('correo'),
        data.get('telefono', ''),
        data.get('direccion', ''),
        data.get('rol_id', 2),
        id
    ))
    db.commit()
    db.close()
    return jsonify({"message": "Empleado modificado"}), 200

@app.route('/api/empleados/<int:id>', methods=['DELETE'])
def eliminar_empleado_api(id):
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("DELETE FROM empleados WHERE id=%s", (id,))
    db.commit()
    db.close()
    return jsonify({"message": "Empleado eliminado"}), 200

# --------------------------------
# Todo Sobre El Apartado Clientes
# --------------------------------
@app.route('/api/clientes', methods=['POST'])
def crear_cliente():
    data = request.json
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO clientes (nombre_apellido, cedula, correo, telefono, direccion)
        VALUES (%s, %s, %s, %s, %s)
    """, (data['nombre_apellido'], data['cedula'], data['correo'], data['telefono'], data['direccion']))
    db.commit()
    cliente_id = cursor.lastrowid
    db.close()
    return jsonify({"message": "Cliente registrado", "cliente_id": cliente_id}), 201

@app.route('/api/clientes', methods=['GET'])
def listar_clientes():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM clientes ORDER BY fecha_registro DESC")
    clientes = cursor.fetchall()
    db.close()
    return jsonify(clientes)

# --------------------------------
# Todo Sobre El Apartado De Ventas
# --------------------------------
@app.route('/api/ventas', methods=['POST'])
def registrar_venta():
    data = request.json
    cliente_id = data['cliente_id']
    productos = data['productos']
    total = sum([p['cantidad'] * p['precio'] for p in productos])
    db = get_db_connection()
    cursor = db.cursor()
    cursor.execute("INSERT INTO ventas (cliente_id, total) VALUES (%s, %s)", (cliente_id, total))
    venta_id = cursor.lastrowid
    for p in productos:
        cursor.execute("""
            INSERT INTO detalle_venta (venta_id, producto, cantidad, precio_unitario, subtotal)
            VALUES (%s, %s, %s, %s, %s)
        """, (venta_id, p['nombre'], p['cantidad'], p['precio'], p['cantidad'] * p['precio']))
        cursor.execute("""
            UPDATE inventario
            SET stock = stock - %s
            WHERE nombre = %s
        """, (p['cantidad'], p['nombre']))
    db.commit()
    db.close()
    return jsonify({"message": "Venta registrada y stock actualizado", "venta_id": venta_id}), 201

@app.route('/api/ventas/dia', methods=['GET'])
def ventas_dia():
    hoy = datetime.now().date()
    inicio = datetime.combine(hoy, datetime.min.time())   
    fin = inicio + timedelta(days=1)                     
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    query = """
        SELECT v.id, c.nombre_apellido AS cliente, d.producto, d.cantidad, d.subtotal, v.fecha
        FROM ventas v
        JOIN clientes c ON v.cliente_id = c.id
        JOIN detalle_venta d ON v.id = d.venta_id
        WHERE v.fecha >= %s AND v.fecha < %s
        ORDER BY v.fecha DESC
    """
    cursor.execute(query, (inicio, fin))
    ventas = cursor.fetchall()
    for v in ventas:
        if isinstance(v["fecha"], datetime):
            v["fecha"] = v["fecha"].strftime("%d %b %Y %H:%M:%S") 
    db.close()
    return jsonify(ventas)

@app.route('/api/ventas/mes', methods=['GET'])
def ventas_mes():
    mes = int(request.args.get("mes", datetime.now().month))  
    año = int(request.args.get("anio", datetime.now().year))  
    inicio = datetime(año, mes, 1)
    if mes == 12:
        fin = datetime(año + 1, 1, 1)
    else:
        fin = datetime(año, mes + 1, 1)
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    query = """
        SELECT v.id, c.nombre_apellido AS cliente, d.producto, d.cantidad, d.subtotal, v.fecha
        FROM ventas v
        JOIN clientes c ON v.cliente_id = c.id
        JOIN detalle_venta d ON v.id = d.venta_id
        WHERE v.fecha >= %s AND v.fecha < %s
        ORDER BY v.fecha DESC
    """
    cursor.execute(query, (inicio, fin))
    ventas = cursor.fetchall()
    for v in ventas:
        if isinstance(v["fecha"], datetime):
            v["fecha"] = v["fecha"].strftime("%d %b %Y %H:%M:%S")
    db.close()
    return jsonify(ventas)

@app.route('/api/ventas/total-dia', methods=['GET'])
def total_ventas_dia():
    hoy = datetime.now().date()
    inicio = datetime.combine(hoy, datetime.min.time())
    fin = inicio + timedelta(days=1)

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    query = """
        SELECT COALESCE(SUM(d.subtotal), 0) AS total
        FROM ventas v
        JOIN detalle_venta d ON v.id = d.venta_id
        WHERE v.fecha >= %s AND v.fecha < %s
    """
    cursor.execute(query, (inicio, fin))
    resultado = cursor.fetchone()
    db.close()
    return jsonify(resultado)

@app.route('/api/ventas/total-mes', methods=['GET'])
def total_ventas_mes():
    mes = int(request.args.get("mes", datetime.now().month))
    año = int(request.args.get("anio", datetime.now().year))
    inicio = datetime(año, mes, 1)
    if mes == 12:
        fin = datetime(año + 1, 1, 1)
    else:
        fin = datetime(año, mes + 1, 1)
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    query = """
        SELECT COALESCE(SUM(d.subtotal), 0) AS total
        FROM ventas v
        JOIN detalle_venta d ON v.id = d.venta_id
        WHERE v.fecha >= %s AND v.fecha < %s
    """
    cursor.execute(query, (inicio, fin))
    resultado = cursor.fetchone()
    db.close()
    return jsonify(resultado)

# --------------------------------------
# Todo Sobre El Apartado Cotizaciones
# --------------------------------------
@app.route('/api/cotizaciones', methods=['POST'])
def registrar_cotizacion():
    data = request.json
    if not data.get('cliente_id') or not data.get('productos'):
        return jsonify({"message": "Faltan datos de cliente o productos"}), 400
    cliente_id = data['cliente_id']
    productos = data['productos']
    try:
        db = get_db_connection()
        cursor = db.cursor()
        total = sum([float(p['cantidad']) * float(p['precio']) for p in productos])
        cursor.execute(
            "INSERT INTO cotizaciones (cliente_id, total) VALUES (%s, %s)",
            (cliente_id, total)
        )
        cotizacion_id = cursor.lastrowid
        for p in productos:
            cursor.execute("""
                INSERT INTO detalle_cotizacion 
                (cotizacion_id, producto, cantidad, precio_unitario, subtotal)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                cotizacion_id,
                p['nombre'],
                int(p['cantidad']),
                float(p['precio']),
                float(p['cantidad']) * float(p['precio'])
            ))
        db.commit()
        return jsonify({"message": "Cotización registrada correctamente ", "cotizacion_id": cotizacion_id}), 201
    except Exception as e:
        db.rollback()
        return jsonify({"message": "Error al registrar cotización ", "error": str(e)}), 500
    finally:
        db.close()
        
# --------------------------------
# Todo Sobre El Apartado De Citas
# --------------------------------
@app.route("/api/citas", methods=["GET"])
def obtener_citas():
    """Obtiene todas las citas registradas en la BD."""
    db = None
    cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM citas ORDER BY fecha_cita DESC")
        citas = cursor.fetchall()
        for c in citas:
            for k, v in c.items():
                if isinstance(v, (datetime, date, time)):
                    c[k] = v.isoformat()
                elif isinstance(v, timedelta):
                    total_seconds = int(v.total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    seconds = total_seconds % 60
                    c[k] = f"{hours:02}:{minutes:02}:{seconds:02}"
        return jsonify(citas)
    except Exception as e:
        print(" Error al obtener citas:", e)
        return jsonify({"message": "Error al obtener citas", "error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()

@app.route("/api/citas", methods=["POST"])
def registrar_cita():
    """Registra una nueva cita en la BD."""
    data = request.json
    campos = ("nombre_cliente", "correo", "telefono", "fecha_cita", "hora_cita", "tipo_cita", "motivo")
    if not all(k in data for k in campos):
        return jsonify({"message": "Faltan campos obligatorios"}), 400
    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO citas (nombre_cliente, correo, telefono, fecha_cita, hora_cita, tipo_cita, motivo, fecha_registro)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            data["nombre_cliente"], data["correo"], data["telefono"],
            data["fecha_cita"], data["hora_cita"], data["tipo_cita"],
            data["motivo"], datetime.now()
        ))
        db.commit()
        return jsonify({"message": "Cita registrada correctamente"}), 201
    except Exception as e:
        db.rollback()
        return jsonify({"message": "Error al registrar cita", "error": str(e)}), 500
    finally:
        cursor.close()
        db.close()
        
@app.route("/api/citas/hoy", methods=["GET"])
def citas_hoy():
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        tz_col = pytz.timezone("America/Bogota")
        fecha_colombia = datetime.now(pytz.utc).astimezone(tz_col).date()
        cursor.execute("SELECT * FROM citas WHERE fecha_cita = %s", (fecha_colombia,))
        citas = cursor.fetchall()
        for c in citas:
            for k, v in c.items():
                if isinstance(v, timedelta):
                    total_seg = int(v.total_seconds())
                    horas = total_seg // 3600
                    minutos = (total_seg % 3600) // 60
                    c[k] = f"{horas:02d}:{minutos:02d}"
        return jsonify(citas)
    except Exception as e:
        print(f"ERROR /api/citas/hoy: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        db.close()

@app.route("/api/citas/manana", methods=["GET"])
def citas_manana():
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        tz_col = pytz.timezone("America/Bogota")
        fecha_colombia = datetime.now(pytz.utc).astimezone(tz_col).date()
        manana = fecha_colombia + timedelta(days=1)
        cursor.execute("SELECT * FROM citas WHERE fecha_cita = %s", (manana,))
        citas = cursor.fetchall()
        for c in citas:
            for k, v in c.items():
                if isinstance(v, timedelta):
                    total_seg = int(v.total_seconds())
                    horas = total_seg // 3600
                    minutos = (total_seg % 3600) // 60
                    c[k] = f"{horas:02d}:{minutos:02d}"
        return jsonify(citas)
    except Exception as e:
        print(f"ERROR /api/citas/manana: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        db.close()
        
@app.route("/api/citas/confirmar", methods=["POST"])
def confirmar_cita():
    data = request.json
    correo = data.get("correo")
    nombre = data.get("nombre")
    fecha = data.get("fecha")
    hora = data.get("hora")
    tipo = data.get("tipo")
    if not correo or not nombre:
        return jsonify({"error": "Datos incompletos"}), 400
    try:
        remitente = "delahozmaicol187@gmail.com"
        contraseña = "llmg cyld tjti lzjz"
        asunto = "Confirmación de Cita - Cerámicas UK"
        cuerpo = f"""
        <h2>Hola {nombre} </h2>
        <p>Te confirmamos tu cita para <b>{fecha}</b> a las <b>{hora}</b> ({tipo}).</p>
        <p>Gracias por confiar en <b>Cerámicas UK</b>.</p>
        """
        msg = MIMEMultipart()
        msg["From"] = remitente
        msg["To"] = correo
        msg["Subject"] = asunto
        msg.attach(MIMEText(cuerpo, "html"))
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(remitente, contraseña)
            server.send_message(msg)
        return jsonify({"mensaje": "Correo de confirmación enviado correctamente"})
    except Exception as e:
        print("ERROR AL ENVIAR CORREO:", str(e))
        return jsonify({"error": str(e)}), 500
    
# --------------------------------
# Todo Sobre FiltroReportes
# --------------------------------
@app.route("/generar_reporte", methods=["POST"])
def generar_reporte():
    tipo = request.form.get("tipo")
    mes = request.form.get("mes")
    anio = request.form.get("anio")
    calidad = request.form.get("calidad")

    if not tipo or not mes or not anio:
        return {"error": "Faltan parámetros"}, 400

    conexion = mysql.connector.connect(**DB_CONFIG)
    cursor = conexion.cursor(dictionary=True)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    titulo = f"Reporte de {tipo.capitalize()} ({mes}/{anio})"
    pdf.cell(0, 10, titulo.encode("latin-1", "replace").decode("latin-1"), ln=True, align="C")
    pdf.ln(10)
    pdf.set_font("Arial", "", 12)

    try:
        if tipo == "inventario":
            query = "SELECT nombre, categoria, marca, proveedor, precio, stock, calidad FROM inventario"
            params = []
            if calidad and calidad.lower() != "todas":
                query += " WHERE calidad = %s"
                params.append(calidad)

            cursor.execute(query, params)
            datos = cursor.fetchall()

            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 10, "Reporte de Inventario".encode("latin-1", "replace").decode("latin-1"), ln=True)
            pdf.ln(5)

            if not datos:
                pdf.set_font("Arial", "", 11)
                pdf.cell(0, 10, "No hay productos registrados para esta calidad.".encode("latin-1", "replace").decode("latin-1"), ln=True)
            else:
                pdf.set_fill_color(0, 0, 0)      
                pdf.set_text_color(255, 255, 255) 
                pdf.set_font("Arial", "B", 10)

                headers = ["Nombre", "Categoría", "Marca", "Proveedor", "Precio", "Stock", "Calidad"]
                col_widths = [40, 25, 25, 30, 25, 20, 25]

                for i, header in enumerate(headers):
                    pdf.cell(col_widths[i], 10, header.encode("latin-1", "replace").decode("latin-1"), border=1, align="C", fill=True)
                pdf.ln(10)
                pdf.set_font("Arial", "", 9)
                pdf.set_text_color(0, 0, 0)
                fill = False

                for row in datos:
                    pdf.set_fill_color(245, 245, 245) if fill else pdf.set_fill_color(255, 255, 255)
                    fill = not fill

                    fila = [
                        str(row["nombre"]),
                        str(row["categoria"]),
                        str(row["marca"]),
                        str(row["proveedor"]),
                        f"${row['precio']:,.0f}",
                        str(row["stock"]),
                        str(row["calidad"]),
                    ]

                    for i, valor in enumerate(fila):
                        pdf.cell(col_widths[i], 8, valor.encode("latin-1", "replace").decode("latin-1"), border=1, align="C", fill=True)
                    pdf.ln(8)

        elif tipo == "ventas":
            query = """
            SELECT c.nombre_apellido AS cliente, d.producto, d.cantidad, d.subtotal, v.fecha
            FROM ventas v
            JOIN clientes c ON v.cliente_id = c.id
            JOIN detalle_venta d ON v.id = d.venta_id
            WHERE MONTH(v.fecha) = %s AND YEAR(v.fecha) = %s
            ORDER BY v.fecha DESC
            """
            cursor.execute(query, (mes, anio))
            datos = cursor.fetchall()

            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 10, "Reporte de Ventas del Mes".encode("latin-1", "replace").decode("latin-1"), ln=True)
            pdf.ln(5)

            if not datos:
                pdf.set_font("Arial", "", 11)
                pdf.cell(0, 10, "No se registraron ventas en este mes.".encode("latin-1", "replace").decode("latin-1"), ln=True)
            else:
                pdf.set_fill_color(0, 0, 0)
                pdf.set_text_color(255, 255, 255)
                pdf.set_font("Arial", "B", 10)

                headers = ["Cliente", "Producto", "Cantidad", "Total", "Fecha"]
                col_widths = [45, 55, 25, 30, 35]

                for i, header in enumerate(headers):
                    pdf.cell(col_widths[i], 10, header.encode("latin-1", "replace").decode("latin-1"), border=1, align="C", fill=True)
                pdf.ln(10)

                pdf.set_font("Arial", "", 9)
                pdf.set_text_color(0, 0, 0)
                fill = False
                total_mensual = 0

                for row in datos:
                    pdf.set_fill_color(245, 245, 245) if fill else pdf.set_fill_color(255, 255, 255)
                    fill = not fill

                    fecha_str = row["fecha"].strftime("%d %b %Y %H:%M:%S")
                    total_mensual += float(row["subtotal"])

                    fila = [
                        str(row["cliente"]),
                        str(row["producto"]),
                        str(row["cantidad"]),
                        f"${row['subtotal']:,.0f}",
                        fecha_str,
                    ]

                    for i, valor in enumerate(fila):
                        pdf.cell(col_widths[i], 8, valor.encode("latin-1", "replace").decode("latin-1"), border=1, align="C", fill=True)
                    pdf.ln(8)

                pdf.ln(5)
                pdf.set_font("Arial", "B", 11)
                total_texto = f"Total mensual: ${total_mensual:,.0f}"
                pdf.cell(0, 10, total_texto.encode("latin-1", "replace").decode("latin-1"), ln=True, align="R")

        else:
            return {"error": "Tipo de reporte no válido"}, 400

        output_dir = os.path.join(os.getcwd(), "reports")
        os.makedirs(output_dir, exist_ok=True)
        nombre_archivo = os.path.join(output_dir, f"reporte_{tipo}_{mes}_{anio}.pdf")
        pdf.output(nombre_archivo)

        with open(nombre_archivo, "rb") as f:
            response = make_response(f.read())
        response.headers["Content-Type"] = "application/pdf"
        response.headers["Content-Disposition"] = f"inline; filename=reporte_{tipo}_{mes}_{anio}.pdf"
        return response

    except Exception as e:
        print("Error generando reporte:", e)
        return {"error": str(e)}, 500

    finally:
        cursor.close()
        conexion.close()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VIEWS_DIR = os.path.join(BASE_DIR, 'views')
PUBLIC_DIR = os.path.join(BASE_DIR, 'public')

@app.route('/')
def home():
    return send_from_directory(VIEWS_DIR, 'login.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(VIEWS_DIR, filename)

@app.route('/views/<path:filename>')
def serve_views(filename):
    return send_from_directory(VIEWS_DIR, filename)

@app.route('/public/<path:filename>')
def serve_public(filename):
    return send_from_directory(PUBLIC_DIR, filename)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

