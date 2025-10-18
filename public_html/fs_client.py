#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
import tempfile
import urllib.parse
from typing import Optional

import requests

TARGET_URL = "http://127.0.0.1:5000"
SESSION = requests.Session()


def api(path: str) -> str:
    base = TARGET_URL.rstrip('/')
    if not path.startswith('/'):
        path = '/' + path
    return base + path


def list_files() -> None:
    res = SESSION.get(api('/api/files'), timeout=30)
    res.raise_for_status()
    for entry in res.json():
        print(f"{entry['mod_time_str']}\t{entry['name']}")


def download(remote: str, local: Optional[str]) -> None:
    url = api('/files/' + urllib.parse.quote(remote))
    with SESSION.get(url, stream=True, timeout=30) as res:
        res.raise_for_status()
        if local == '-' or local is None:
            handle = sys.stdout.buffer
            for chunk in res.iter_content(chunk_size=8192):
                handle.write(chunk)
            handle.flush()
        else:
            with open(local, 'wb') as handle:
                for chunk in res.iter_content(chunk_size=8192):
                    handle.write(chunk)
            print(f"Downloaded {remote} -> {local}")


def upload(local: str, remote: Optional[str]) -> None:
    remote = remote or os.path.basename(local)
    with open(local, 'rb') as handle:
        res = SESSION.post(api('/api/files/upload'), files={'file': (remote, handle)}, timeout=30)
    res.raise_for_status()
    name = res.json().get('name', remote)
    print(f"Uploaded as {name}")


def rename(old: str, new: str) -> None:
    res = SESSION.post(api('/api/files/rename'), json={'old_name': old, 'new_name': new}, timeout=30)
    if res.status_code == 409:
        print('Target name already exists', file=sys.stderr)
        sys.exit(1)
    res.raise_for_status()
    print(f"Renamed {old} -> {new}")


def delete(remote: str) -> None:
    res = SESSION.post(api('/api/files/delete/' + urllib.parse.quote(remote)), timeout=30)
    if res.status_code == 404:
        print('Not found', file=sys.stderr)
        sys.exit(1)
    res.raise_for_status()
    print(f"Deleted {remote}")


def edit(remote: str) -> None:
    if not remote.endswith('.note'):
        print('edit is only supported for .note files', file=sys.stderr)
        sys.exit(1)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.note')
    tmp_path = tmp.name
    tmp.close()
    try:
        try:
            download(remote, tmp_path)
        except requests.HTTPError as exc:  # allow missing note
            if exc.response.status_code != 404:
                raise
        editor = os.environ.get('EDITOR', 'vim')
        subprocess.call([editor, tmp_path])
        with open(tmp_path, 'r', encoding='utf-8') as handle:
            content = handle.read()
        res = SESSION.post(api('/api/files/upload-data'), json={'filename': remote, 'content': content})
        res.raise_for_status()
        print(f"Saved {remote}")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def main() -> None:
    parser = argparse.ArgumentParser(description='FStore hub CLI')
    sub = parser.add_subparsers(dest='command', required=True)

    sub.add_parser('ls')

    p_get = sub.add_parser('get')
    p_get.add_argument('remote')
    p_get.add_argument('local', nargs='?', default=None)

    p_put = sub.add_parser('put')
    p_put.add_argument('local')
    p_put.add_argument('remote', nargs='?', default=None)

    p_cat = sub.add_parser('cat')
    p_cat.add_argument('remote')

    p_rm = sub.add_parser('rm')
    p_rm.add_argument('remote')

    p_mv = sub.add_parser('mv')
    p_mv.add_argument('old')
    p_mv.add_argument('new')

    p_edit = sub.add_parser('edit')
    p_edit.add_argument('remote')

    args = parser.parse_args()

    if args.command == 'ls':
        list_files()
    elif args.command == 'get':
        download(args.remote, args.local or args.remote)
    elif args.command == 'put':
        upload(args.local, args.remote)
    elif args.command == 'cat':
        download(args.remote, '-')
    elif args.command == 'rm':
        delete(args.remote)
    elif args.command == 'mv':
        rename(args.old, args.new)
    elif args.command == 'edit':
        edit(args.remote)


if __name__ == '__main__':
    main()
