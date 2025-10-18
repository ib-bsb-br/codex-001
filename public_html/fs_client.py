#!/usr/bin/env python3
import os
import sys
import json
import argparse
import requests
from subprocess import call

# This will be replaced by the server with the correct URL
TARGET_URL = "http://127.0.0.1:5000"
EDITOR = os.environ.get('EDITOR', 'vim')

def list_files():
    try:
        res = requests.get(f"{TARGET_URL}/list")
        res.raise_for_status()
        files = res.json()
        for f in files:
            print(f"{f['mod_time_str']}\t{f['name']}")
    except requests.exceptions.RequestException as e:
        print(f"Error listing files: {e}", file=sys.stderr)
        sys.exit(1)

def get_file(remote_path, local_path=None):
    if not local_path:
        local_path = os.path.basename(remote_path)

    try:
        with requests.get(f"{TARGET_URL}/f/{remote_path}", stream=True) as r:
            r.raise_for_status()
            with open(local_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        print(f"Downloaded '{remote_path}' to '{local_path}'")
    except requests.exceptions.RequestException as e:
        print(f"Error downloading file: {e}", file=sys.stderr)
        sys.exit(1)

def put_file(local_path, remote_path=None):
    if not remote_path:
        remote_path = os.path.basename(local_path)

    if not os.path.exists(local_path):
        print(f"Error: Local file '{local_path}' not found.", file=sys.stderr)
        sys.exit(1)

    try:
        with open(local_path, 'rb') as f:
            files = {'file': (remote_path, f)}
            res = requests.post(f"{TARGET_URL}/upload", files=files)
            res.raise_for_status()
        print(f"Uploaded '{local_path}' to '{res.json().get('name', remote_path)}'")
    except requests.exceptions.RequestException as e:
        print(f"Error uploading file: {e}", file=sys.stderr)
        sys.exit(1)

def cat_file(remote_path):
    try:
        res = requests.get(f"{TARGET_URL}/f/{remote_path}")
        res.raise_for_status()
        print(res.text)
    except requests.exceptions.RequestException as e:
        print(f"Error getting file content: {e}", file=sys.stderr)
        sys.exit(1)

def remove_file(remote_path):
    try:
        res = requests.post(f"{TARGET_URL}/delete/{remote_path}")
        res.raise_for_status()
        print(f"Deleted '{remote_path}'")
    except requests.exceptions.RequestException as e:
        print(f"Error deleting file: {e}", file=sys.stderr)
        sys.exit(1)

def move_file(old_path, new_path):
    try:
        res = requests.post(f"{TARGET_URL}/rename", json={'old_name': old_path, 'new_name': new_path})
        res.raise_for_status()
        print(f"Moved '{old_path}' to '{new_path}'")
    except requests.exceptions.RequestException as e:
        print(f"Error moving file: {e}", file=sys.stderr)
        sys.exit(1)

def edit_file(remote_path):
    if not remote_path.endswith('.note'):
        print("Error: Editing is only supported for .note files.", file=sys.stderr)
        sys.exit(1)

    try:
        # Fetch current content
        res = requests.get(f"{TARGET_URL}/f/{remote_path}")
        res.raise_for_status()
        initial_content = res.text
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            initial_content = "" # Create new file
        else:
            raise e
    except requests.exceptions.RequestException as e:
        print(f"Error fetching file for editing: {e}", file=sys.stderr)
        sys.exit(1)

    # Use a temporary file for editing
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix=".note") as tmp:
        tmp.write(initial_content)
        tmp.flush()
        tmp_path = tmp.name

    # Open the temp file in the user's editor
    call([EDITOR, tmp_path])

    # Read the edited content
    with open(tmp_path, 'r') as tmp:
        new_content = tmp.read()

    os.remove(tmp_path)

    # Upload the new content
    try:
        res = requests.post(f"{TARGET_URL}/upload_data", json={'filename': remote_path, 'content': new_content})
        res.raise_for_status()
        print(f"Saved changes to '{remote_path}'")
    except requests.exceptions.RequestException as e:
        print(f"Error saving file: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="CLI client for FStore.")
    subparsers = parser.add_subparsers(dest='command', required=True)

    subparsers.add_parser('ls', help='List remote files.')

    cat_parser = subparsers.add_parser('cat', help='Print remote file content.')
    cat_parser.add_argument('remote_path', help='The remote file to display.')

    get_parser = subparsers.add_parser('get', help='Download a file.')
    get_parser.add_argument('remote_path', help='The remote file to download.')
    get_parser.add_argument('local_path', nargs='?', help='The local path to save to.')

    put_parser = subparsers.add_parser('put', help='Upload a file.')
    put_parser.add_argument('local_path', help='The local file to upload.')
    put_parser.add_argument('remote_path', nargs='?', help='The remote path to save to.')

    rm_parser = subparsers.add_parser('rm', help='Delete a remote file.')
    rm_parser.add_argument('remote_path', help='The remote file to delete.')

    mv_parser = subparsers.add_parser('mv', help='Move/rename a remote file.')
    mv_parser.add_argument('old_path', help='The current remote path.')
    mv_parser.add_argument('new_path', help='The new remote path.')

    edit_parser = subparsers.add_parser('edit', help='Edit a remote .note file.')
    edit_parser.add_argument('remote_path', help='The remote .note file to edit.')

    args = parser.parse_args()

    if args.command == 'ls':
        list_files()
    elif args.command == 'cat':
        cat_file(args.remote_path)
    elif args.command == 'get':
        get_file(args.remote_path, args.local_path)
    elif args.command == 'put':
        put_file(args.local_path, args.remote_path)
    elif args.command == 'rm':
        remove_file(args.remote_path)
    elif args.command == 'mv':
        move_file(args.old_path, args.new_path)
    elif args.command == 'edit':
        edit_file(args.remote_path)

if __name__ == '__main__':
    main()