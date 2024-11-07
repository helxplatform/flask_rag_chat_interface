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
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }
    # payload = {
    #     "input": {
    #         "input": user_message,
    #         "chat_history": []
    #     },
    #     "config": {},
    #     "kwargs": {}
    # }

    # Attach the session_id to the payload
    session_id = session.get('session_id', 'unknown')
    payload['input']['input'] = user_message
    payload['session_id'] = session_id  # Add session_id to payload

    print(payload)

    unique_url = f"{api_url}"
    # unique_url = f"{api_url}?_={int(time.time())}"

    logging.debug(f"Payload being sent to API: {payload}")

    try:
        response = requests.post(unique_url, json=payload, headers=headers)
        response.raise_for_status()  # Raise an HTTPError for bad responses

        logging.debug(f"Response received: {response.text}")

        # Check if the response content is JSON
        if response.headers.get('Content-Type') == 'application/json':
            response_json = response.json()
            bot_response = response_json.get('output', 'Sorry, I did not understand that.')
        else:
            print(f"Unexpected content type: {response.headers.get('Content-Type')}")
            logging.error(f"Unexpected content type: {response.headers.get('Content-Type')}")
            bot_response = 'Sorry, the response from the server was not in JSON format.'

        bot_response_hyperlinked = add_hyperlink(bot_response['output'])
        knowledge_graph = bot_response['extra']
        bot_response_formatted = format_response(bot_response_hyperlinked)  # Format response to replace newlines with <br>
        payload['input']['chat_history'].append([user_message, bot_response_formatted])
        print(payload)
    except requests.exceptions.HTTPError as http_err:
        logging.error(f"HTTP error occurred: {http_err}")
        bot_response = 'Sorry, there was an error processing your request.'
    except Exception as err:
        logging.error(f"Other error occurred: {err}")
        bot_response = 'Sorry, there was an error processing your request.'

    return jsonify({
        'response': bot_response_formatted,
        'extra': {
            'knowledge_graph': knowledge_graph
        }
    })

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