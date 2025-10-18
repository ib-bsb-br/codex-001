import json
import os
import tempfile
import unittest

from public_html.fstore_app import app as flask_app
from public_html.fstore_app.app import safe_slug


class BoardAppTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        flask_app.app.config['TESTING'] = True
        flask_app.app.config['DATA_DIR'] = self.tempdir.name
        self.client = flask_app.app.test_client()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_index_renders(self) -> None:
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('data-board-slug', response.get_data(as_text=True))

    def test_quick_add_creates_task(self) -> None:
        response = self.client.get('/?b=test&add=Sample', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        api = self.client.get('/api/boards/test')
        payload = api.get_json()
        self.assertEqual(len(payload['tasks']), 1)
        self.assertEqual(payload['tasks'][0]['text'], 'Sample')

    def test_board_operations(self) -> None:
        add = self.client.post(
            '/api/boards/demo',
            json={'op': 'add', 'text': 'Task A'}
        )
        self.assertEqual(add.status_code, 200)
        toggle = self.client.post(
            '/api/boards/demo',
            json={'op': 'toggle', 'id': add.get_json()['tasks'][0]['id']}
        )
        self.assertEqual(toggle.status_code, 200)
        data = toggle.get_json()
        self.assertTrue(data['tasks'][0]['done'])

    def test_etag_support(self) -> None:
        initial = self.client.get('/api/boards/public')
        self.assertEqual(initial.status_code, 200)
        etag = initial.headers.get('ETag')
        conditional = self.client.get('/api/boards/public', headers={'If-None-Match': etag})
        self.assertEqual(conditional.status_code, 304)

    def test_safe_slug(self) -> None:
        slug = safe_slug('../weird value!!')
        self.assertEqual(slug, '___weird_value__')


if __name__ == '__main__':
    unittest.main()
