"""Pencatat sesi belajar lokal. Python 3.10+, standard library only."""
import argparse
import csv
import json
import re
import sqlite3
import sys
import unicodedata
from contextlib import closing
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

VERSION = "1.0.0"
APP_ID = 1398035780
MAX_ROWS = 10000
SCHEMA = """CREATE TABLE sessions (
    id INTEGER PRIMARY KEY,
    topic TEXT NOT NULL CHECK(length(topic) BETWEEN 1 AND 200),
    started_utc TEXT NOT NULL,
    minutes INTEGER NOT NULL CHECK(typeof(minutes) = 'integer' AND minutes BETWEEN 1 AND 1440)
)"""


class StudyError(ValueError):
    """Kesalahan yang aman ditampilkan kepada pengguna."""


def parse_offset(value):
    if not re.fullmatch(r"[+-](?:0[0-9]|1[0-4]):[0-5][0-9]", value):
        raise StudyError("Offset harus seperti +07:00, dengan rentang -14:00 sampai +14:00.")
    hours, minutes = map(int, value[1:].split(":"))
    if hours == 14 and minutes:
        raise StudyError("Offset maksimum adalah 14:00.")
    total = (hours * 60 + minutes) * (-1 if value[0] == "-" else 1)
    return timezone(timedelta(minutes=total))


def parse_start(value):
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9](?:Z|[+-][0-9]{2}:[0-9]{2})", value):
        raise StudyError("Waktu harus YYYY-MM-DDTHH:MM:SS+07:00 atau berakhiran Z.")
    if not value.endswith("Z"):
        parse_offset(value[-6:])
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except (ValueError, OverflowError) as exc:
        raise StudyError("Tanggal atau waktu tidak valid.") from exc
    if not 2 <= result.year <= 9998:
        raise StudyError("Tahun UTC harus antara 0002 dan 9998.")
    return result.isoformat(timespec="seconds")


def validate_topic(value):
    result = value.strip()
    if not 1 <= len(result) <= 200 or any(unicodedata.category(c).startswith("C") or c in "\u2028\u2029" for c in result):
        raise StudyError("Topik harus 1–200 karakter dan tidak mengandung karakter kontrol.")
    return result


def db_path(value):
    path = Path(value).expanduser()
    if path.is_symlink():
        raise StudyError("Database symlink tidak didukung.")
    return path.resolve()


def initialize(path):
    # Exclusive creation never truncates an existing database or unrelated file.
    with path.open("xb"):
        pass
    with closing(sqlite3.connect(str(path))) as connection:
        with connection:
            connection.execute(SCHEMA)
            connection.execute(f"PRAGMA application_id = {APP_ID}")
            connection.execute("PRAGMA user_version = 1")


def connect(path, writable=False):
    if not path.is_file():
        raise StudyError("Database belum ada. Jalankan init terlebih dahulu.")
    connection = sqlite3.connect(path.as_uri() + ("?mode=rw" if writable else "?mode=ro"), uri=True, timeout=5)
    try:
        if connection.execute("PRAGMA application_id").fetchone()[0] != APP_ID or connection.execute("PRAGMA user_version").fetchone()[0] != 1:
            raise StudyError("Format atau versi database tidak didukung.")
        tables = connection.execute("SELECT name, sql FROM sqlite_master WHERE type='table'").fetchall()
        if tables != [("sessions", SCHEMA)]:
            raise StudyError("Struktur database tidak didukung.")
    except Exception:
        connection.close()
        raise
    connection.row_factory = sqlite3.Row
    return connection


def add_session(path, topic, minutes, start):
    topic = validate_topic(topic)
    if type(minutes) is not int or not 1 <= minutes <= 1440:
        raise StudyError("Durasi harus bilangan bulat 1–1440 menit.")
    started = parse_start(start)
    with closing(connect(path, writable=True)) as connection:
        with connection:
            cursor = connection.execute("INSERT INTO sessions(topic, started_utc, minutes) VALUES (?, ?, ?)", (topic, started, minutes))
            return {"id": cursor.lastrowid, "topic": topic, "started_utc": started, "minutes": minutes}


