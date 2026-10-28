"""Melody framing, shared parsers and the X3 offline test fixture.

Adapted from OppoPodsManager (Copyright 2026 Zhaoyi-ya), GPL-3.0-or-later.
Modified 2026-10-22: bounded Python codec and explicit model-specific mappings.
See docs/PROTOCOL.md for source references. No Bluetooth I/O in this module.
"""
from dataclasses import dataclass
from enum import IntEnum
import struct


class Command(IntEnum):
    BATTERY = 0x0106
    NOISE = 0x010C
    FEATURES = 0x010D
    EQUALIZER = 0x010F
    SET_FEATURE = 0x0403
    SET_NOISE = 0x0404
    SET_EQUALIZER = 0x0406


@dataclass(frozen=True)
class Frame:
    command: int
    payload: bytes


def encode(command: int, payload: bytes = b"") -> bytes:
    # Length field is ONE byte and includes seven bytes preceding the payload.
    if not 0 <= command <= 0xFFFF:
        raise ValueError("command must fit uint16")
    if len(payload) > 248:
        raise ValueError("Melody payload exceeds the one-byte frame length")
    return struct.pack("<BBBBHBH", 0xAA, 7 + len(payload), 0, 0,
                       command, 0xF0, len(payload)) + payload


class Decoder:
    """Incremental, bounded decoder; handles fragments, coalescing and noise."""
    def __init__(self):
        self.buffer = bytearray()

    def feed(self, chunk: bytes) -> list[Frame]:
        # Consume incrementally: even an arbitrarily large input cannot accumulate.
        result = []
        for byte in chunk:
            self.buffer.append(byte)
            while self.buffer:
                if self.buffer[0] != 0xAA:
                    del self.buffer[0]
                    continue
                if len(self.buffer) < 2:
                    break
                total = self.buffer[1] + 2
                if total < 9:
                    del self.buffer[0]
                    continue
                if len(self.buffer) < 9:
                    break
                length = int.from_bytes(self.buffer[7:9], "little")
                # Byte 6 is a transaction/event sequence, not a fixed marker.
                # Official X3 captures use changing values for notifications
                # and echo the request sequence in replies.
                if self.buffer[2:4] != b"\x00\x00" or length != total - 9:
                    del self.buffer[0]
                    continue
                if len(self.buffer) < total:
                    break
                result.append(Frame(int.from_bytes(self.buffer[4:6], "little"),
                                    bytes(self.buffer[9:total])))
                del self.buffer[:total]
        return result


# Enco X3 only. These are protocol indices, NOT response values.
NOISE_INDICES = {"off": 0, "transparency": 8, "smart": 7,
                 "light": 6, "moderate": 5, "deep": 4}
NOISE_RESPONSE = {"off": (8, 0), "transparency": (0, 1),
                  "smart": (0x80, 0), "light": (0x40, 0),
                  "moderate": (0x20, 0), "deep": (0x10, 0)}
PRESETS = ((0, "至臻原音"), (1, "高清解析"), (2, "纯享人声"),
           (3, "澎湃低音"), (7, "丹拿特调"))
FEATURES = {"wear": 0x04, "dual": 0x11}


def noise_payload(mode: str) -> bytes:
    index = NOISE_INDICES[mode]
    data = bytearray(3 + index // 8)
    data[:2] = b"\x01\x01"
    data[2 + index // 8] = 1 << (index % 8)
    return bytes(data)


def parse_noise(payload: bytes) -> str | None:
    if payload and payload[0] in (0, 3):
        payload = payload[1:]
    if len(payload) < 4:
        return None
    if payload[0] == 4:
        return "smart"
    extra = {(2, 0): "smart", (4, 0): "transparency", (0, 2): "vocal", (0, 8): "adaptive"}
    if tuple(payload[2:4]) in extra:
        return extra[tuple(payload[2:4])]
    return next((mode for mode, values in NOISE_RESPONSE.items()
                 if values == tuple(payload[2:4])), None)


@dataclass(frozen=True)
class Battery:
    percent: int
    charging: bool


def parse_battery(payload: bytes, *, partial=False) -> dict[str, Battery | None]:
    result = {} if partial else dict.fromkeys(("left", "right", "case"))
    if len(payload) >= 2 and payload[0] == 0:
        payload = payload[1:]
    if not payload:
        return result
    if payload[0] == 4 and len(payload) >= 7:
        for i, key in enumerate(("left", "right", "case")):
            percent, charging = payload[1 + 2*i:3 + 2*i]
            result[key] = Battery(percent, bool(charging)) if 0 < percent <= 100 else None
        return result
    count = payload[0]
    if len(payload) % 2:
        if not (0 < count <= 8 and len(payload) >= 1 + count * 2):
            return result
        payload = payload[1:1 + count*2]
    for i in range(0, len(payload) - 1, 2):
        component, raw = payload[i:i+2]
        percent = raw & 0x7F
        if component in (1, 2, 3):
            key = ("left", "right", "case")[component-1]
            result[key] = Battery(percent, bool(raw & 0x80)) if 0 < percent <= 100 else None
    return result
