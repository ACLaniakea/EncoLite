"""Measure the isolated framework experiment; leave the live controller running."""
from pathlib import Path
import hashlib
import json
import statistics
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / '.build-deps'), str(ROOT / 'tools')]
import psutil
from memory_metrics import process_tree_memory

OUT = ROOT / 'verification/qt-probe'
OUT.mkdir(parents=True, exist_ok=True)
for stale in ('window.json', 'failure.txt'):
    (OUT / stale).unlink(missing_ok=True)
host = ROOT / '.tools/python-3.13.17-embed-amd64/python.exe'
report = {'production_replaced': False, 'bluetooth_used': False,
          'scope': 'Representative Qt Quick controls; not the migrated application', 'samples': []}
with (OUT / 'stdout.log').open('wb') as stdout, (OUT / 'stderr.log').open('wb') as stderr:
    process = subprocess.Popen([str(host), str(ROOT / 'tools/qt_probe.py')], cwd=ROOT, stdout=stdout, stderr=stderr)
    try:
        for _ in range(25):
            if process.poll() is not None: break
            time.sleep(1)
        if process.poll() is None:
            for _ in range(15):
                tree = process_tree_memory(process.pid)
                for row in tree['processes']:
                    row['private_working_set'] = psutil.Process(row['pid']).memory_full_info().uss
                tree['private_working_set_sum'] = sum(row['private_working_set'] for row in tree['processes'])
                report['samples'].append(tree)
                time.sleep(.5)
        process.wait(timeout=20)
        report['exit_code'] = process.returncode
    except Exception as error:
        report['error'] = str(error)
        if process.poll() is None:
            process.terminate(); process.wait(timeout=10)
    if report['samples']:
        for key in ('working_set_sum', 'private_bytes_sum', 'private_working_set_sum'):
            report['mean_' + key + '_mib'] = round(statistics.mean(row[key] for row in report['samples']) / 1048576, 2)
    if (OUT / 'window.json').exists():
        report['window'] = json.loads((OUT / 'window.json').read_text('utf-8'))
    report['result'] = 'PASS' if report.get('exit_code') == 0 and report.get('window', {}).get('result') == 'PASS' else 'FAIL'
    (OUT / 'report.json').write_text(json.dumps(report, indent=2), 'utf-8')
print(json.dumps({key: value for key, value in report.items() if key != 'samples'}), flush=True)
print((OUT / 'stderr.log').read_text('utf-8', errors='replace'), flush=True)
