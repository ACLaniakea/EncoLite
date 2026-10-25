"""Run the built application's own smoke callbacks and collect its report."""
from pathlib import Path
import sys,subprocess,json
sys.stdout.reconfigure(encoding='utf-8',errors='backslashreplace')
ROOT=Path(__file__).resolve().parents[1]
bundle=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'dist/EncoLite'
report=ROOT/'verification/bundle-smoke.json'
report.unlink(missing_ok=True)
process=subprocess.Popen([str(bundle/'EncoLite.exe'),'--smoke-test','--no-tray','--test-report',str(report)],
                         stdout=subprocess.PIPE,stderr=subprocess.PIPE)
try:
    stdout,stderr=process.communicate(timeout=25)
except subprocess.TimeoutExpired:
    process.kill();stdout,stderr=process.communicate()
    print('FAIL: bundle smoke timed out',flush=True)
print('exit:',process.returncode,flush=True)
(ROOT/'verification/bundle-stderr.log').write_bytes(stderr)
print(stderr.decode(errors='replace')[-3500:],flush=True)
if not report.exists():raise SystemExit(1)
data=json.loads(report.read_text());print(json.dumps(data),flush=True)
assert process.returncode==0 and data['result']=='PASS'
