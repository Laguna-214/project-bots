"""Pinned GGUF lifecycle, with real local filesystem test transport."""
import hashlib, json, tempfile, unittest
from pathlib import Path
from project_bots import llama_store

class StoreTests(unittest.TestCase):
    def test_hash_verified_import_and_remove_preserve_unrelated_files(self):
        with tempfile.TemporaryDirectory() as t:
            h=Path(t); data=b'GGUF'+b'\x00'*200
            src=h/'source';src.write_bytes(data)
            digest=hashlib.sha256(data).hexdigest()
            entry={'url':src.as_uri(),'sha256':digest,'size':len(data),'context':2048,'capabilities':['tools'],'model_info':{}}
            result=llama_store.apply_model(h,'tiny',entry,'download',allow_file=True)
            p=Path(result['path']);self.assertEqual(p.read_bytes(),data)
            self.assertTrue(result['managed'])
            self.assertIn('[tiny]',(h/'.local/share/project-bots-llama/models.ini').read_text())
            keep=p.parent/'private-report';keep.write_text('keep')
            llama_store.apply_model(h,'tiny',result,'delete')
            self.assertFalse(p.exists());self.assertEqual(keep.read_text(),'keep')
            self.assertNotIn('[tiny]',(h/'.local/share/project-bots-llama/models.ini').read_text())

    def test_bad_hash_never_publishes_model_or_preset(self):
        with tempfile.TemporaryDirectory() as t:
            h=Path(t);src=h/'source';src.write_bytes(b'GGUFbad')
            entry={'url':src.as_uri(),'sha256':'a'*64,'size':7,'context':2048}
            with self.assertRaises(ValueError):llama_store.apply_model(h,'tiny',entry,'download',allow_file=True)
            self.assertFalse((h/'.local/share/project-bots-llama/models.ini').exists())

    def test_existing_model_reimport_checks_bytes_not_only_registry(self):
        with tempfile.TemporaryDirectory() as t:
            h=Path(t);src=h/'source';data=b'GGUF'+b'x'*20;src.write_bytes(data)
            entry={'url':src.as_uri(),'sha256':hashlib.sha256(data).hexdigest(),'size':len(data),'context':2048}
            result=llama_store.apply_model(h,'tiny',entry,'download',allow_file=True)
            Path(result['path']).write_bytes(b'corrupted')
            with self.assertRaises(ValueError):llama_store.apply_model(h,'tiny',entry,'download',allow_file=True)

    def test_preserved_model_deletion_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(ValueError):llama_store.apply_model(Path(t),'original',{'managed':False},'delete')
