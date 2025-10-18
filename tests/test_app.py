import io
import os
import tempfile
import unittest
from typing import Dict

from public_html.fstore_app import app as flask_app
from public_html.fstore_app.app import board_etag, load_board, safe_slug


class HubAppTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        flask_app.app.config['TESTING'] = True
        flask_app.app.config['DATA_DIR'] = self.tempdir.name
        self.client = flask_app.app.test_client()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _headers(self, slug: str, key: str) -> Dict[str, str]:
        board = load_board(slug)
        return {
            'Content-Type': 'application/json',
            'If-Match': board_etag(board),
            'Idempotency-Key': key,
        }

    def test_dashboard_renders_files_and_boards(self) -> None:
        response = self.client.get('/')
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Shared Files', body)
        self.assertIn('data-board-slug', body)

    def test_quick_add_creates_task(self) -> None:
        response = self.client.get('/?b=test&add=Sample', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        api = self.client.get('/api/boards/test')
        payload = api.get_json()
        self.assertEqual(len(payload['tasks']), 1)
        self.assertEqual(payload['tasks'][0]['text'], 'Sample')

    def test_board_mutations_respect_concurrency(self) -> None:
        headers = self._headers('demo', 'demo-add')
        add = self.client.post('/api/boards/demo', headers=headers, json={'op': 'add', 'text': 'Task A'})
        self.assertEqual(add.status_code, 200)
        task_id = add.get_json()['tasks'][0]['id']

        toggle_headers = {
            'Content-Type': 'application/json',
            'If-Match': add.headers.get('ETag'),
            'Idempotency-Key': 'demo-toggle',
        }
        toggle = self.client.post('/api/boards/demo', headers=toggle_headers, json={'op': 'toggle', 'id': task_id})
        self.assertEqual(toggle.status_code, 200)
        self.assertTrue(toggle.get_json()['tasks'][0]['done'])

        # Idempotent replay returns cached result
        toggle_headers['If-Match'] = toggle.headers.get('ETag')
        replay = self.client.post('/api/boards/demo', headers=toggle_headers, json={'op': 'toggle', 'id': task_id})
        self.assertEqual(replay.status_code, 200)
        self.assertTrue(replay.get_json()['tasks'][0]['done'])

    def test_conflict_returns_409(self) -> None:
        headers = self._headers('conflict', 'first')
        first = self.client.post('/api/boards/conflict', headers=headers, json={'op': 'add', 'text': 'A'})
        self.assertEqual(first.status_code, 200)
        stale_headers = {
            'Content-Type': 'application/json',
            'If-Match': headers['If-Match'],
            'Idempotency-Key': 'second',
        }
        conflict = self.client.post('/api/boards/conflict', headers=stale_headers, json={'op': 'add', 'text': 'B'})
        self.assertEqual(conflict.status_code, 409)

    def test_file_crud_cycle(self) -> None:
        upload = (self.client.post(
            '/api/files/upload',
            data={'file': (io.BytesIO(b'hello'), 'hello.txt')},
            content_type='multipart/form-data'
        ))
        self.assertEqual(upload.status_code, 200)

        listing = self.client.get('/api/files')
        names = [item['name'] for item in listing.get_json()]
        self.assertIn('hello.txt', names)

        rename = self.client.post('/api/files/rename', json={'old_name': 'hello.txt', 'new_name': 'hi.txt'})
        self.assertEqual(rename.status_code, 200)

        delete = self.client.post('/api/files/delete/hi.txt')
        self.assertEqual(delete.status_code, 200)

    def test_fs_documentation(self) -> None:
        response = self.client.get('/fs')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Automation', response.get_data(as_text=True))

    def test_safe_slug(self) -> None:
        self.assertEqual(safe_slug('../weird value!!'), '___weird_value__')


if __name__ == '__main__':
    unittest.main()
