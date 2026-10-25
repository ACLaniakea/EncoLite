"""Real Melody session: one reader, serialized requests, confirmed state only."""
from collections import deque
import threading
import time

from .protocol import Decoder, encode, parse_battery, parse_noise, FEATURES
from .extended_session import ExtendedSession


class RequestTimeout(ConnectionError):
    pass


class Channel:
    def __init__(self, transport, on_frame, on_disconnect, trace):
        self.transport, self.on_frame, self.on_disconnect, self.trace = transport, on_frame, on_disconnect, trace
        self.decoder = Decoder()
        self.closed = threading.Event()
        self.gate = threading.Lock()
        self.pending_lock = threading.Lock()
        self.pending = None
        self.reader = threading.Thread(target=self._read, name="EncoLite-Bluetooth", daemon=True)
        self.reader.start()

    def _read(self):
        try:
            while not self.closed.is_set():
                for frame in self.decoder.feed(self.transport.read(1)):
                    self.trace.append(f"RX {encode(frame.command, frame.payload).hex(' ').upper()}")
                    try:
                        self.on_frame(frame)
                    except (ValueError, UnicodeError, IndexError) as error:
                        self.trace.append(f"忽略格式异常的响应 {frame.command:04X}: {error}")
                    with self.pending_lock:
                        if self.pending and frame.command == self.pending[0]:
                            self.pending[2].append(frame.payload)
                            self.pending[1].set()
        except (OSError, ConnectionError) as error:
            if not self.closed.is_set():
                self.close()
                self.on_disconnect(str(error))

    def send_only(self, command, payload=b""):
        if self.closed.is_set():
            raise ConnectionError("耳机未连接")
        packet = encode(command, payload)
        self.trace.append(f"TX {packet.hex(' ').upper()}")
        self.transport.write(packet)

    def request(self, command, payload=b"", timeout=2, empty_ok=False):
        with self.gate:
            event, result = threading.Event(), []
            with self.pending_lock:
                self.pending = (command | 0x8000, event, result)
            try:
                self.send_only(command, payload)
                if not event.wait(timeout) or not result:
                    # No transaction id exists in Melody. Close the stream so
                    # a late reply cannot satisfy a later request of this opcode.
                    self.close()
                    raise RequestTimeout(f"耳机无响应（{command:04X}），请重新连接")
                data = result[0]
                if not data and empty_ok:
                    return data
                if not data or data[0] != 0:
                    status = f"{data[0]:02X}" if data else "空响应"
                    raise ValueError(f"耳机拒绝操作（{command:04X} / {status}）")
                return data
            finally:
                with self.pending_lock:
                    self.pending = None

    def close(self):
        self.closed.set()
        self.transport.close()
        with self.pending_lock:
            if self.pending:
                self.pending[1].set()


from .model_catalog import model_for,canonical_product_id,connection_attempts


def bitmap_has(bitmap, bit):
    return bit // 8 < len(bitmap) and bool(bitmap[bit // 8] & (1 << bit % 8))


