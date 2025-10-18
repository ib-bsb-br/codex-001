import re

import pytest

pytest.importorskip('playwright.sync_api')
from playwright.sync_api import expect


@pytest.mark.playwright
def test_add_task_from_board(page, live_server):
    page.goto(f"{live_server}/")
    page.click("button.nav-tab[data-target='boards']")
    page.fill('#newtodo', 'Playwright task')
    page.keyboard.press('Enter')
    first_item = page.locator('#list li').first
    expect(first_item).to_contain_text('Playwright task')

    # Toggle via space shortcut
    first_item.focus()
    page.keyboard.press(' ')
    expect(first_item).to_have_class(re.compile('done'))
