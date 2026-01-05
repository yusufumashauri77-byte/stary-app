from flask import Flask, render_template, request, send_from_directory
from flask_socketio import SocketIO, emit, join_room
import os
from werkzeug.utils import secure_filename
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'stary-app-2026-secret'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

users = {}
messages = {'General': []}

ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'mp4', 'pdf', 'webm'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return {'error': 'no file'}, 400
    file = request.files['file']
    if file.filename == '' or not allowed_file(file.filename):
        return {'error': 'invalid'}, 400
    filename = secure_filename(file.filename)
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(path)
    return {'url': f'/static/uploads/{filename}'}

@app.route('/static/uploads/<filename>')
def uploaded(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@socketio.on('join')
def on_join(data):
    username = data.get('username', 'Anonymous')
    phone = data.get('phone', 'unknown')
    room = data.get('room', 'General')
    profile_pic = data.get('profile_pic', '/static/default-avatar.png')

    join_room(room)
    users[request.sid] = {'username': username, 'phone': phone, 'profile_pic': profile_pic, 'room': room}

    online_count = len([u for u in users.values() if u['room'] == room])
    emit('online_users', online_count, room=room)
    emit('message_history', messages.get(room, []), to=request.sid)

@socketio.on('send_message')
def handle_message(data):
    room = data['room']
    if room not in messages:
        messages[room] = []

    msg_data = {
        'username': data['username'],
        'phone': data['phone'],
        'message': data.get('message', ''),
        'file_url': data.get('file_url'),
        'profile_pic': data.get('profile_pic'),
        'time': datetime.now().strftime("%H:%M")
    }
    messages[room].append(msg_data)
    emit('new_message', msg_data, room=room)

@socketio.on('disconnect')
def on_disconnect():
    if request.sid in users:
        user = users.pop(request.sid)
        room = user['room']
        online_count = len([u for u in users.values() if u['room'] == room])
        emit('online_users', online_count, room=room)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5001, debug=True)