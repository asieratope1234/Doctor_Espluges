from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
from flask import Flask, render_template


app = Flask(__name__)
app.config['SECRET_KEY'] = 'tu-secreto'
socketio = SocketIO(app)

# Guardamos mensajes en memoria (para prueba, en producción usar base de datos)
mensajes = []

@app.route('/chat')
def chat():
    return render_template('chat.html')

@app.route('/')
def index():
    return render_template('chat.html')

@socketio.on('conectar')
def on_connect():
    # Cuando un cliente se conecta, le enviamos todo el historial
    emit('historial', mensajes)

@socketio.on('mensaje_nuevo')
def on_mensaje(data):
    # data = {'usuario': 'Asier', 'mensaje': 'Hola a todos'}
    mensajes.append(data)
    # Emitimos el mensaje a todos los clientes conectados (broadcast)
    emit('mensaje', data, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, debug=True)

