"""Run against a seeded local server. Requires playwright + Chromium (dev dependencies).
PLAYWRIGHT_BROWSERS_PATH=/tmp/kulisy-browsers .venv/bin/python tests/browser_smoke.py
"""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

BASE = os.getenv('TEST_BASE_URL', 'http://127.0.0.1:8000')
PASSWORD = os.getenv('DEMO_PASSWORD', 'Kulisy-demo-2026!')
Path('artifacts').mkdir(exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, channel="chromium")
    desktop = browser.new_context(viewport={'width':1440,'height':1000})
    page = desktop.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(BASE)
    page.locator('#id_username').fill('organizer@kulisy.test')
    page.locator('#id_password').fill(PASSWORD)
    page.get_by_role('button',name='Войти →',exact=True).click()
    page.get_by_role('link',name='Вечер кампуса',exact=False).click()
    expect(page.get_by_role('heading',name='Вечер кампуса',exact=True)).to_be_visible()
    expect(page.locator('#registrations-chart')).to_be_visible()
    page.screenshot(path='artifacts/dashboard-desktop.png',full_page=True)
    for route in ['guests','categories','team','budget','report']:
        page.goto(f'{BASE}/events/1/{route}/')
        assert page.locator('h1').count() == 1, route
    with page.expect_download() as download_info:
        page.get_by_role('link',name='Скачать Excel',exact=False).click()
    download_info.value.save_as('artifacts/report.xlsx')
    mobile = browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
    phone = mobile.new_page()
    phone.on('pageerror', lambda error: errors.append(str(error)))
    phone.goto(f'{BASE}/r/demo-campus/')
    expect(phone.get_by_role('heading',name='Займите своё место')).to_be_visible()
    assert phone.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    phone.screenshot(path='artifacts/registration-mobile.png',full_page=True)
    phone.goto(BASE)
    phone.locator('#id_username').fill('controller@kulisy.test')
    phone.locator('#id_password').fill(PASSWORD)
    phone.get_by_role('button',name='Войти →',exact=True).click()
    phone.get_by_role('link',name='Вечер кампуса',exact=False).click()
    expect(phone.locator('#ticket-count')).to_have_text('30')
    phone.wait_for_function("navigator.serviceWorker.controller !== null")
    phone.wait_for_function("location.search.includes('device_user')")
    phone.wait_for_function("caches.match(location.href).then(r => !!r)")
    data = phone.evaluate("fetch(document.getElementById('scanner-app').dataset.snapshot).then(r=>r.json())")
    unused = next(t for t in data['tickets'] if not t['checked'] and t['status']=='active')
    mobile.set_offline(True)
    phone.locator('#code-input').fill(unused['id'])
    phone.get_by_role('button',name='Проверить',exact=True).click()
    expect(phone.locator('#queue-count')).to_have_text('1')
    expect(phone.locator('#scan-result')).to_contain_text('Проходите')
    phone.locator('#code-input').fill(unused['id'])
    phone.get_by_role('button',name='Проверить',exact=True).click()
    expect(phone.locator('#scan-result')).to_contain_text('Уже прошёл')
    expect(phone.locator('#queue-count')).to_have_text('1')
    phone.reload()
    expect(phone.locator('#queue-count')).to_have_text('1')
    expect(phone.locator('#ticket-count')).to_have_text('30')
    assert phone.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    phone.screenshot(path='artifacts/scanner-offline-mobile.png',full_page=True)
    mobile.set_offline(False)
    phone.get_by_role('button',name='Обновить и синхронизировать').click()
    expect(phone.locator('#queue-count')).to_have_text('0',timeout=20000)
    data = phone.evaluate("fetch(document.getElementById('scanner-app').dataset.snapshot).then(r=>r.json())")
    assert next(t for t in data['tickets'] if t['id']==unused['id'])['checked']
    assert errors == [], errors
    print('PASS: desktop pages, Excel, mobile registration, offline scan, local duplicate, offline reload, reconnect and sync; no JS errors.')
    browser.close()
