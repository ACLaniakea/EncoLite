"""Inspect the app's own headless Slint renderer, not the Windows desktop."""
from pathlib import Path
import base64
import json
import os
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/"verification"
PORT = 19463


def rpc(method, params):
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/mcp",
        json.dumps({"jsonrpc":"2.0", "id":1, "method":method,"params":params}).encode(),
        {"Content-Type":"application/json","Accept":"application/json, text/event-stream"})
    with urllib.request.urlopen(req,timeout=20) as response:
        body=response.read().decode()
    if body.lstrip().startswith("{"):
        return json.loads(body)
    lines = [x[6:] for x in body.splitlines() if x.startswith("data: ")]
    return json.loads(lines[-1])


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    action=sys.argv[1]
    if action == "start":
        env=os.environ.copy()
        env.update(PYTHONPATH=str(ROOT/".test-deps"), SLINT_EMIT_DEBUG_INFO="1",
                   SLINT_MCP_PORT=str(PORT), SLINT_BACKEND="headless-software")
        log=(OUT/"headless.log").open("w")
        child=subprocess.Popen([sys.executable,str(ROOT/"main.py"),"--preview",*sys.argv[2:]],env=env,stdout=log,stderr=log)
        (OUT/"headless-pid.txt").write_text(str(child.pid))
        for _ in range(50):
            try:
                print(json.dumps(rpc("initialize",{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"EncoLite preview","version":"0.1"}}),ensure_ascii=False));break
            except Exception:
                if child.poll() is not None:
                    raise RuntimeError((OUT/"headless.log").read_text())
                time.sleep(.2)
        else: raise RuntimeError("Renderer did not start")
    elif action == "tools":
        print(json.dumps(rpc("tools/list",{}),ensure_ascii=False))
    elif action == "stop":
        sys.path.insert(0,str(ROOT/".build-deps"))
        import psutil
        process=psutil.Process(int((OUT/"headless-pid.txt").read_text()))
        if str(ROOT/"main.py").lower() in " ".join(process.cmdline()).lower():
            process.terminate()
            process.wait(10)
    else:
        result=rpc("tools/call",{"name":action,"arguments":json.loads(sys.argv[2]) if len(sys.argv)>2 else {}})
        for content in result.get("result",{}).get("content",[]):
            if content.get("type")=="image":
                path=OUT/(sys.argv[3] if len(sys.argv)>3 else "preview.png")
                path.write_bytes(base64.b64decode(content["data"]))
                content["data"]="saved: "+str(path)
        print(json.dumps(result,ensure_ascii=False))
