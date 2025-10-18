import os
import tempfile

import pytest

pytest.importorskip('playwright.sync_api')
from playwright.sync_api import expect


@pytest.mark.playwright
def test_upload_and_delete_file(page, live_server):
    page.goto(f"{live_server}/")
    page.click("button.nav-tab[data-target='files']")

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(b'from playwright')
        tmp_path = tmp.name
    try:
        page.set_input_files('#file-input', tmp_path)
        expect(page.locator('#files-status')).to_contain_text('Uploaded', timeout=5000)

        rows = page.locator('#files-table tbody tr')
        expect(rows).to_have_count(1)
        expect(rows.first).to_contain_text(os.path.basename(tmp_path))

        page.once('dialog', lambda dialog: dialog.accept())
        rows.first.locator("button[data-action='delete']").click()
        expect(page.locator('#files-status')).to_contain_text('Deleted', timeout=5000)
    finally:
        os.unlink(tmp_path)
