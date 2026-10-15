import csv
import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout, closing
from pathlib import Path
from unittest.mock import patch

import study_session as app


class StudyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "belajar # ü.db"
        app.initialize(self.db)

    def add(self, topic="Python", minutes=30, start="2026-10-12T08:00:00+07:00"):
        return app.add_session(self.db, topic, minutes, start)

    def rows(self, week="2026-10-15", offset="+07:00"):
        return app.sessions_for_week(self.db, week, app.parse_offset(offset))[1]

    def cli(self, *args):
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            status = app.main(["--db", str(self.db), *args])
        return status, output.getvalue(), errors.getvalue()

    def test_persistence_and_parameterized_topic(self):
        topic = "SQL'); DROP TABLE sessions; --"
        first = self.add(topic)
        self.assertEqual(first["id"], 1)
        self.assertEqual(self.rows()[0]["topic"], topic)
        self.assertEqual(self.add()["id"], 2)

    def test_duration_validation_does_not_insert(self):
        for value in (-1, 0, 1441, 1.5, True):
            with self.subTest(value=value), self.assertRaises(app.StudyError):
                self.add(minutes=value)
        self.assertEqual(self.rows(), [])

    def test_duration_boundaries(self):
        self.add(minutes=1)
        self.add(minutes=1440)
        self.assertEqual(sum(row["minutes"] for row in self.rows()), 1441)

    def test_topic_validation(self):
        for topic in (" ", "a" * 201, "a\nb", "a\x00", "x\u2028y", "x\u200by"):
            with self.subTest(topic=topic), self.assertRaises(app.StudyError):
                self.add(topic)
        self.add("  Basis data 日本語  ")
        self.assertEqual(self.rows()[0]["topic"], "Basis data 日本語")

    def test_timestamp_offsets_same_instant(self):
        self.assertEqual(app.parse_start("2026-10-12T08:00:00+07:00"), app.parse_start("2026-10-12T01:00:00Z"))
        self.assertEqual(app.parse_start("2026-10-11T20:00:00-05:00"), "2026-10-12T01:00:00+00:00")

    def test_invalid_timestamps(self):
        for value in ("2026-10-12T08:00:00", "2026-02-30T08:00:00Z", "2026-10-12T24:00:00Z", "2026-10-12T08:00:60Z", "2026-10-12T08:00:00+14:01", "0001-01-01T00:00:00Z", "20261012T080000Z"):
            with self.subTest(value=value), self.assertRaises(app.StudyError):
                app.parse_start(value)

    def test_offset_limits(self):
        for offset in ("+14:00", "-14:00", "+00:00", "+05:30"):
            app.parse_offset(offset)
        for offset in ("Asia/Jakarta", "+24:00", "07:00", "+01:60", "-14:30"):
            with self.subTest(offset=offset), self.assertRaises(app.StudyError):
                app.parse_offset(offset)

    def test_week_start_inclusive_end_exclusive(self):
        self.add("before", start="2026-10-11T23:59:59+07:00")
        self.add("start", start="2026-10-12T00:00:00+07:00")
        self.add("end", start="2026-10-18T23:59:59+07:00")
        self.add("after", start="2026-10-19T00:00:00+07:00")
        self.assertEqual([r["topic"] for r in self.rows()], ["start", "end"])

    def test_timezone_changes_week_membership(self):
        self.add(start="2026-10-11T18:00:00Z")
        self.assertEqual(len(self.rows()), 1)
        self.assertEqual(self.rows(offset="+00:00"), [])

    def test_cross_year_monday(self):
        monday, _, _ = app.week_bounds("2027-01-01", app.parse_offset("+07:00"))
        self.assertEqual(monday, "2026-12-28")

    def test_invalid_week(self):
        for week in ("2026-02-30", "20261012", "9999-12-31", "0001-01-01"):
            with self.subTest(week=week), self.assertRaises(app.StudyError):
                app.week_bounds(week, app.parse_offset("+07:00"))

    def test_summary_groups_and_empty(self):
        self.add("Python", 20)
        self.add("SQL", 15)
        self.add("Python", 40)
        report = app.summarize(self.rows(), "2026-10-12", "+07:00")
        self.assertEqual(report["total_minutes"], 75)
        self.assertEqual(report["session_count"], 3)
        self.assertEqual(report["topics"], [{"topic": "Python", "minutes": 60}, {"topic": "SQL", "minutes": 15}])
        self.assertEqual(app.summarize([], "2026-10-12", "+07:00")["total_minutes"], 0)

    def test_overlapping_sessions_count_independently(self):
        self.add(minutes=60)
        self.add(minutes=60)
        self.assertEqual(app.summarize(self.rows(), "2026-10-12", "+07:00")["total_minutes"], 120)

    def test_read_commands_leave_database_bytes_unchanged(self):
        self.add()
        before = self.db.read_bytes()
        self.assertEqual(self.cli("list", "--week", "2026-10-15")[0], 0)
        self.assertEqual(self.cli("summary", "--week", "2026-10-15")[0], 0)
        self.assertEqual(self.db.read_bytes(), before)

    def test_init_does_not_overwrite(self):
        before = self.db.read_bytes()
        with self.assertRaises(FileExistsError):
            app.initialize(self.db)
        self.assertEqual(self.db.read_bytes(), before)

    def test_missing_database_not_created(self):
        path = self.db.parent / "missing.db"
        with self.assertRaises(app.StudyError):
            app.connect(path)
        self.assertFalse(path.exists())

    def test_foreign_or_changed_schema_rejected(self):
        foreign = self.db.parent / "foreign.db"
        with closing(sqlite3.connect(foreign)) as connection:
            connection.execute("CREATE TABLE private(value TEXT)")
        before = foreign.read_bytes()
        with self.assertRaises(app.StudyError):
            app.add_session(foreign, "test", 20, "2026-10-12T08:00:00Z")
        self.assertEqual(foreign.read_bytes(), before)
        with closing(sqlite3.connect(self.db)) as connection:
            connection.execute("ALTER TABLE sessions ADD COLUMN unexpected TEXT")
        with self.assertRaises(app.StudyError):
            app.connect(self.db)

    def test_database_version_rejected(self):
        with closing(sqlite3.connect(self.db)) as connection:
            connection.execute("PRAGMA user_version=2")
        with self.assertRaises(app.StudyError):
            app.connect(self.db)

    def test_symlink_guard(self):
        with patch.object(Path, "is_symlink", return_value=True), self.assertRaises(app.StudyError):
            app.db_path(str(self.db))

    def test_csv_roundtrip_unicode_and_formula(self):
        self.add('Python, "dasar" 日本語')
        self.add("=1+1")
        output = self.db.parent / "report.csv"
        before = self.db.read_bytes()
        app.export_csv(self.db, output, self.rows())
        with output.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(rows[0]["topic"], 'Python, "dasar" 日本語')
        self.assertEqual(rows[1]["topic"], "'=1+1")
        self.assertEqual(self.db.read_bytes(), before)

    def test_formula_prefixes(self):
        for value in ("=SUM(A1)", "+cmd", "-2", "@SUM(A1)", "  =1"):
            self.assertEqual(app.csv_cell(value), "'" + value)
        self.assertEqual(app.csv_cell("Python"), "Python")

    def test_export_does_not_overwrite(self):
        output = self.db.parent / "report.csv"
        output.write_text("existing", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            app.export_csv(self.db, output, [])
        self.assertEqual(output.read_text(encoding="utf-8"), "existing")

    def test_export_protects_database_sidecars(self):
        for suffix in ("", "-wal", "-shm", "-journal"):
            with self.subTest(suffix=suffix), self.assertRaises(app.StudyError):
                app.export_csv(self.db, str(self.db) + suffix, [])

    def test_empty_export_header(self):
        output = self.db.parent / "empty.csv"
        app.export_csv(self.db, output, [])
        with output.open(encoding="utf-8-sig", newline="") as stream:
            self.assertEqual(list(csv.reader(stream)), [["id", "topic", "started_utc", "minutes"]])

    def test_row_limit_fails_without_truncating(self):
        self.add()
        self.add()
        with patch.object(app, "MAX_ROWS", 1), self.assertRaises(app.StudyError):
            self.rows()

    def test_cli_add_summary_export(self):
        code, output, errors = self.cli("add", "--topic", "Python", "--minutes", "25", "--start", "2026-10-12T08:00:00+07:00")
        self.assertEqual((code, errors), (0, ""))
        self.assertEqual(json.loads(output)["minutes"], 25)
        code, output, _ = self.cli("summary", "--week", "2026-10-15")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)["total_minutes"], 25)
        self.assertEqual(self.cli("export", "--week", "2026-10-15", "--output", str(self.db.parent / "cli.csv"))[0], 0)

    def test_cli_error_no_traceback(self):
        code, output, errors = self.cli("add", "--topic", "Python", "--minutes", "-1", "--start", "2026-10-12T08:00:00Z")
        self.assertEqual((code, output), (2, ""))
        self.assertIn("Durasi", errors)
        self.assertNotIn("Traceback", errors)

    def test_corrupt_db_error(self):
        self.db.write_bytes(b"not a database")
        code, output, errors = self.cli("summary", "--week", "2026-10-15")
        self.assertEqual((code, output), (2, ""))
        self.assertNotIn(str(self.db), errors)


if __name__ == "__main__":
    unittest.main()