class LiveSession(ExtendedSession):
    is_live = True

    def __init__(self, on_changed=None):
        self.on_changed = on_changed
        self.connected = False
        self.ready = False
        self.device_name = "未连接耳机"
        self.product_id = ""
        self.firmware = ""
        self.noise = ""
        self.preset = -1
        self.features = {}
        self.battery = {}
        self.bitmap = b""
        self.profile = None
        self.game_sound = None
        self.trace = deque(maxlen=32)
        self.error = ""
        self.noise_error = None
        self.channel = None
        self.cancel = threading.Event()
        self._generation = 0
        self.registered_events = set()
        self._last_updates = {}
        self.reset_extended()

    def _changed(self):
        if self.on_changed:
            self.on_changed()

    @property
    def noise_modes(self):
        return self.profile.get("noise", {}) if self.profile and bitmap_has(self.bitmap, 8) else {}

    @property
    def presets(self):
        if not self.profile or not bitmap_has(self.bitmap, 10):
            return []
        return [*self.profile.get("presets", []), *({"id":e.id,"name":e.name,"custom":True} for e in self.custom_entries)]

    @property
    def eq_available(self):
        if not self.connected or not self.presets:
            return False
        if self.profile.get("eq_mutex") and bitmap_has(self.bitmap, 49):
            return self.game_sound == 0
        return True

    def connect(self, device, cancel=None):
        from .bluetooth_windows import Rfcomm
        self.disconnect()
        self.cancel = cancel if cancel is not None else threading.Event()
        generation = self._generation
        self.device_name = device.name
        self.error = ""
        self._changed()
        failure = None
        # Resolve the catalog's service UUID, then bounded legacy fallbacks.
        # Every path must pass the same product/capability handshake.
        attempts = connection_attempts(device.name)
        for service, port in attempts:
            if self.cancel.is_set() or generation != self._generation:
                raise ConnectionAbortedError("连接已取消")
            transport = Rfcomm()
            channel = None
            try:
                transport.connect(device, service=service, channel=port, cancel=self.cancel)
                channel = Channel(transport,
                    lambda frame: self._receive(frame, generation),
                    lambda error: self._lost(error, generation), self.trace)
                self.channel = channel
                product = channel.request(0x0103)
                if len(product) != 4:
                    raise ValueError("耳机产品标识格式异常")
                self.product_id = f"{int.from_bytes(product[1:], 'little'):06X}"
                self.product_id=canonical_product_id(self.product_id)
                self.profile = model_for(self.product_id, device.name)
                if self.profile:
                    self.device_name = self.profile["name"]
                capabilities = channel.request(0x0100)
                if len(capabilities) < 2:
                    raise ValueError("耳机能力信息无效")
                self.bitmap = capabilities[1:]
                self.connected = True
                if bitmap_has(self.bitmap, 0):
                    firmware = channel.request(0x0105)
                    if len(firmware) >= 3:
                        raw = firmware[2:].decode("utf-8", "replace").strip("\x00 ")
                        parts = raw.split(",")
                        self.firmware = ".".join(str(int(parts[i])) for i in range(2, len(parts), 3)) if len(parts) >= 3 and len(parts) % 3 == 0 and all(parts[i].isdigit() for i in range(2,len(parts),3)) else raw
                self.refresh()
                self._register_notifications()
                if self.cancel.is_set():
                    raise ConnectionAbortedError("连接已取消")
                self.ready=True
                self.error = ""
                self._changed()
                return
            except (OSError, ConnectionError, ValueError) as error:
                failure = error
                self.connected = False
                self.ready=False
                if channel:
                    channel.close()
                    channel.reader.join(timeout=1.5)
                else:
                    transport.close()
                self.channel = None
        self.error = str(failure or "未找到可用的耳机控制服务")
        self._changed()
        raise ConnectionError(self.error)

    def _lost(self, error, generation):
        if generation == self._generation:
            self.connected = False
            self.ready=False
            self.noise=""
            self.preset=-1
            self.features={}
            self.battery = {}
            self.error = error
            self._changed()

    def _receive(self, frame, generation):
        if generation != self._generation:
            return
        command, data = frame.command, frame.payload
        if command == 0x8404:
            self.noise_error = data[0] if data and data[0] else None
            return
        if command in (0x0204, 0x8202):
            if command == 0x8202:
                if len(data) < 2 or data[0] != 0:
                    return
                data = data[1:]
            if not data:
                return
            event, data = data[0], data[1:]
            if event == 1:
                patch = parse_battery(data, partial=True)
                if not patch:
                    return
                self.battery = {**self.battery, **patch}
                self._last_updates[0x0106] = time.monotonic()
            elif event == 3:
                parsed = self.parse_noise_state(data)
                if parsed:
                    self.noise = parsed
                    self._last_updates[0x010C] = time.monotonic()
            elif event == 2:
                from .oppo_features import parse_wear
                self.wear_state.update(parse_wear(data))
                self._last_updates[0x0109] = time.monotonic()
            elif event == 5 and data:
                self.features[self.feature_id('game')]=bool(data[0])
            elif event in (6,0xF2):
                # Process on the serialized worker; never issue requests on reader.
                self.dirty.add('multi')
            else:
                return
            self._changed()
            return
        if command == 0x0504:
            if data:
                self.preset = data[1] if len(data) > 1 and data[0] == 0 else data[0]
                self._last_updates[0x010F] = time.monotonic()
                self._changed()
            return
        if not data or data[0] != 0:
            return
        if command == 0x8106:
            self.battery = parse_battery(data)
        elif command == 0x810C:
            mode = self.parse_noise_state(data)
            if mode:
                self.noise = mode
        elif command == 0x810F and len(data) >= 2:
            self.preset = data[1]
        elif command == 0x810D and len(data) >= 2 and len(data) >= 2 + data[1]*2:
            self.features = {data[i]: bool(data[i+1]) for i in range(2, 2+data[1]*2, 2)}
        elif command == 0x812B and len(data) >= 2:
            self.game_sound = data[1]
        elif self.extended_receive(command,data):
            pass
        else:
            return
        self._last_updates[command & 0x7FFF] = time.monotonic()
        self._changed()

    def parse_noise_state(self,data):
        mode=parse_noise(data)
        # Three-mode models call their only ANC setting "NC". Keep the decoded
        # physical ANC state without exposing an unsupported strength as Smart.
        modes=self.noise_modes
        if mode in ('smart','deep','moderate','light','adaptive') and mode not in modes and 'nc' in modes:
            return 'nc'
        return mode

    def request(self, command, payload=b"", **kwargs):
        if not self.connected or not self.channel:
            raise ConnectionError("耳机未连接")
        try:
            return self.channel.request(command, payload, **kwargs)
        except (OSError, RequestTimeout) as error:
            self._lost(str(error), self._generation)
            raise

    def refresh(self):
        # Consume before reading; notifications received during the read must
        # survive for the next pass rather than getting cleared at its end.
        self.dirty.discard('multi')
        self.request(0x0106)
        if self.noise_modes:
            self.request(0x010C, b"\x01\x01")
        if self.presets:
            self.request(0x010F)
        if self.profile and bitmap_has(self.bitmap, 7):
            self.request(0x010D,self.feature_query())
        if self.profile and (self.supported('game_sound') or self.profile.get("eq_mutex")) and bitmap_has(self.bitmap, 49):
            try:
                self.request(0x012B)
            except ValueError:
                self.game_sound = None  # Fail closed when mutex state is unknown.
        self.extended_refresh()

    def refresh_due(self, interactive, *, force=False, now=None):
        if not self.connected or not self.ready:
            return
        now=time.monotonic() if now is None else now
        def read(command, interval, payload=b'', optional=None, forced=True):
            if not ((force and forced) or now-self._last_updates.get(command,float('-inf'))>=interval):
                return
            try:
                self.request(command,payload)
            except ValueError:
                if optional:
                    self.unavailable.add(optional)
                if command==0x012B:
                    self.game_sound=None
                # Optional/temporarily refused states should not be hammered.
            self._last_updates[command]=time.monotonic()
        read(0x0106,2 if interactive else 10)
        if interactive:
            if self.noise_modes:
                read(0x010C,2,b'\x01\x01')
            if self.command_supported(0x0109):
                read(0x0109,2)
            if self.presets:
                read(0x010F,4)
            if self.profile and bitmap_has(self.bitmap,7):
                read(0x010D,10,self.feature_query())
            if self.supported('spatial_audio'):
                read(0x012A,10,optional='spatial_audio')
            if self.supported('bass'):
                read(0x0124,10,optional='bass')
            if self.profile and (self.supported('game_sound') or self.profile.get('eq_mutex')) and bitmap_has(self.bitmap,49):
                read(0x012B,10)
            if self.supported('custom'):
                read(0x0122,120,b'\x01\x05',optional='custom',forced=False)
            if self.command_supported(0x0114):
                read(0x0114,30)
        dirty='multi' in self.dirty
        if dirty or (interactive and (force or now-self._last_updates.get(0x0112,float('-inf'))>=30)):
            self.dirty.discard('multi')
            if self.supported('multi'):
                read(0x0112,0,optional='multi')
                if self.command_supported(0x0132):
                    read(0x0132,0)

    def _register_notifications(self):
        events = self.request(0x0200)
        if len(events) < 2 or len(events) < events[1]+2:
            return
        selected=set(events[2:2+events[1]]) & {1,2,3,5,6,0xF2}
        if self.command_supported(0x0205) and selected:
            try:
                reply=self.request(0x0205,bytes((len(selected),*sorted(selected))),empty_ok=True)
                if len(reply)<=1:
                    self.registered_events=selected
                elif len(reply)>=2+reply[1]*2:
                    self.registered_events={reply[i] for i in range(2,2+reply[1]*2,2)
                                            if reply[i] in selected and reply[i+1]==0}
                selected-=self.registered_events
            except ValueError:
                pass
        for event in selected:
            try:
                self.request(0x0201, bytes((event,)))
                self.registered_events.add(event)
            except ValueError:
                pass

    def set_noise(self, mode):
        if mode not in self.noise_modes:
            raise ValueError("这副耳机不支持该降噪档位")
        index = self.noise_modes[mode]
        payload = bytearray(3 + index//8)
        payload[:2] = b"\x01\x01"
        payload[2+index//8] = 1 << index%8
        if not self.connected or not self.channel:
            raise ConnectionError("耳机未连接")
        # Upstream sends ANC without requiring a 0x8404 ACK; actual state wins.
        self.noise_error = None
        self.channel.send_only(0x0404, payload)
        for _ in range(3):
            if self.cancel.wait(.15):
                raise ConnectionAbortedError("操作已取消")
            if self.noise_error is not None:
                raise ValueError(f"耳机当前状态不允许切换，请确认已佩戴（{self.noise_error:02X}）")
            self.request(0x010C, b"\x01\x01")
            if self.noise == mode:
                return
        raise ValueError("耳机未切换到该模式，已显示实际状态")

    def set_preset(self, preset):
        if preset not in {p["id"] for p in self.presets}:
            raise ValueError("这副耳机不支持该音效")
        if not self.eq_available:
            if self.game_sound and self._blocks('eq'):
                self.set_game_sound(0)
            else:
                raise ValueError("当前音效状态不允许切换均衡器")
        self.request(0x0406, bytes((preset,)))
        self.cancel.wait(.15)
        self.request(0x010F)
        if self.preset != preset:
            raise ValueError("音效未生效，已显示耳机实际设置")

    def disconnect(self):
        if self.finding and self.connected and self.channel:
            try:
                self.channel.send_only(0x0400,b'\x00')
            except (OSError,ConnectionError):
                pass
        self.cancel.set()
        self._generation += 1
        channel, self.channel = self.channel, None
        self.connected = False
        self.ready=False
        if channel:
            channel.close()
            if channel.reader is not threading.current_thread():
                channel.reader.join(timeout=1.5)
        self.battery = {}
        self.features = {}
        self.noise = ""
        self.preset = -1
        self.bitmap = b""
        self.game_sound = None
        self.registered_events = set()
        self._last_updates = {}
        self.product_id=''
        self.firmware=''
        self.profile=None
        self.reset_extended()
        self._changed()

    def close(self):
        self.on_changed = None
        self.disconnect()
