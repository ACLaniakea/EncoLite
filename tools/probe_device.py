"""Read-only hardware probe. Never sends a SET command."""
from pathlib import Path
import json
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from encolite.bluetooth_windows import discover,Rfcomm,MELODY
from encolite.protocol import Decoder,encode


def query(link,decoder,command,payload=b"",timeout=2):
    link.write(encode(command,payload))
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        for frame in decoder.feed(link.read(.15)):
            if frame.command==command|0x8000:
                return frame.payload
    raise TimeoutError(f"Command {command:04X} timed out")


if __name__=="__main__":
    for device in discover():
        for service,channel in ((MELODY,0),(str(__import__('uuid').UUID(int=0)),1),(str(__import__('uuid').UUID(int=0)),15)):
            link=Rfcomm()
            try:
                link.connect(device,service=service,channel=channel,timeout=2)
                decoder=Decoder()
                results={"name":device.name,"channel":channel}
                for command,payload in ((0x0103,b""),(0x0100,b""),(0x0106,b""),(0x010c,b"\x01\x01"),(0x010f,b""),(0x010d,b""),(0x0105,b""),(0x0200,b"")):
                    try:
                        results[f"{command:04X}"]=query(link,decoder,command,payload).hex(" ")
                    except TimeoutError as error:
                        results[f"{command:04X}"]=str(error)
                print(json.dumps(results,ensure_ascii=False),flush=True)
                if "timed out" not in results["0103"]:
                    break
            except (OSError,TimeoutError) as error:
                print(json.dumps({"channel":channel,"error":str(error)},ensure_ascii=False),flush=True)
            finally:
                link.close()
