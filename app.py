from flask import Flask, render_template, request, jsonify, url_for, send_file, session
import requests
import logging
import time
import re
import os
import json
import uuid
from io import BytesIO



app = Flask(__name__)
logging.basicConfig(level=logging.WARNING)
app.secret_key = os.getenv('FLASK_SECRET_KEY', str(uuid.uuid4()))  # Use environment variable for production
logging.basicConfig(level=logging.WARNING)

# Dictionary to store user sessions, each containing their chat history
user_sessions = {}

def generate_session_id():
    return str(uuid.uuid4())

def get_user_session(session_id):
    """Retrieve or create a user session based on session_id."""
    if session_id not in user_sessions:
        user_sessions[session_id] = {
            'chat_history': []
        }
    return user_sessions[session_id]

def create_payload(user_input):
    return {
        "input": {
            "input": user_input,
            "chat_history": session.get('chat_history', [])
        },
        "config": {},
        "kwargs": {},
        "session_id": session.get('session_id')
    }

@app.route('/')
def home():
    # Initialize or retrieve the user's session
    if 'session_id' not in session:
        session_id = generate_session_id()
        session['session_id'] = session_id
        get_user_session(session_id)  # Initialize new session
        logging.debug(f"New session created: {session_id}")
    else:
        session_id = session['session_id']
        logging.debug(f"Existing session: {session_id}")

    banner_image_url = url_for('static', filename='images/banner.png')
    return render_template('index.html', banner_image_url=banner_image_url)



def add_hyperlink(text):
    # Regex to find standalone phs ID (e.g., phs123456) not part of a URL
    phs_pattern = r'\b(phs\d{4,})\b(?![^<]*<\/a>)'
    phs_replacement = r'<a href="https://www.ncbi.nlm.nih.gov/projects/gap/cgi-bin/study.cgi?study_id=\1" target="_blank">\1</a>'

    # Regex to find URLs
    url_pattern = r'(https?://[^\s]+)'
    url_replacement = r'<a href="\1">\1</a>'

    # First, replace URLs with hyperlinks
    text = re.sub(url_pattern, url_replacement, text)

    # Then, replace standalone phs IDs with hyperlinks
    text = re.sub(phs_pattern, phs_replacement, text, flags=re.IGNORECASE)

    return text

def format_response(text):
    # Replace newlines with <br> tags
    text = text.replace('**', '')
    return text.replace('\n', '<br>')


@app.route('/get_response', methods=['POST'])
def get_response():
    session_id = session.get('session_id')
    if not session_id:
        return jsonify({'response': 'Session not found. Please refresh the page.'}), 400

    user_session = get_user_session(session_id)
    chat_history = user_session['chat_history']


    user_message = request.form['message']
    api_url = os.getenv('API_URL')
    headers = {'accept': 'application/json', 'Content-Type': 'application/json'}

    # Build the payload with the user's specific chat history
    payload = {
        "input": {
            "input": user_message,
            "chat_history": chat_history.copy()  # Send a copy of the current history
        },
        "config": {},
        "kwargs": {},
        "session_id": session_id
    }

    try:
        # KG endpoint
        logging.debug("*" * 20)
        logging.debug("*** KG response ***")
        logging.debug("*" * 20)
        logging.info(payload)
        
        response_kg_raw = requests.post(api_url, json=payload, headers=headers)
        response_json_kg = response_kg_raw.json()
        print(json.dumps(response_json_kg, indent=2))

        # Extract kg endpoint output
        response_kg = response_json_kg.get('output', {}).get('extra', {}).get('knowledge_graph', {})
        response_output = response_json_kg.get('output', {}).get('output', {})
        response_output = add_hyperlink(format_response(response_output))
        # Update the user's chat history in their session
        chat_history.append([user_message, response_output])
        logging.debug(f"Updated chat history for session {session_id}: {chat_history}")

        return jsonify({
            'response': response_output,
            'knowledge_graph': response_kg
        })
    except requests.exceptions.RequestException as e:
        logging.error(f"Request failed: {e}")
        return jsonify({'response': 'An error occurred while processing your request.'})


@app.route('/export_chat_history')
def export_chat_history():
    session_id = session.get('session_id')
    if not session_id or session_id not in user_sessions:
        return jsonify({'error': 'No chat history found.'}), 404

    chat_history = user_sessions[session_id]['chat_history']
    chat_json = json.dumps(chat_history, indent=4)
    bytes_io = BytesIO(chat_json.encode('utf-8'))
    bytes_io.seek(0)

    return send_file(bytes_io,
                     mimetype='application/json',
                     as_attachment=True,
                     download_name='chat_history.json')

@app.route('/clear_history', methods=['POST'])
def clear_history():
    session_id = session.get('session_id')
    if session_id and session_id in user_sessions:
        user_sessions[session_id]['chat_history'] = []
    return jsonify({'status': 'success', 'message': 'Chat history cleared.'})


if __name__ == '__main__':
    app.run(debug=True)