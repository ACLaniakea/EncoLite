import unittest
from encolite.model_catalog import is_earbud_candidate,models

class DeviceFilterTests(unittest.TestCase):
    def test_rejects_same_brand_non_headphones_even_if_renamed(self):
        for name,cod in [('OPPO Find X8',0x020c),('OnePlus 13',0x020c),('一加 Watch',0x0704),
                         ('OPPO Enco X3',0x010c),('OnePlus Keyboard',0x0540),
                         ('OPPO Speaker',0x0414),('OPPO Enco X3',0x0414),('OPPO TV',0x043c)]:
            with self.subTest(name=name,cod=cod):self.assertFalse(is_earbud_candidate(name,cod))

    def test_headsets_and_headphones_keep_both_supported_brands(self):
        for cod in (0x240404,0x200408,0x240418):
            for name in ('OPPO Enco X3','OnePlus Buds Pro 3','一加 Buds Ace 2','OnePlus renamed'):
                with self.subTest(name=name,cod=cod):self.assertTrue(is_earbud_candidate(name,cod))
            for name in ('Sony WF-1000XM5','AirPods Pro','realme Buds','Concord speaker'):
                self.assertFalse(is_earbud_candidate(name,cod))

    def test_missing_class_requires_an_explicit_earbud_identity(self):
        for model in models():
            for name in [model['name'],*model.get('aliases',[])]:
                with self.subTest(name=name):self.assertTrue(is_earbud_candidate(name,0))
        for name in ('OPPO Enco X9','OnePlus Buds 9','一加 Buds Ace 9','OPPO O-Free'):
            self.assertTrue(is_earbud_candidate(name,0x0400),name)
        for name in ('OPPO Find X8','OnePlus 13','一加手机','OPPO TV','OPPO','encore keyboard','My OnePlus',None,''):
            self.assertFalse(is_earbud_candidate(name,0),name)
