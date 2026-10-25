"""Render each view with Slint's own offscreen backend for visual review."""
from pathlib import Path
import base64
import json
import os
import subprocess
import sys
import time

from ui_probe import rpc

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/"verification"


def capture(name, arguments, live=False, dark=False, notice=False, charging=False):
    env = os.environ.copy()
    env.update(PYTHONPATH=str(ROOT/".test-deps"),SLINT_EMIT_DEBUG_INFO="1",
               SLINT_MCP_PORT="19463",SLINT_BACKEND="headless-software")
    with (OUT/"headless.log").open("w") as log:
        child = subprocess.Popen([sys.executable,str(ROOT/"tools/preview_charging.py") if charging else str(ROOT/"tools/preview_notice.py") if notice else str(ROOT/"tools/preview_dark.py") if dark else str(ROOT/"main.py"),*([] if dark or notice or charging else ["--no-tray",*([] if live else ["--preview"])]),*arguments],
                                 env=env,stdout=log,stderr=log)
        try:
            for _ in range(50):
                if child.poll() is not None:
                    raise RuntimeError((OUT/"headless.log").read_text())
                try:
                    rpc("initialize",{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"EncoLite layout review","version":"0.1"}})
                    break
                except Exception:
                    time.sleep(.1)
            if live:
                time.sleep(3)
            data=rpc("tools/call",{"name":"list_windows","arguments":{}})
            handle=json.loads(data["result"]["content"][0]["text"])["windowHandles"][0]
            props=rpc("tools/call",{"name":"get_window_properties","arguments":{"windowHandle":handle}})
            (OUT/(name+"-geometry.json")).write_text(json.dumps(props,indent=2),"utf-8")
            result=rpc("tools/call",{"name":"take_screenshot","arguments":{"windowHandle":handle}})
            for content in result["result"]["content"]:
                if content["type"]=="image":
                    (OUT/(name+".png")).write_bytes(base64.b64decode(content["data"]))
            print("Rendered:",name,flush=True)
        finally:
            child.terminate()
            child.wait(10)


if __name__=="__main__":
    OUT.mkdir(exist_ok=True)
    live="--live" in sys.argv
    if '--charging' in sys.argv:
        for name,args in (('charging-main',[]),('charging-quick',['--quick']),('charging-quick-dark',['--quick','--dark'])):
            capture(name,args,charging=True)
        sys.exit()
    for page,name in enumerate(("main","sound","settings","about","features","custom","devices")):
        if "--popups-only" not in sys.argv and ("--compact" not in sys.argv or page in (0,5)):
            capture(name,["--page",str(page)],live=live)
    capture("quick",["--quick"],live=live)
    if "--notice" in sys.argv:
        capture("connection-notice",[],notice=True)
    if "--dark" in sys.argv:
        capture("main-dark",[],dark=True)
        capture("quick-dark",["--quick"],dark=True)
