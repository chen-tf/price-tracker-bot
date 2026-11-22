import csv
import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "convert_backup", Path(__file__).parents[1] / "scripts" / "convert_backup.py"
)
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


class BackupTest(unittest.TestCase):
    def write_csv(self, path, name, rows):
        with (path / f"{name}.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    def fixture(self, path):
        self.write_csv(
            path, "user", [{"id": "123456789012345", "chat_id": "123456789012345", "state": "1"}]
        )
        self.write_csv(
            path,
            "good_info",
            [
                {
                    "id": "123",
                    "name": "商品's\n名稱",
                    "price": "1000",
                    "stock_state": "1",
                    "state": "1",
                }
            ],
        )
        self.write_csv(
            path,
            "user_sub_good",
            [
                {
                    "id": "uuid-1",
                    "user_id": "123456789012345",
                    "good_id": "123",
                    "price": "1200",
                    "is_notified": "t",
                    "state": "1",
                }
            ],
        )

    def test_preserves_ids_prices_quoted_names_and_boolean(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            self.fixture(path)
            sql, counts = backup.convert(path)
            self.assertEqual(counts, {"user": 1, "good_info": 1, "user_sub_good": 1})
            with sqlite3.connect(":memory:") as db:
                db.executescript(
                    (Path(__file__).parents[1] / "migrations" / "0001_initial.sql").read_text()
                )
                db.executescript(sql)
                self.assertEqual(
                    db.execute("SELECT name FROM good_info").fetchone()[0], "商品's\n名稱"
                )
                self.assertEqual(
                    db.execute("SELECT user_id, price, is_notified FROM user_sub_good").fetchone(),
                    ("123456789012345", 1200, 1),
                )

    def test_rejects_missing_parent_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            self.fixture(path)
            self.write_csv(
                path,
                "user_sub_good",
                [{"id": "1", "user_id": "999", "good_id": "123", "price": "1200"}],
            )
            with self.assertRaises(sqlite3.IntegrityError):
                backup.convert(path)

    def test_rejects_invalid_prices_instead_of_dropping_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            self.fixture(path)
            self.write_csv(
                path, "good_info", [{"id": "123", "name": "商品", "price": "0", "stock_state": "1"}]
            )
            with self.assertRaises(sqlite3.IntegrityError):
                backup.convert(path)


if __name__ == "__main__":
    unittest.main()
