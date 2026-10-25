"""Demo transport consumes real Melody frames; no hardware side effects."""
from collections import deque
from .protocol import (Command, Decoder, FEATURES, NOISE_RESPONSE, PRESETS,
                       encode, noise_payload, parse_battery, parse_noise)


class DemoTransport:
    def __init__(self):
        self.connected = True
        self.noise = "smart"
        self.preset = 0
        self.features = {0x04: True, 0x11: False}
        self.requests = Decoder()

    def exchange(self, packet: bytes) -> bytes:
        if not self.connected:
            raise ConnectionError("演示设备已断开")
        frames = self.requests.feed(packet)
        if len(frames) != 1:
            raise ValueError("Expected one complete request")
        frame = frames[0]
        cmd, payload = frame.command, frame.payload
        if cmd == Command.SET_NOISE:
            mode = next((m for m in NOISE_RESPONSE if noise_payload(m) == payload), None)
            if mode is None:
                raise ValueError("Unsupported demo noise mode")
            self.noise = mode
            data = b"\x00"
        elif cmd == Command.NOISE:
            data = bytes((0, 1, 1, *NOISE_RESPONSE[self.noise]))
        elif cmd == Command.BATTERY:
            data = bytes((0, 3, 1, 86, 2, 82, 3, 64))
        elif cmd == Command.SET_FEATURE:
            if len(payload) != 2 or payload[0] not in self.features or payload[1] not in (0, 1):
                raise ValueError("Unsupported demo feature")
            self.features[payload[0]] = bool(payload[1])
            data = b"\x00"
        elif cmd == Command.FEATURES:
            data = bytes((0, len(self.features), *[b for k,v in self.features.items() for b in (k, int(v))]))
        elif cmd == Command.SET_EQUALIZER:
            if len(payload) != 1 or payload[0] not in {p[0] for p in PRESETS}:
                raise ValueError("Unsupported preset")
            self.preset = payload[0]
            data = b"\x00"
        elif cmd == Command.EQUALIZER:
            data = bytes((0, self.preset))
        else:
            raise ValueError("Unsupported command")
        return encode(cmd | 0x8000, data)


class DemoSession:
    def __init__(self):
        self.transport = DemoTransport()
        self.decoder = Decoder()
        self.trace = deque(maxlen=32)
        self.noise = "smart"
        self.preset = 0
        self.battery = {}
        self.features = {}
        self.refresh()

    @property
    def connected(self):
        return self.transport.connected

    def request(self, command, payload=b""):
        packet = encode(command, payload)
        reply = self.transport.exchange(packet)
        self.trace.append(f"TX {packet.hex(' ').upper()}\nRX {reply.hex(' ').upper()}")
        frames = self.decoder.feed(reply)
        if len(frames) != 1 or frames[0].command != command | 0x8000:
            raise ValueError("Unexpected response")
        if not frames[0].payload or frames[0].payload[0] != 0:
            raise ValueError("Device rejected command")
        return frames[0].payload

    def refresh(self):
        self.battery = parse_battery(self.request(Command.BATTERY))
        self.noise = parse_noise(self.request(Command.NOISE, b"\x01\x01"))
        self.preset = self.request(Command.EQUALIZER)[1]
        data = self.request(Command.FEATURES)
        self.features = {data[i]: bool(data[i+1]) for i in range(2, len(data)-1, 2)}

    def set_noise(self, mode):
        self.request(Command.SET_NOISE, noise_payload(mode))
        self.noise = parse_noise(self.request(Command.NOISE, b"\x01\x01"))
        if self.noise != mode:
            raise ValueError("Noise readback mismatch")

    def set_preset(self, preset):
        self.request(Command.SET_EQUALIZER, bytes((preset,)))
        self.preset = self.request(Command.EQUALIZER)[1]
        if self.preset != preset:
            raise ValueError("Preset readback mismatch")

    def set_feature(self, key, enabled):
        feature = FEATURES[key]
        self.request(Command.SET_FEATURE, bytes((feature, int(enabled))))
        data = self.request(Command.FEATURES)
        self.features = {data[i]: bool(data[i+1]) for i in range(2, len(data)-1, 2)}
        if self.features.get(feature) != enabled:
            raise ValueError("Feature readback mismatch")
