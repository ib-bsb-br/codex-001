import threading
from typing import Generator

import pytest
from werkzeug.serving import make_server

from public_html.fstore_app import app as flask_app


@pytest.fixture(scope='session')
def live_server(tmp_path_factory: pytest.TempPathFactory) -> Generator[str, None, None]:
    data_dir = tmp_path_factory.mktemp('data')
    flask_app.app.config['DATA_DIR'] = str(data_dir)
    flask_app.app.config['TESTING'] = True

    server = make_server('127.0.0.1', 0, flask_app.app)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{port}'
    finally:
        server.shutdown()
        thread.join()
