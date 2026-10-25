"""OnePlus identity, services and real model-dependent payloads, without hardware writes."""
import importlib.util,json,sys,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from encolite.model_catalog import models,model_for,canonical_product_id,is_candidate_name,connection_attempts,MELODY,LEGACY
from encolite.live_session import LiveSession
from encolite.protocol import Battery

class OnePlusTests(unittest.TestCase):
    def session(self,identifier):
        session=LiveSession();session.connected=True;session.profile=model_for(identifier,'');session.product_id=identifier
        session.device_name=session.profile['name'];session.bitmap=b'\xff'*9;session.game_sound=0
        return session

    def test_catalog_has_exact_upstream_brands_and_all_profiles(self):
        catalog=models();self.assertEqual(len(catalog),88)
        self.assertEqual(len({p['id'] for p in catalog}),88)
        self.assertEqual({p['brand'] for p in catalog},{'OPPO','OnePlus'})
        self.assertEqual(sum(p['brand']=='OnePlus' for p in catalog),32)
        source=ROOT.parent/'OppoPodsManager-upstream/Assets/Oplus/Data/DeviceModels.json'
        if not source.exists():self.skipTest('upstream source is outside this standalone copy')
        entries=json.loads(source.read_text('utf-8-sig'))['whiteList']
        expected={p['id'].upper() for p in entries if p.get('brand','OPPO').casefold() in ('oppo','oneplus')}
        self.assertEqual({p['id'] for p in catalog},expected)
        spec=importlib.util.spec_from_file_location('model_importer',ROOT/'tools/import_models.py')
        importer=importlib.util.module_from_spec(spec);spec.loader.exec_module(importer)
        for entry in entries:
            if entry.get('brand','OPPO').casefold()=='oneplus':
                with self.subTest(model=entry['name']):self.assertEqual(model_for(entry['id']),importer.profile(entry))

    def test_discovery_accepts_both_brands_and_rejects_others(self):
        for name in ('OPPO Enco X3','oneplus Buds Pro 3','OnePlus Nord Buds 3r','一加 Buds Ace 2','One Plus Buds'):
            self.assertTrue(is_candidate_name(name),name)
        for name in ('realme Buds Air 6','AirPods Pro','Sony WF-1000XM5','',None):self.assertFalse(is_candidate_name(name),name)

    def test_identity_is_strict_and_retains_aliases(self):
        self.assertEqual(model_for('064014','OPPO Enco X3')['name'],'OnePlus Buds Pro 3')
        self.assertEqual(model_for('064014'.lower())['brand'],'OnePlus')
        self.assertIsNone(model_for('FFFFFF','OnePlus Buds Pro 3'))
        self.assertIsNone(model_for('065414garbage','OnePlus Buds 4'))
        self.assertEqual(model_for('065814')['id'],'065854')
        self.assertEqual(model_for('','OnePlus Nord Newton')['id'],'065854')
        self.assertEqual(model_for('','oneplus buds pro 3')['id'],'064014')
        self.assertIsNone(model_for('','OnePlus Buds Pro 3 unknown clone'))

    def test_old_product_ranges_and_legacy_service_precedence(self):
        for start,target in ((0x100100,'060414'),(0x100200,'060814'),(0x108100,'068414'),(0x108200,'068814')):
            for delta in range(3):self.assertEqual(model_for(f'{start+delta:06X}')['id'],target)
        self.assertEqual(connection_attempts('OnePlus Buds Pro')[0],(LEGACY,0))
        self.assertEqual(connection_attempts('OnePlus Buds Pro 3')[0],(MELODY,0))
        self.assertEqual(connection_attempts('OPPO Enco X3')[0],(MELODY,0))
        for name in ('OnePlus Buds Pro','OnePlus Buds Pro 3','OnePlus renamed'):
            attempts=connection_attempts(name);self.assertEqual(len(attempts),len(set(attempts)))
            self.assertEqual({port for _,port in attempts},{0,1,15});self.assertLessEqual(len(attempts),4)
        self.assertEqual(model_for('050414')['support_spp'],False)

    def test_handshake_uses_legacy_uuid_and_normalizes_returned_product(self):
        attempts=[]
        class Transport:
            def connect(self,device,**values):attempts.append(values);return self
            def close(self):pass
        class Channel:
            def __init__(self,*args):self.reader=SimpleNamespace(join=lambda **_:None)
            def request(self,command):return b'\0'+int('100101',16).to_bytes(3,'little') if command==0x0103 else b'\0\0'
            def close(self):pass
        fake=SimpleNamespace(Rfcomm=Transport)
        session=LiveSession()
        with patch.dict(sys.modules,{'encolite.bluetooth_windows':fake}),patch('encolite.live_session.Channel',Channel),patch.object(session,'refresh'),patch.object(session,'_register_notifications'):
            session.connect(SimpleNamespace(name='OnePlus Buds',address=1))
            self.assertEqual(attempts[0]['service'],LEGACY)
            self.assertEqual(session.product_id,'060414');self.assertEqual(session.profile['brand'],'OnePlus');self.assertTrue(session.ready)
            session.disconnect()

    def test_noise_writes_use_model_indices_not_oppo_x3_defaults(self):
        for identifier,mode,expected in [('064014','transparency','010104'),('063C14','transparency','010104'),('065414','adaptive','01010008'),('062414','nc','010101'),('062414','off','010102'),('067410','transparency','01010001')]:
            with self.subTest(model=identifier,mode=mode):
                session=self.session(identifier);session.channel=Mock();session.cancel=Mock();session.cancel.wait.return_value=False
                session.request=lambda *args,mode=mode:setattr(session,'noise',mode)
                session.set_noise(mode);command,payload=session.channel.send_only.call_args.args
                self.assertEqual(command,0x0404);self.assertEqual(bytes(payload),bytes.fromhex(expected))
        session=self.session('064014');session.channel=Mock()
        with self.assertRaises(ValueError):session.set_noise('vocal')
        session.channel.send_only.assert_not_called()

    def test_sparse_presets_and_capability_gates(self):
        session=self.session('064014');self.assertEqual([p['id'] for p in session.presets],[0,1,2,3,7])
        self.assertTrue(session.supported('custom'));self.assertTrue(session.supported('multi'));self.assertTrue(session.supported('spatial_audio'))
        session.bitmap=b'\0'*9
        self.assertFalse(session.supported('custom'));self.assertFalse(session.supported('spatial_audio'));self.assertEqual(session.presets,[]);self.assertFalse(session.noise_modes)
        session=self.session('061C14');self.assertFalse(session.noise_modes);self.assertFalse(session.supported('custom'));self.assertFalse(session.supported('wear'))
        session=self.session('062414')
        self.assertEqual(session.parse_noise_state(bytes.fromhex('0001018000')),'nc')
        self.assertEqual(session.parse_noise_state(bytes.fromhex('0001010800')),'off')
        self.assertEqual(session.parse_noise_state(bytes.fromhex('0001010001')),'transparency')
        self.assertIsNone(session.parse_noise_state(bytes.fromhex('000101FFFF')))

    def test_projection_names_battery_form_and_no_inherited_x3_features(self):
        from encolite.controller import Controller
        from encolite.json_view import JsonView
        from encolite.presentation import JsonPresentation
        for identifier in ('064014','061C14','050C14'):
            session=self.session(identifier);session.battery={'right':Battery(77,True)}
            controller=Controller(session=session,presentation=JsonPresentation());view=JsonView()
            try:
                controller.sync_window(view)
                self.assertEqual(view.model_name,session.profile['name'])
                self.assertEqual(view.can_anc,bool(session.noise_modes))
                self.assertEqual(view.single_battery_key,'right')
                self.assertEqual(view.battery_layout,'SingleBattery' if identifier=='050C14' else 'DualEarWithCase')
                self.assertEqual(view.custom_available,session.supported('custom'))
            finally:controller.close()

if __name__=='__main__':unittest.main()
