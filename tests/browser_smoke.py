"""Optional browser regression: python tests/browser_smoke.py (Playwright + Chromium)."""
import os
from pathlib import Path
import subprocess
import tempfile
import time
from urllib.request import Request, urlopen

from openpyxl import load_workbook
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
API = 'http://127.0.0.1:8002'
WEB = 'http://127.0.0.1:8010'


def wait_ready(url):
    for _ in range(80):
        try:
            with urlopen(url, timeout=1):
                return
        except OSError:
            time.sleep(.1)
    raise AssertionError(f'Not ready: {url}')


with tempfile.TemporaryDirectory() as temp:
    runtime = dict(os.environ, HOSPITAL_DATA_DIR=temp, FRONTEND_ORIGINS=WEB)
    subprocess.run(['python', 'scripts/build_static.py'], cwd=ROOT,
                   env=dict(os.environ, API_BASE_URL=API), check=True)
    log = open(Path(temp) / 'server.log', 'w')
    backend = subprocess.Popen([str(ROOT / '.venv/bin/python'), '-m', 'uvicorn', 'app.main:app', '--port', '8002'], cwd=ROOT, env=runtime, stdout=log, stderr=log)
    frontend = subprocess.Popen(['python', '-m', 'http.server', '8010', '--bind', '127.0.0.1', '--directory', str(ROOT / 'dist')], stdout=log, stderr=log)
    try:
        wait_ready(API + '/api/health')
        wait_ready(WEB)
        preflight = Request(API + '/api/login', method='OPTIONS', headers={'Origin': WEB, 'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'content-type'})
        with urlopen(preflight) as response:
            assert response.headers['Access-Control-Allow-Origin'] == WEB
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox'])
            page = browser.new_page(viewport={'width': 1440, 'height': 1000})
            page.set_default_timeout(6000)
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            held = []
            page.route(API + '/api/**', lambda route: held.append(route))
            page.goto(WEB, wait_until='domcontentloaded')
            page.locator('#login').wait_for(state='visible')
            page.locator('#lang').click()
            assert page.locator('#loginForm button').inner_text() == '登入'
            page.locator('#connectionBanner').wait_for(state='visible')
            # The backend has not answered, yet the login UI is interactive.
            assert held
            page.locator('#loginForm [name=username]').fill('admin')
            page.locator('#loginForm [name=password]').fill('demo1234')
            held.pop(0).abort()
            page.get_by_text('伺服器暫時無法連線。請重新連線；表單內容仍保留。', exact=True).first.wait_for()
            page.locator('#loginForm button').click()
            page.wait_for_timeout(100)
            assert page.locator('#loginForm button').is_disabled()
            assert len(held) == 1
            held.pop(0).abort()
            page.locator('#loginForm button').wait_for(state='visible')
            page.wait_for_timeout(100)
            assert page.locator('#loginForm [name=password]').input_value() == 'demo1234'
            assert '帳號或密碼錯誤' not in page.locator('#loginError').inner_text()
            page.unroute(API + '/api/**')
            page.locator('#retryConnection').click()
            page.locator('#connectionBanner').wait_for(state='hidden')
            page.locator('#loginForm button').click()
            page.locator('#dashboard').wait_for(state='visible')
            assert page.locator('#overview #recordForm').is_visible()
            assert page.locator('#editorDialog').count()==0
            assert page.locator('[name=patientName], [name=chartNo], [name=examDate], [name=physician]').count() == 0
            page.locator('[name=caseId]').fill('STATIC-001')
            # Search both English and Chinese regardless of interface language.
            page.locator('#diagnosisSearch').fill('spastic')
            page.locator('#diagnoses input:visible').first.check()
            page.locator('#diagnosisSearch').fill('腦性麻痺')
            assert page.locator('#diagnoses input:checked').count() == 1
            page.locator('#recordForm button.primary').click()
            page.locator('#overview').wait_for(state='hidden');page.locator('#records').wait_for(state='visible')
            page.locator('#recordRows').get_by_text('STATIC-001', exact=True).wait_for()
            assert '已選取 1 筆' in page.locator('#selectionStatus').inner_text()
            # Legacy data must not be displayed or searched, and editing must preserve it.
            auth = {'Authorization': 'Bearer ' + page.evaluate('sessionStorage.token')}
            legacy = page.request.post(API + '/api/records', headers=auth, data={'caseId':'LEGACY-002', 'patientName':'REMOVED-NAME', 'chartNo':'REMOVED-CHART', 'examDate':'2099-12-31', 'physician':'REMOVED-DOCTOR'}).json()
            page.reload();page.locator('#dashboard').wait_for(state='visible');page.locator('[data-tab=records]').click()
            page.locator('#recordRows').get_by_text('LEGACY-002', exact=True).wait_for()
            assert 'REMOVED-NAME' not in page.locator('#recordRows').inner_text()
            page.locator('[data-tab=overview]').click()
            page.locator('#overviewCaseRows').get_by_text('LEGACY-002', exact=True).wait_for()
            dashboard_text=page.locator('#overview').inner_text()
            for removed in ['REMOVED-NAME','REMOVED-CHART','2099-12-31','REMOVED-DOCTOR','Patient name','Chart number','Examination date']:
                assert removed not in dashboard_text
            assert page.locator('#overviewCaseRows tr').count()==2
            page.locator('#lang').click()
            assert page.locator('#overview').get_by_role('columnheader',name='Case ID',exact=True).count()==1
            page.locator('#lang').click()
            page.locator('[data-tab=records]').click()

            page.locator('#search').fill('REMOVED-NAME')
            assert page.locator('#recordRows tr').count() == 0
            page.locator('#search').fill('LEGACY-002')
            page.locator('#recordRows [data-edit]').click()
            assert page.locator('#overview').is_visible()
            page.locator('#recordForm button.primary').click();page.locator('#overview').wait_for(state='hidden');page.locator('#records').wait_for(state='visible')
            stored = page.request.get(API + '/api/records', headers=auth).json()
            assert next(row for row in stored if row['id']==legacy['id'])['patientName']=='REMOVED-NAME'
            page.locator('#search').fill('STATIC-001')
            page.locator('#recordRows .record-select').check()
            # Only the selected case is downloaded below.
            page.locator('#search').fill('')
            page.locator('#recordRows .record-select').evaluate_all('(boxes)=>boxes.forEach(box=>{if(box.checked && box.closest("tr").textContent.includes("LEGACY-002"))box.click()})')
            for width in [1280, 1440, 1920]:
                page.set_viewport_size({'width': width, 'height': 1000})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                assert page.locator('#caseWorkbook').evaluate('(el)=>el.getBoundingClientRect().width') <= 1
                assert page.locator('#export').evaluate('(el)=>el.getBoundingClientRect().height') <= 45
            assert page.locator('[data-tab=entry]').count()==0
            page.locator('#clearSelection').click()
            assert page.locator('#export').is_disabled()
            page.locator('#search').fill('STATIC-001, LEGACY-002')
            assert page.locator('#recordRows tr').count()==2
            page.locator('#selectMatches').click()
            assert page.locator('#selectedCases button').count()==2
            page.locator('#search').fill('STATIC-001')
            assert page.locator('#selectedCases button').count()==2
            for fmt in ['csv','txt']:
                page.locator('#exportFormat').select_option(fmt)
                with page.expect_download() as result:
                    page.locator('#export').click()
                export_path=Path(temp)/('cases.'+fmt)
                result.value.save_as(export_path)
                content=export_path.read_text(encoding='utf-8-sig')
                assert 'STATIC-001' in content and 'LEGACY-002' in content
                assert 'REMOVED-NAME' not in content
            page.locator('#selectedCases [data-unselect="'+legacy['id']+'"]').click()
            assert page.locator('#selectedCases button').count()==1
            page.locator('#exportFormat').select_option('xlsx')
            with page.expect_download() as download:
                page.locator('#export').click()
            path = Path(temp) / 'output.xlsx'
            download.value.save_as(path)
            wb = load_workbook(path)
            assert wb['Case overview']['B1'].value == '診斷分類\nDiagnosis Groups'
            assert '腦性麻痺' in wb['Checklist details']['B7'].value
            if os.environ.get('ARTIFACT_DIR'):
                artifact_dir = Path(os.environ['ARTIFACT_DIR'])
                artifact_dir.mkdir(parents=True, exist_ok=True)
                (artifact_dir / 'rehab-bilingual-sample.xlsx').write_bytes(path.read_bytes())
                page.set_viewport_size({'width': 1440, 'height': 1000})
                page.screenshot(path=str(artifact_dir / 'rehab-desktop-v2.png'), full_page=True)
                page.screenshot(path=str(artifact_dir / 'records-ui-zh.png'), full_page=True)
            page.locator('#lang').click()
            assert page.locator('#export').inner_text().strip().endswith('Download')
            if os.environ.get('ARTIFACT_DIR'):
                page.screenshot(path=str(artifact_dir / 'records-ui-en.png'), full_page=True)
            page.locator('.records-filter summary').click()
            assert page.locator('#importDate').is_visible()
            page.locator('.records-filter summary').click()
            page.reload()
            page.locator('#dashboard').wait_for(state='visible')
            page.locator('[data-tab=records]').click()
            page.locator('#recordRows').get_by_text('STATIC-001', exact=True).wait_for()
            page.locator('#caseWorkbook').set_input_files({'name':'cases.csv','mimeType':'text/csv','buffer':b'CASE ID,Diagnosis\nIMPORT-003,Autism\n'})
            page.locator('#pendingImportBar').wait_for(state='visible')
            assert page.locator('#export').is_disabled()
            page.locator('#saveImported').click()
            page.locator('#pendingImportBar').wait_for(state='hidden')
            page.locator('#recordRows').get_by_text('cases-IMPORT-003',exact=True).wait_for()
            assert page.locator('#selectedCases button').count()==1
            assert not errors, errors
            browser.close()
        print('PASS: static UI while API is pending/offline; login language; retry; duplicate-submit protection; cross-origin login/CRUD; bilingual search and XLSX; desktop widths; reload persistence')
    finally:
        frontend.terminate()
        backend.terminate()
        frontend.wait()
        backend.wait()
        log.close()
