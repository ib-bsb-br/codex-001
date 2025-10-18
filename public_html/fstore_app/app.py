import os
import re
import datetime
from flask import Flask, request, jsonify, send_from_directory, render_template, abort, url_for

app = Flask(__name__)
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
CLIENT_SCRIPT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'fs_client.py')

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

def _reject_name(filename):
    """Rejects invalid filenames."""
    return not filename or '..' in filename or '/' in filename or '\\' in filename

def _get_unique_filename(filename):
    """Generates a unique filename by appending a number if it already exists."""
    if not os.path.exists(os.path.join(DATA_DIR, filename)):
        return filename

    name, ext = os.path.splitext(filename)
    i = 1
    while True:
        new_name = f"{name}_{i}{ext}"
        if not os.path.exists(os.path.join(DATA_DIR, new_name)):
            return new_name
        i += 1

def _files_list():
    """Returns a sorted list of files with metadata."""
    files = []
    for name in sorted(os.listdir(DATA_DIR)):
        path = os.path.join(DATA_DIR, name)
        if os.path.isfile(path):
            mod_time = os.path.getmtime(path)
            files.append({
                'name': name,
                'mod_time': mod_time,
                'mod_time_str': datetime.datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M:%S')
            })
    return files

@app.route('/')
def index():
    return render_template('overview.html', files=_files_list())

@app.route('/list')
def list_files_api():
    return jsonify(_files_list())

@app.route('/f/<path:fn>')
def download_file(fn):
    if _reject_name(fn):
        abort(400)
    return send_from_directory(DATA_DIR, fn, as_attachment=True)

@app.route('/e/<path:fn>')
def edit_note(fn):
    if _reject_name(fn) or not fn.endswith('.note'):
        abort(403)

    file_path = os.path.join(DATA_DIR, fn)
    content = ""
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

    return render_template('note.html', filename=fn, content=content)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    if _reject_name(file.filename):
        return jsonify({'error': 'Invalid filename'}), 400

    unique_filename = _get_unique_filename(file.filename)
    file.save(os.path.join(DATA_DIR, unique_filename))
    return jsonify({'name': unique_filename, 'status': 'success'})

@app.route('/upload_data', methods=['POST'])
def upload_data():
    data = request.get_json()
    filename = data.get('filename')
    content = data.get('content')

    if _reject_name(filename):
        return jsonify({'error': 'Invalid filename'}), 400

    with open(os.path.join(DATA_DIR, filename), 'w', encoding='utf-8') as f:
        f.write(content)

    return jsonify({'status': 'success', 'filename': filename})

@app.route('/rename', methods=['POST'])
def rename_file():
    data = request.get_json()
    old_name = data.get('old_name')
    new_name = data.get('new_name')

    if _reject_name(old_name) or _reject_name(new_name):
        return jsonify({'error': 'Invalid filename'}), 400

    old_path = os.path.join(DATA_DIR, old_name)
    new_path = os.path.join(DATA_DIR, new_name)

    if not os.path.exists(old_path):
        return jsonify({'error': 'File not found'}), 404
    if os.path.exists(new_path):
        return jsonify({'error': 'Target filename already exists'}), 409

    os.rename(old_path, new_path)
    return jsonify({'status': 'success'})

@app.route('/delete/<path:fn>', methods=['POST'])
def delete_file(fn):
    if _reject_name(fn):
        return jsonify({'error': 'Invalid filename'}), 400

    file_path = os.path.join(DATA_DIR, fn)
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404

    os.remove(file_path)
    return jsonify({'status': 'success'})

@app.route('/fs')
def get_fs_client():
    if not os.path.exists(CLIENT_SCRIPT_PATH):
        abort(500, "fs_client.py not found on server.")

    with open(CLIENT_SCRIPT_PATH, 'r') as f:
        client_code = f.read()

    # Dynamically set the target URL
    target_url = request.url_root.rstrip('/')
    modified_code = re.sub(
        r"TARGET_URL = \"http://127.0.0.1:5000\"",
        f"TARGET_URL = \"{target_url}\"",
        client_code
    )

    response = app.response_class(
        response=modified_code,
        status=200,
        mimetype='text/x-python'
    )
    response.headers["Content-Disposition"] = "attachment; filename=fs_client.py"
    return response

if __name__ == '__main__':
    # This part is for local development, not for Passenger
    app.run(debug=True, port=5000)