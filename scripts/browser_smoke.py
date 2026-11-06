"""Optional real-browser regression: requires Playwright and Chromium, running app.
Run: python scripts/browser_smoke.py --url http://127.0.0.1:8502
Does not install browser dependencies or use synthetic data as validated evidence.
"""
import argparse
import csv
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from playwright.sync_api import sync_playwright, expect

parser=argparse.ArgumentParser()
parser.add_argument('--url',default='http://127.0.0.1:8502')
parser.add_argument('--chromium',default='/usr/bin/chromium')
args=parser.parse_args()
with sync_playwright() as p, TemporaryDirectory() as tmp:
    browser=p.chromium.launch(executable_path=args.chromium, headless=True, args=['--no-sandbox'])
    page=browser.new_page(accept_downloads=True)
    errors=[]
    page.on('pageerror',lambda e: errors.append(str(e)))
    page.goto(args.url)
    expect(page.get_by_role('tab',name='Dashboard',exact=True)).to_be_visible(timeout=30000)
    tabs=['Dashboard','Pervane Performans Analizi','Open-Water Characteristics','Pervane Karşılaştırması','Deneysel Veri Analizi','Proje Ayarları']
    for tab in tabs:
        page.get_by_role('tab',name=tab,exact=True).click()
        expect(page.get_by_role('tab',name=tab,exact=True)).to_have_attribute('aria-selected','true')
    with page.expect_download() as info:
        page.get_by_role('button',name='Proje şemasını JSON indir').click()
    dest=Path(tmp)/'project.json';info.value.save_as(dest)
    project=json.loads(dest.read_text())
    assert len(project['thrusters'])==2 and all(not t['samples'] for t in project['thrusters'])
    page.get_by_role('tab',name='Open-Water Characteristics',exact=True).click()
    page.locator('input[type=file]').nth(0).set_input_files(dict(name='synthetic_test.csv',mimeType='text/csv',buffer=b'J,KT,KQ\n0,.2,.04\n1,.1,.02\n'))
    expect(page.get_by_text('Deneysel interpolasyon:',exact=False)).to_be_visible(timeout=30000)
    assert page.locator('[data-testid=stPlotlyChart]').count()>=3
    for label, filename, columns in [
        ('Temsili CSV şablonu indir','template.csv', {'J','KT','KQ'}),
        ('Hesaplanmış eğrileri indir','curves.csv', {'J','thrust_n','torque_nm','shaft_power_w','status'}),
    ]:
        with page.expect_download() as info:
            page.get_by_role('button',name=label,exact=True).click()
        dest=Path(tmp)/filename;info.value.save_as(dest)
        rows=list(csv.DictReader(io.StringIO(dest.read_text())))
        assert rows and columns.issubset(rows[0])
    page.get_by_role('tab',name='Pervane Karşılaştırması',exact=True).click()
    with page.expect_download() as info:
        page.get_by_role('button',name='Karşılaştırmayı CSV indir').click()
    dest=Path(tmp)/'comparison.csv';info.value.save_as(dest)
    rows=list(csv.DictReader(io.StringIO(dest.read_text())))
    assert len(rows)==2 and {r['propeller'] for r in rows}=={'A','B'}
    page.get_by_role('tab',name='Pervane Performans Analizi',exact=True).click()
    page.get_by_label('Analiz yöntemi',exact=True).click()
    page.get_by_role('option',name='B — Deneysel açık su CSV',exact=True).click()
    expect(page.get_by_text('4.851 N',exact=True)).to_be_visible(timeout=30000)
    with page.expect_download() as info:
        page.get_by_role('button',name='Çalışma noktasını CSV indir').click()
    dest=Path(tmp)/'point.csv';info.value.save_as(dest)
    row=next(csv.DictReader(io.StringIO(dest.read_text())))
    assert abs(float(row['kt'])-.15)<1e-10 and row['method'].startswith('B')
    page.get_by_role('tab',name='Deneysel Veri Analizi',exact=True).click()
    with page.expect_download() as info:
        page.get_by_role('button',name='Temsili ölçüm şablonunu indir').click()
    dest=Path(tmp)/'measurement_template.csv';info.value.save_as(dest)
    assert len(list(csv.DictReader(io.StringIO(dest.read_text()))))==3
    page.locator('input[type=file]').nth(1).set_input_files(dict(name='measurement_test.csv',mimeType='text/csv',buffer=b'rpm,advance_speed_m_s,thrust_n,torque_nm,electrical_power_w\n3000,1.5,3.88,.0485,25\n'))
    expect(page.get_by_role('button',name='Boyutsuzlaştırılmış verileri indir')).to_be_visible(timeout=30000)
    with page.expect_download() as info:
        page.get_by_role('button',name='Boyutsuzlaştırılmış verileri indir').click()
    dest=Path(tmp)/'measurement.csv';info.value.save_as(dest)
    row=next(csv.DictReader(io.StringIO(dest.read_text())))
    assert float(row['electrical_power_w'])==25 and .119<float(row['KT'])<.121
    page.locator('input[type=file]').nth(1).set_input_files(dict(name='invalid.csv',mimeType='text/csv',buffer=b'wrong\n1\n'))
    expect(page.get_by_text('Ölçüm verisi işlenemedi:',exact=False)).to_be_visible(timeout=30000)
    assert not errors, errors
    assert page.locator('[data-testid=stException]').count()==0
    browser.close()
    print('PASS: six tabs, actual coefficient/measurement uploads, B calculation, CSV/JSON downloads, malformed CSV, no JS errors')