def week_bounds(value, offset):
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise StudyError("Tanggal minggu harus YYYY-MM-DD.")
    try:
        selected = date.fromisoformat(value)
        monday = selected - timedelta(days=selected.weekday())
        start = datetime.combine(monday, time(), offset)
        end = start + timedelta(days=7)
        return monday.isoformat(), start.astimezone(timezone.utc).isoformat(), end.astimezone(timezone.utc).isoformat()
    except (ValueError, OverflowError) as exc:
        raise StudyError("Tanggal minggu berada di luar rentang yang didukung.") from exc


def sessions_for_week(path, week, offset):
    monday, start, end = week_bounds(week, offset)
    with closing(connect(path)) as connection:
        rows = connection.execute("SELECT id, topic, started_utc, minutes FROM sessions WHERE started_utc >= ? AND started_utc < ? ORDER BY started_utc, id LIMIT ?", (start, end, MAX_ROWS + 1)).fetchall()
    if len(rows) > MAX_ROWS:
        raise StudyError("Minggu berisi lebih dari 10000 sesi; ekspor/ringkasan dibatalkan.")
    return monday, [dict(row) for row in rows]


def summarize(rows, monday, offset):
    topics = {}
    for row in rows:
        topics[row["topic"]] = topics.get(row["topic"], 0) + row["minutes"]
    return {"week_start": monday, "offset": offset, "session_count": len(rows), "total_minutes": sum(row["minutes"] for row in rows), "topics": [{"topic": topic, "minutes": minutes} for topic, minutes in sorted(topics.items())]}


def csv_cell(value):
    # Quoting CSV alone does not prevent spreadsheet formula interpretation.
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def export_csv(path, output, rows):
    path = Path(path).resolve()
    output = Path(output).expanduser()
    protected = {path, Path(str(path) + "-wal"), Path(str(path) + "-shm"), Path(str(path) + "-journal")}
    if output.is_symlink() or output.resolve() in protected:
        raise StudyError("Tujuan ekspor tidak boleh menunjuk database atau file pendampingnya.")
    with output.open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, quoting=csv.QUOTE_ALL)
        writer.writerow(["id", "topic", "started_utc", "minutes"])
        for row in rows:
            writer.writerow([row["id"], csv_cell(row["topic"]), row["started_utc"], row["minutes"]])


def parser():
    root = argparse.ArgumentParser(description="Catat sesi belajar dan ringkas minggu Senin–Minggu.")
    root.add_argument("--version", action="version", version=VERSION)
    root.add_argument("--db", default="study.db", help="Lokasi database lokal (default: study.db).")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="Buat database baru tanpa menimpa file.")
    add = commands.add_parser("add", help="Catat sesi belajar yang telah dilakukan.")
    add.add_argument("--topic", required=True)
    add.add_argument("--minutes", required=True, type=int)
    add.add_argument("--start", required=True, help="Waktu mulai dengan offset eksplisit.")
    for name in ("list", "summary", "export"):
        command = commands.add_parser(name, help={"list": "Lihat sesi dalam satu minggu.", "summary": "Ringkasan durasi per topik.", "export": "Ekspor sesi mingguan ke CSV baru."}[name])
        command.add_argument("--week", required=True, help="Tanggal mana saja dalam minggu, YYYY-MM-DD.")
        command.add_argument("--offset", default="+07:00", help="Offset tetap untuk batas minggu (default +07:00).")
        if name == "export":
            command.add_argument("--output", required=True)
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        path = db_path(args.db)
        if args.command == "init":
            initialize(path)
            result = {"status": "database_dibuat", "version": VERSION}
        elif args.command == "add":
            result = add_session(path, args.topic, args.minutes, args.start)
        else:
            offset = parse_offset(args.offset)
            monday, rows = sessions_for_week(path, args.week, offset)
            if args.command == "summary":
                result = summarize(rows, monday, args.offset)
            elif args.command == "export":
                export_csv(path, args.output, rows)
                result = {"status": "csv_dibuat", "session_count": len(rows)}
            else:
                result = {"week_start": monday, "offset": args.offset, "sessions": rows}
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0
    except StudyError as exc:
        print(f"Gagal: {exc}", file=sys.stderr)
    except FileExistsError:
        print("Gagal: file tujuan sudah ada; pilih nama baru.", file=sys.stderr)
    except (OSError, sqlite3.Error, OverflowError, UnicodeError):
        print("Gagal: database atau file tidak dapat diakses. Periksa lokasi, izin, dan format.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
