from flask import Flask, render_template, request, jsonify, send_from_directory
import os
from werkzeug.utils import secure_filename
from datetime import datetime
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'stary-app-2026-secret'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Data in-memory (itabaki hadi server i-restart)
messages = {'General': []}
online_users = set()  # tuna-store phone numbers tu

ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'mp4', 'pdf', 'webm', 'mp3'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'no file'}), 400
    file = request.files['file']
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({'error': 'invalid'}), 400
    filename = secure_filename(file.filename)
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(path)
    return jsonify({'url': f'/static/uploads/{filename}'})

@app.route('/static/uploads/<filename>')
def uploaded(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# API endpoints za polling
@app.route('/api/messages/<room>')
def get_messages(room):
    return jsonify(messages.get(room, []))

@app.route('/api/send', methods=['POST'])
def send_message():
    data = request.json
    room = data.get('room', 'General')
    if room not in messages:
        messages[room] = []

    msg_data = {
        'username': data['username'],
        'phone': data['phone'],
        'message': data.get('message', ''),
        'file_url': data.get('file_url'),
        'profile_pic': data.get('profile_pic', '/static/default-avatar.png'),
        'time': datetime.now().strftime("%H:%M")
    }
    messages[room].append(msg_data)
    return jsonify({'status': 'sent'})

@app.route('/api/online', methods=['POST'])
def update_online():
    data = request.json
    phone = data.get('phone')
    room = data.get('room', 'General')
    if phone:
        online_users.add(phone)
    return jsonify({'count': len([u for u in online_users if True])})

@app.route('/api/online_count/<room>')
def online_count(room):
    # Kwa kuwa hatuna room-specific tracking vizuri, tunarudisha total (unaweza kuboresha baadaye)
    return jsonify({'count': len(online_users)})

@app.route('/api/heartbeat', methods=['POST'])
def heartbeat():
    # Client atutumia heartbeat kila sekunde 10 ili tu-update online
    data = request.json
    phone = data.get('phone')
    if phone:
        online_users.add(phone)
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
