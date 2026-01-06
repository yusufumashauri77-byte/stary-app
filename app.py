from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit, join_room, leave_room
import os
from werkzeug.utils import secure_filename
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

users = {}  # sid: {'username':, 'phone':, 'profile_pic':, 'room':}
messages = {}  # room: [msgs]
groups = {'General': {'admin': None, 'members': []}}  # group: {'admin': phone, 'members': [phones]}

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'mp4', 'pdf', 'webm'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        file_url = f"/static/uploads/{filename}"
        return jsonify({'url': file_url})
    return jsonify({'error': 'File type not allowed'}), 400

@app.route('/static/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@socketio.on('join')
def on_join(data):
    username = data['username']
    phone = data['phone']
    room = data['room']
    profile_pic = data.get('profile_pic', '/static/default-avatar.png')

    join_room(room)
    sid = request.sid
    users[sid] = {'username': username, 'phone': phone, 'profile_pic': profile_pic, 'room': room}

    if room not in messages:
        messages[room] = []

    # If general, all can join
    if room == 'General':
        emit('status', {'msg': f'{username} ameingia {room}'}, room=room)

    # Check if in group members
    if room in groups and phone not in groups[room]['members'] and groups[room]['admin'] is not None:
        leave_room(room)
        emit('error', {'msg': 'You are not in this group'}, to=sid)
        return

    emit('user_joined', {'phone': phone, 'username': username, 'profile_pic': profile_pic}, room=room)
    emit('online_users', get_online_users(room), room=room)
    emit('message_history', messages[room], to=sid)

@socketio.on('send_message')
def handle_message(data):
    room = data['room']
    phone = data['phone']

    # Check if sender is in group
    if room in groups and phone not in groups[room]['members'] and groups[room]['admin'] is not None:
        emit('error', {'msg': 'You are not in this group'}, to=request.sid)
        return

    msg_data = {
        'username': data['username'],
        'phone': phone,
        'message': data['message'],
        'file_url': data.get('file_url'),
        'profile_pic': data.get('profile_pic'),
        'time': datetime.now().strftime("%H:%M")
    }
    messages.setdefault(room, []).append(msg_data)
    emit('new_message', msg_data, room=room)

@socketio.on('typing')
def typing(data):
    emit('user_typing', {'phone': data['phone']}, room=data['room'], include_self=False)

@socketio.on('create_group')
def create_group(data):
    group_name = data['name']
    creator = data['phone']
    members = data.get('members', []).split(',')  # comma separated phones
    if group_name in groups:
        emit('error', {'msg': 'Group exists'}, to=request.sid)
        return
    groups[group_name] = {'admin': creator, 'members': [creator] + [m.strip() for m in members if m.strip()]}
    emit('group_created', {'name': group_name, 'members': groups[group_name]['members']}, to=request.sid)
    # Notify members (optional)

@socketio.on('add_to_group')
def add_to_group(data):
    group = data['group']
    user = data['user']
    if group in groups and users[request.sid]['phone'] == groups[group]['admin']:
        if user not in groups[group]['members']:
            groups[group]['members'].append(user)
            emit('user_added', {'group': group, 'user': user}, room=group)
    else:
        emit('error', {'msg': 'Not admin'}, to=request.sid)

@socketio.on('remove_from_group')
def remove_from_group(data):
    group = data['group']
    user = data['user']
    if group in groups and users[request.sid]['phone'] == groups[group]['admin']:
        if user in groups[group]['members']:
            groups[group]['members'].remove(user)
            emit('user_removed', {'group': group, 'user': user}, room=group)
    else:
        emit('error', {'msg': 'Not admin'}, to=request.sid)

@socketio.on('disconnect')
def disconnect():
    if request.sid in users:
        user = users[request.sid]
        leave_room(user['room'])
        emit('user_left', {'phone': user['phone']}, room=user['room'])
        emit('online_users', get_online_users(user['room']), room=user['room'])
        del users[request.sid]

def get_online_users(room):
    return [v for v in users.values() if v['room'] == room]

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5001, debug=True)
