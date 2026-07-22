import tempfile
import unittest
from pathlib import Path

from scripts.security.open_04_001_evidence_io import atomic_write_json_new, load_json


class Open04001EvidenceIoTest(unittest.TestCase):
    def test_publishes_once_and_rejects_duplicate_json_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "evidence.json"
            atomic_write_json_new(output, {"state": "first"})
            self.assertEqual("first", load_json(output)["state"])
            with self.assertRaises(FileExistsError):
                atomic_write_json_new(output, {"state": "second"})
            duplicate = root / "duplicate.json"
            duplicate.write_text('{"state":"first","state":"second"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate JSON field"):
                load_json(duplicate)


if __name__ == "__main__":
    unittest.main()
