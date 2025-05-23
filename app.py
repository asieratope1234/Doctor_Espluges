import os
import json
import uuid
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'clave_secreta'  # ¡Cámbiala en producción!

# Archivos de datos
USUARIOS_FILE = 'usuarios.json'
EVENTOS_FILE = 'eventos.json'
GRUPOS_FILE = 'grupos.json'
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Crear carpeta de uploads si no existe
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Cargar y guardar usuarios
def cargar_usuarios():
    if os.path.exists(USUARIOS_FILE):
        with open(USUARIOS_FILE, 'r') as archivo:
            return json.load(archivo)
    return {}

def guardar_usuarios(usuarios):
    with open(USUARIOS_FILE, 'w') as archivo:
        json.dump(usuarios, archivo, indent=4)

# Cargar y guardar eventos
def cargar_eventos():
    if os.path.exists(EVENTOS_FILE):
        with open(EVENTOS_FILE, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def guardar_eventos(eventos):
    print(f"Guardando eventos: {eventos}")  # Debug
    with open(EVENTOS_FILE, 'w') as f:
        json.dump(eventos, f, indent=4)

# Cargar y guardar grupos
def cargar_grupos():
    if os.path.exists(GRUPOS_FILE):
        with open(GRUPOS_FILE, 'r') as archivo:
            try:
                return json.load(archivo)
            except json.JSONDecodeError:
                return []
    return []

def guardar_grupos(grupos):
    with open(GRUPOS_FILE, 'w') as archivo:
        json.dump(grupos, archivo, indent=4)

# Inicializar datos
usuarios = cargar_usuarios()
chats_grupos = {}  # Diccionario para almacenar mensajes por grupo

@app.route('/')
def calendario():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', usuario=session['usuario'])

@app.route('/eventos')
def obtener_eventos():
    """Obtener todos los eventos en formato JSON para FullCalendar"""
    if 'usuario' not in session:
        return jsonify([]), 401

    eventos = cargar_eventos()
    print(f"Eventos cargados para {session['usuario']}: {eventos}")  # Debug

    # Filtrar solo eventos del usuario actual
    eventos_usuario = [evento for evento in eventos
                      if evento.get('extendedProps', {}).get('usuario') == session['usuario']]

    return jsonify(eventos_usuario)

@app.route('/añadir_evento', methods=['POST'])
def añadir_evento():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    titulo = request.form.get('titulo')
    fecha = request.form.get('fecha')
    color = request.form.get('color')
    descripcion = request.form.get('descripcion', '')

    if not (titulo and fecha and color):
        return redirect(url_for('calendario'))

    eventos = cargar_eventos()

    nuevo_evento = {
        'id': str(uuid.uuid4()),
        'title': titulo,
        'start': fecha,
        'color': color,
        'extendedProps': {
            'descripcion': descripcion,
            'usuario': session['usuario']
        }
    }

    eventos.append(nuevo_evento)
    guardar_eventos(eventos)
    print(f"Evento añadido: {nuevo_evento}")  # Debug
    return redirect(url_for('calendario'))

@app.route('/eliminar_evento', methods=['POST'])
def eliminar_evento():
    if 'usuario' not in session:
        return jsonify({"error": "No autenticado"}), 403

    evento_id = request.form.get('id')
    print(f"ID a eliminar: {evento_id}")

    if not evento_id or evento_id == "undefined":
        return jsonify({"error": "ID no proporcionado o inválido"}), 400

    eventos = cargar_eventos()

    # Solo eliminar eventos del usuario actual (por seguridad)
    usuario_actual = session['usuario']
    eventos_filtrados = []

    for ev in eventos:
        # Si el evento no es del usuario actual o no tiene el ID a eliminar, lo mantenemos
        if not (ev.get('id') == evento_id and ev.get('extendedProps', {}).get('usuario') == usuario_actual):
            eventos_filtrados.append(ev)

    guardar_eventos(eventos_filtrados)
    return jsonify({"success": True})

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        usuario = request.form['usuario']
        clave = request.form['clave']
        if usuario in usuarios and check_password_hash(usuarios[usuario], clave):
            session['usuario'] = usuario
            return redirect(url_for('calendario'))
        else:
            error = 'Usuario o contraseña incorrectos.'
    return render_template('login.html', error=error)

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    error = None
    if request.method == 'POST':
        usuario = request.form['usuario']
        clave = request.form['clave']
        if usuario in usuarios:
            error = 'El usuario ya existe.'
        else:
            usuarios[usuario] = generate_password_hash(clave)
            guardar_usuarios(usuarios)
            return redirect(url_for('login'))
    return render_template('registro.html', error=error)

# Guardamos los mensajes en memoria (para producción usa base de datos)
chat_messages = []

@app.route('/chat')
def chat():
    if 'usuario' not in session:
        return "No estás logueado", 401
    return render_template('chat.html', username=session['usuario'])

@app.route('/chat/messages', methods=['GET', 'POST'])
def chat_messages_api():
    if 'usuario' not in session:
        return jsonify({'error': 'No autenticado'}), 401

    if request.method == 'POST':
        data = request.json
        mensaje = data.get('mensaje', '').strip()
        if mensaje == '':
            return jsonify({'error': 'Mensaje vacío'}), 400

        chat_messages.append({
            'usuario': session['usuario'],
            'mensaje': mensaje,
            'hora': datetime.now().strftime('%H:%M:%S')
        })
        return jsonify({'success': True})

    # GET devuelve todos los mensajes
    return jsonify(chat_messages)

@app.route('/grupos', methods=['GET', 'POST'])
def gestion_grupos():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        nombre_grupo = request.form.get('nombre_grupo', '').strip()
        miembros_seleccionados = request.form.getlist('miembros')

        if nombre_grupo:
            grupos = cargar_grupos()

            # Añadir automáticamente al usuario que crea el grupo
            miembros = [session['usuario']]

            # Añadir otros miembros seleccionados (evitar duplicados)
            for miembro in miembros_seleccionados:
                if miembro not in miembros:
                    miembros.append(miembro)

            # Verificar que el grupo no existe ya
            if not any(g['nombre'] == nombre_grupo for g in grupos):
                nuevo_grupo = {
                    'nombre': nombre_grupo,
                    'miembros': miembros,
                    'creador': session['usuario'],
                    'imagen': None,
                    'fecha_creacion': datetime.now().isoformat()
                }
                grupos.append(nuevo_grupo)
                guardar_grupos(grupos)
                return redirect(url_for('gestion_grupos'))
            else:
                error = 'Ya existe un grupo con ese nombre'
                usuarios_existentes = [u for u in usuarios.keys() if u != session['usuario']]
                return render_template('groups.html', grupos=grupos, usuarios=usuarios_existentes, error=error)

    # GET - Recargar grupos desde archivo
    grupos = cargar_grupos()
    usuarios_existentes = [u for u in usuarios.keys() if u != session['usuario']]
    return render_template('groups.html', grupos=grupos, usuarios=usuarios_existentes)

@app.route('/grupo/<nombre_grupo>/editar', methods=['GET', 'POST'])
def editar_grupo(nombre_grupo):
    if 'usuario' not in session:
        return redirect(url_for('login'))

    grupos_actualizados = cargar_grupos()
    grupo = next((g for g in grupos_actualizados if g['nombre'] == nombre_grupo), None)

    if not grupo:
        return f'Grupo "{nombre_grupo}" no encontrado', 404

    # Solo el creador puede editar el grupo
    if grupo.get('creador') != session['usuario']:
        return 'Solo el creador del grupo puede editarlo', 403

    if request.method == 'POST':
        accion = request.form.get('accion')

        if accion == 'eliminar_miembro':
            miembro_a_eliminar = request.form.get('miembro')
            if miembro_a_eliminar != session['usuario'] and miembro_a_eliminar in grupo['miembros']:
                grupo['miembros'].remove(miembro_a_eliminar)

        elif accion == 'añadir_miembros':
            nuevos_miembros = request.form.getlist('nuevos_miembros')
            for miembro in nuevos_miembros:
                if miembro not in grupo['miembros']:
                    grupo['miembros'].append(miembro)

        elif accion == 'subir_imagen':
            if 'imagen' in request.files:
                file = request.files['imagen']
                if file and file.filename != '' and allowed_file(file.filename):
                    filename = f"{nombre_grupo}_{uuid.uuid4().hex}.{file.filename.rsplit('.', 1)[1].lower()}"
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    grupo['imagen'] = filename

        # Actualizar grupo en la lista
        for i, g in enumerate(grupos_actualizados):
            if g['nombre'] == nombre_grupo:
                grupos_actualizados[i] = grupo
                break

        guardar_grupos(grupos_actualizados)
        return redirect(url_for('editar_grupo', nombre_grupo=nombre_grupo))

    # GET - mostrar formulario de edición
    usuarios_disponibles = [u for u in usuarios.keys() if u not in grupo['miembros']]
    return render_template('editar_grupo.html', grupo=grupo, usuarios_disponibles=usuarios_disponibles)

@app.route('/grupo/<nombre_grupo>/eliminar', methods=['POST'])
def eliminar_grupo(nombre_grupo):
    if 'usuario' not in session:
        return redirect(url_for('login'))

    grupos_actualizados = cargar_grupos()
    grupo = next((g for g in grupos_actualizados if g['nombre'] == nombre_grupo), None)

    if not grupo:
        return jsonify({'error': 'Grupo no encontrado'}), 404

    # Solo el creador puede eliminar el grupo
    if grupo.get('creador') != session['usuario']:
        return jsonify({'error': 'Solo el creador puede eliminar el grupo'}), 403

    # Eliminar imagen si existe
    if grupo.get('imagen'):
        imagen_path = os.path.join(app.config['UPLOAD_FOLDER'], grupo['imagen'])
        if os.path.exists(imagen_path):
            os.remove(imagen_path)

    # Eliminar grupo de la lista
    grupos_actualizados = [g for g in grupos_actualizados if g['nombre'] != nombre_grupo]
    guardar_grupos(grupos_actualizados)

    # Eliminar mensajes del chat del grupo
    if nombre_grupo in chats_grupos:
        del chats_grupos[nombre_grupo]

    return jsonify({'success': True})

@app.route('/grupo/<nombre_grupo>/', methods=['GET', 'POST'], strict_slashes=False)
def chat_grupo(nombre_grupo):
    if 'usuario' not in session:
        return redirect(url_for('login'))

    grupos_actualizados = cargar_grupos()
    grupo = next((g for g in grupos_actualizados if g['nombre'] == nombre_grupo), None)

    if not grupo:
        return f'Grupo "{nombre_grupo}" no encontrado', 404

    # Verificar que el usuario actual es miembro del grupo
    if session['usuario'] not in grupo['miembros']:
        return 'No tienes permisos para acceder a este grupo', 403

    if request.method == 'POST':
        mensaje = request.form.get('mensaje', '').strip()
        usuario = session['usuario']
        if mensaje:
            chats_grupos.setdefault(nombre_grupo, []).append({
                'usuario': usuario,
                'mensaje': mensaje,
                'hora': datetime.now().strftime('%H:%M:%S')
            })
        return redirect(url_for('chat_grupo', nombre_grupo=nombre_grupo))

    mensajes = chats_grupos.get(nombre_grupo, [])
    return render_template('chat_grupo.html', grupo=grupo, mensajes=mensajes, session=session)

@app.route('/logout')
def logout():
    session.pop('usuario', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
