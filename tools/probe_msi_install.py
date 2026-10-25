"""Temporary first-run MSI check in this project's isolated install directory."""
from pathlib import Path
import subprocess,os
ROOT=Path(__file__).resolve().parents[1]
msi=ROOT/'release/EncoLite-0.3.0-preview.2-win-x64.msi'
target=ROOT/'.install-test/Enco Lite'
log=ROOT/'verification/native-msi-install.log'
exe=Path(os.environ['SystemRoot'])/'System32/msiexec.exe'
command=f'"{exe}" /i "{msi}" /qn /norestart INSTALLDIR="{target}" /L*v "{log}"'
print(command,flush=True)
p=subprocess.run(command,timeout=60)
print('MSI_INSTALL_EXIT',p.returncode,flush=True)
