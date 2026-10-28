"""Wire-level regressions for the independently ported Melody codec."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest
from encolite.protocol import (Command, Decoder, Frame, PRESETS, encode,
                              noise_payload, parse_battery, parse_noise)
from encolite.session import DemoSession


class CodecTests(unittest.TestCase):
    def test_known_deep_noise_wire_packet(self):
        self.assertEqual(encode(Command.SET_NOISE, noise_payload("deep")),
                         bytes.fromhex("AA 0A 00 00 04 04 F0 03 00 01 01 10"))

    def test_every_fragment_boundary_and_coalesced_frames(self):
        packet = encode(Command.BATTERY) + encode(Command.SET_EQUALIZER, b"\x07")
        expected = [Frame(Command.BATTERY, b""), Frame(Command.SET_EQUALIZER, b"\x07")]
        for split in range(len(packet)+1):
            decoder = Decoder()
            self.assertEqual(decoder.feed(packet[:split]) + decoder.feed(packet[split:]), expected)

    def test_payload_header_does_not_break_frame(self):
        packet = encode(0x1234, bytes((0xAA,))*248)
        self.assertEqual(Decoder().feed(packet), [Frame(0x1234, bytes((0xAA,))*248)])
        with self.assertRaises(ValueError):
            encode(0x1234, b"x"*249)

    def test_invalid_length_and_reserved_header_recover(self):
        bad = bytearray(encode(0x0106))
        bad[2] = 1
        decoder = Decoder()
        self.assertEqual(decoder.feed(b"junk\xaa\x00"+bad+encode(0x0106)), [Frame(0x0106,b"")])
        malformed = bytearray(encode(0x0106, b"abc"))
        malformed[7] = 250
        self.assertEqual(Decoder().feed(malformed+encode(0x0106)), [Frame(0x0106,b"")])

    def test_variable_sequence_replies_and_notifications_at_every_fragment_boundary(self):
        # Exact non-motion frames observed on the owned X3 official session.
        reply = bytes.fromhex('aa0800000d84d5010000')
        notice = bytes.fromhex('aa0a00000a05580300010101')
        expected = [Frame(0x840D,b'\x00'),Frame(0x050A,b'\x01\x01\x01')]
        packet = reply+notice
        for split in range(len(packet)+1):
            decoder = Decoder()
            self.assertEqual(decoder.feed(packet[:split])+decoder.feed(packet[split:]),expected)
        zero_sequence = bytearray(reply)
        zero_sequence[6] = 0
        self.assertEqual(Decoder().feed(zero_sequence),expected[:1])

    def test_unfinished_and_noise_buffer_is_bounded(self):
        decoder = Decoder()
        decoder.feed(b"\xaa\xff" + b"\x00"*2_000_000)
        self.assertLessEqual(len(decoder.buffer), 256)
        decoder.feed(b"\xaa\x0a\x00")
        self.assertEqual(len(decoder.buffer), 3)

    def test_notification_and_query_response_noise(self):
        self.assertEqual(parse_noise(bytes((0,1,1,0,1))), "transparency")
        self.assertEqual(parse_noise(bytes((3,1,1,0x10,0))), "deep")
        self.assertEqual(noise_payload("transparency"), b"\x01\x01\x00\x01")
        self.assertIsNone(parse_noise(b"\x00"))
        self.assertIsNone(parse_noise(b"\x00\x01\x01\xff\xff"))

    def test_battery_charging_missing_and_legacy_format(self):
        b = parse_battery(bytes((0,3,1,86,2,0x80|82,3,0)))
        self.assertEqual(b["left"].percent, 86)
        self.assertTrue(b["right"].charging)
        self.assertIsNone(b["case"])
        old = parse_battery(bytes((4,55,1,75,0,0,0)))
        self.assertEqual(old["left"].percent, 55)
        self.assertTrue(old["left"].charging)
        self.assertIsNone(old["case"])

    def test_battery_missing_count_and_invalid_values(self):
        self.assertEqual(parse_battery(bytes((1,52,2,64)))["right"].percent, 64)
        self.assertTrue(all(x is None for x in parse_battery(bytes((3,1,127,2,0,3,101))).values()))
        for length in range(8):
            parse_battery(bytes((0,3,1,80,2,70,3,60))[:length])


class SessionTests(unittest.TestCase):
    def test_set_and_readback_all_modes_and_presets(self):
        session = DemoSession()
        for mode in ("off","smart","transparency","light","moderate","deep"):
            session.set_noise(mode)
            self.assertEqual(session.noise, mode)
        for preset, _ in PRESETS:
            session.set_preset(preset)
            self.assertEqual(session.preset,preset)
        for enabled in (False, True):
            session.set_feature("wear", enabled)
            session.set_feature("dual", enabled)
            self.assertEqual(session.features, {4:enabled,17:enabled})

    def test_disconnect_rejects_changes_and_trace_is_bounded(self):
        session = DemoSession()
        session.transport.connected = False
        with self.assertRaises(ConnectionError):
            session.set_noise("deep")
        self.assertEqual(session.noise,"smart")
        session.transport.connected = True
        for _ in range(40):
            session.refresh()
        self.assertEqual(len(session.trace),32)

    def test_unsupported_preset_does_not_mutate_state(self):
        session = DemoSession()
        with self.assertRaises(ValueError):
            session.set_preset(5)
        self.assertEqual(session.preset,0)


if __name__ == "__main__":
    unittest.main()
