from flask import Flask, session
from flask_socketio import SocketIO, emit, join_room, leave_room
from datetime import timedelta
from config import SECRET_KEY
from utils.db import init_db, close_db
from routes import register_blueprints
from models.message import Message

app = Flask(__name__, template_folder='template', static_folder='static')
app.config.from_mapping(
    SECRET_KEY=SECRET_KEY,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=False,  # Set to True in production with HTTPS
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
)
app.config['SESSION_PERMANENT'] = True

# Initialize SocketIO for real-time chat
socketio = SocketIO(app, cors_allowed_origins="*", manage_session=False)

# Initialize database (creates tables if they don't exist)
with app.app_context():
    init_db()

register_blueprints(app)
app.teardown_appcontext(close_db)


@app.before_request
def before_request():
    """Ensure sessions stay permanent across all requests"""
    session.permanent = True
    app.permanent_session_lifetime = timedelta(days=7)


# WebSocket event handler for sending messages
@socketio.on('send_message')
def handle_send_message(data):
    sender_id = session.get('user_id')
    recipient_id = data.get('recipient_id')
    content = data.get('content', '').strip()

    if not sender_id or not recipient_id or not content:
        emit('error', {'message': 'Invalid message data'})
        return

    if sender_id == recipient_id:
        emit('error', {'message': 'Cannot message yourself'})
        return

    # Save message to database
    Message.send(sender_id, recipient_id, content)

    # Create room identifier (ensure consistent ordering)
    room = f"chat_{min(sender_id, recipient_id)}_{max(sender_id, recipient_id)}"

    # Emit to both users in the conversation
    emit('receive_message', {
        'sender_id': sender_id,
        'recipient_id': recipient_id,
        'content': content,
        'is_sent': True
    }, room=room)


@socketio.on('join_chat')
def handle_join_chat(data):
    user_id = session.get('user_id')
    recipient_id = data.get('recipient_id')

    if not user_id or not recipient_id:
        emit('error', {'message': 'Invalid chat room'})
        return

    # Create room identifier (ensure consistent ordering)
    room = f"chat_{min(user_id, recipient_id)}_{max(user_id, recipient_id)}"
    join_room(room)

    emit('status', {'message': f'User {user_id} joined the chat'}, room=room)


@socketio.on('leave_chat')
def handle_leave_chat(data):
    user_id = session.get('user_id')
    recipient_id = data.get('recipient_id')

    if not user_id or not recipient_id:
        return

    room = f"chat_{min(user_id, recipient_id)}_{max(user_id, recipient_id)}"
    leave_room(room)

    emit('status', {'message': f'User {user_id} left the chat'}, room=room)


if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)

