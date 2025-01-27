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
app.secret_key = str(uuid.uuid4())  # Needed to use sessions

# instantiate payload
payload = {
        "input": {
            "input": "",
            "chat_history": []
        },
        "config": {},
        "kwargs": {}
    }

def generate_session_id():
    return str(uuid.uuid4())

@app.route('/')
def home():
    # Generate a new session_id if not already in session
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())  # Generate a random session_id
        logging.debug(f"New session_id created: {session['session_id']}")
    else:
        logging.debug(f"Existing session_id: {session['session_id']}")

    # Clear the chat history whenever the home page is accessed
    payload['input']['chat_history'] = []
    
    banner_image_url = url_for('static', filename='images/banner.png')  # Example static image
    return render_template('index.html', banner_image_url=banner_image_url)
    # return render_template('index.html')

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
    user_message = request.form['message']
    api_url = os.getenv('API_URL')
    api_url_kg = os.getenv('API_URL_KG')
    headers = {'accept': 'application/json', 'Content-Type': 'application/json'}

    session_id = session.get('session_id', 'unknown')
    payload['input']['input'] = user_message
    payload['session_id'] = session_id

    try:
        # KG endpoint
        print("*" * 20)
        print("*** KG response ***")
        print("*" * 20)
        print(api_url_kg)
        print(payload)
        
        response_kg_raw = requests.post(api_url_kg, json=payload, headers=headers)
        response_json_kg = response_kg_raw.json()
        print(json.dumps(response_json_kg, indent=2))

        # Extract kg endpoint output
        response_kg = response_json_kg.get('output', {}).get('extra', {}).get('knowledge_graph', {})
        response_output = response_json_kg.get('output', {}).get('output', {})

        return jsonify({
            'response': response_output,
            'knowledge_graph': response_kg
        })
    except requests.exceptions.RequestException as e:
        logging.error(f"Request failed: {e}")
        return jsonify({'response': 'An error occurred while processing your request.'})

@app.route('/export_chat_history')
def export_chat_history():
    chat_history_json = json.dumps(payload['input']['chat_history'], indent=4)
    chat_history_bytes = BytesIO(chat_history_json.encode('utf-8'))
    chat_history_bytes.seek(0)

    return send_file(chat_history_bytes,
                     mimetype='application/json',
                     as_attachment=True,
                     download_name='chat_history.json')

@app.route('/clear_history', methods=['POST'])
def clear_history():
    # Clear the chat history in the payload
    payload['input']['chat_history'] = []
    return jsonify({'status': 'success', 'message': 'Chat history cleared.'})

if __name__ == '__main__':
    app.run(debug=True)