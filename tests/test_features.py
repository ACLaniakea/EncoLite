import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import unittest
from encolite.oppo_features import *
from encolite.live_session import LiveSession,Channel,RequestTimeout,model_for
from encolite.protocol import Frame,parse_noise
import queue
import threading

class FeatureTests(unittest.TestCase):
    def test_x3_real_custom_response_and_truncation(self):
        data=bytes.fromhex('00 02 00 FA 06 04 06 E5 9D 87 E8 A1 A1 06 3E 00 05 FA 00 04 E8 03 03 A0 0F 05 40 1F 03 80 3E 02 00 FA 06 05 06 E9 80 9A E9 80 8F 06 3E 00 01 FA 00 03 E8 03 05 A0 0F 04 40 1F 06 80 3E 04')
        entries=parse_custom(data)
        self.assertEqual(entries[0].gains,(5,4,3,5,3,2))
        self.assertEqual(entries[1].name,'通透')
        self.assertEqual(entries[0].minimum,-6)
        for length in range(2,len(data)):
            with self.assertRaises(ValueError): parse_custom(data[:length])

    def test_custom_round_trip_utf8_signed_and_limits(self):
        entry=CustomEQ(9,'轻柔', (62,250,1000),(-6,0,6))
        encoded=custom_payload(2,entry)
        self.assertEqual(parse_custom(b'\0\1\1'+encoded[1:])[0],CustomEQ(9,'轻柔',(62,250,1000),(-6,0,6),selected=True))
        for entry in (CustomEQ(0,'空 格',(62,),(0,)),CustomEQ(0,'Valid',(62,),(7,)),CustomEQ(0,'A'*240,(62,),(0,))):
            with self.assertRaises(ValueError): custom_payload(1,entry)

    def test_multi_wire_and_partial_response(self):
        response=bytes.fromhex('00 01 8C 66 4E B1 16 10 0D 02 01 03')+b'ABC'
        device=parse_multi(response)[0]
        self.assertEqual(device['address'],'10:16:B1:4E:66:8C')
        self.assertTrue(device['current'])
        self.assertEqual(multi_payload('priority',device['address']),bytes.fromhex('04 01 10 16 B1 4E 66 8C'))
        self.assertEqual(multi_payload('auto'),b'\4\0')
        for length in range(2,len(response)):
            with self.assertRaises(ValueError): parse_multi(response[:length])
        with self.assertRaises(ValueError): multi_payload('disconnect','wrong')
        self.assertEqual(parse_priority(bytes.fromhex('00 01 01 8C 66 4E B1 16 10')),device['address'])

    def test_vocal_smart_strength_and_short_codec(self):
        self.assertEqual(parse_noise(bytes.fromhex('00 01 01 00 02')),'vocal')
        self.assertEqual(parse_noise(bytes.fromhex('03 04 01 10 00')),'smart')
        self.assertEqual(parse_codec(b'\0\2'),'AAC')
        self.assertEqual(parse_codec(bytes.fromhex('00 02 00 00 02 01')),'AAC')
        self.assertEqual(parse_wear(bytes.fromhex('00 03 01 07 02 07 03 04')),{1:'已佩戴',2:'已佩戴'})

    def test_whitelist_holes_unknown_and_dedicated_protocol_gates(self):
        s=LiveSession(); s.connected=True; s.profile=model_for('067410',''); s.bitmap=bytes.fromhex('FF777AEEE68F8E04')
        self.assertEqual(s.profile['noise']['vocal'],9)
        self.assertEqual([p['id'] for p in s.presets],[0,1,2,3,7])
        self.assertIsNone(model_for('FFFFFF','OPPO Enco X3'))
        self.assertTrue(s.supported('spatial_audio'))
        self.assertFalse(s.supported('spatial'))
        self.assertTrue(s.supported('multi'))
        self.assertFalse(s.supported('multi_write'))
        self.assertTrue(s.supported('hearing'))
        s.bitmap=b'\x80'
        self.assertFalse(s.supported('hearing'))
        self.assertFalse(s.supported('custom'))
        self.assertFalse(s.feature_available('dual'))

    def test_old_model_transparency_parent_index_and_noop_spine(self):
        import json
        models=json.loads(Path(__file__).resolve().parents[1].joinpath('encolite/oppo_models.json').read_text('utf-8'))
        self.assertEqual(sum(p.get('brand')=='OPPO' for p in models),56)
        self.assertEqual(sum(p.get('brand')=='OnePlus' for p in models),32)
        for p in models:
            s=LiveSession(); s.connected=True; s.profile=p; s.bitmap=b'\xff'*9
            self.assertFalse(s.supported('spine'))
        self.assertEqual(model_for('067410','')['noise']['off'],0)

    def test_notification_updates_and_stale_generation(self):
        s=LiveSession(); s._receive(Frame(0x0204,bytes.fromhex('02 02 01 07 02 04')),0)
        self.assertEqual(s.wear_state,{1:'已佩戴',2:'在盒中'})
        s._receive(Frame(0x8202,bytes.fromhex('00 F2')),0)
        self.assertIn('multi',s.dirty)
        s._generation=1
        s._receive(Frame(0x810F,b'\0\7'),0)
        self.assertEqual(s.preset,-1)

class Transport:
    def __init__(self): self.closed=False; self.packets=queue.Queue()
    def write(self,data): pass
    def read(self,timeout):
        try: return self.packets.get(timeout=.01)
        except queue.Empty: return b''
    def close(self): self.closed=True

class ChannelTests(unittest.TestCase):
    def test_timeout_closes_channel_and_rejects_later_requests(self):
        t=Transport(); c=Channel(t,lambda frame:None,lambda error:None,[])
        try:
            with self.assertRaises(RequestTimeout): c.request(0x010F,timeout=.025)
            self.assertTrue(t.closed)
            with self.assertRaises(ConnectionError): c.request(0x010F,timeout=.025)
        finally: c.close(); c.reader.join(1)


class ImageTests(unittest.TestCase):
    def test_catalog_uses_exact_product_ids_and_neutral_fallback(self):
        from encolite.images import product_image
        root=Path(__file__).resolve().parents[1]
        self.assertEqual(product_image(root,'067410').name,'067410.png')
        self.assertNotEqual(product_image(root,'067410'),product_image(root,'063C10'))
        self.assertEqual(product_image(root,'FFFFFF').name,'device-neutral.svg')
        self.assertEqual(product_image(root,'../../067410').name,'device-neutral.svg')
        catalog=__import__('json').loads((root/'ui/assets/models/manifest.json').read_text('utf-8'))
        self.assertEqual(sum(p['name'].startswith('OPPO') for p in catalog.values()),31)
        self.assertEqual(sum(p['name'].startswith('OnePlus') for p in catalog.values()),4)
        for key,record in catalog.items():
            image=product_image(root,key)
            self.assertEqual(image.name,record['file'])
            self.assertTrue(image.read_bytes().startswith(b'\x89PNG'))

    def test_per_model_override_does_not_leak_to_other_models(self):
        import tempfile
        from encolite.images import product_image
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            override=Path(temporary)/'067410/product.png'
            override.parent.mkdir();override.write_bytes(b'custom')
            self.assertEqual(product_image(root,'067410',temporary),override)
            self.assertNotEqual(product_image(root,'063C10',temporary),override)

if __name__=='__main__': unittest.main()
