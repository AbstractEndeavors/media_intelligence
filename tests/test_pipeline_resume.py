import tempfile, unittest
from pathlib import Path
from media_intelligence import MediaPipeline


class Resume(unittest.TestCase):
    def test_source_changes_and_same_basename_do_not_reuse_body(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            a = root / "one" / "same.txt"
            b = root / "two" / "same.txt"
            for p, text in [(a, "First document"), (b, "Second document")]:
                p.parent.mkdir()
                p.write_text(text)
            out = str(root / "artifacts")
            first = MediaPipeline(str(a), out_root=out).extract().persist()
            second = MediaPipeline(str(b), out_root=out).extract().persist()
            self.assertNotEqual(first.item.media_id, second.item.media_id)
            self.assertEqual(second.item.text, "Second document")
            resumed = MediaPipeline(str(a), out_root=out)
            self.assertEqual(resumed.item.text, "First document")
            a.write_text("Changed document")
            changed = MediaPipeline(str(a), out_root=out).extract()
            self.assertNotEqual(changed.item.media_id, first.item.media_id)
            self.assertEqual(changed.item.text, "Changed document")

    def test_file_store_rejects_parent_id(self):
        from media_intelligence.persist import FileStore

        with tempfile.TemporaryDirectory() as folder:
            store = FileStore(folder)
            with self.assertRaises(ValueError):
                store.collection_dir("..")
