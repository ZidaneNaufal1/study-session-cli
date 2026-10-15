"""Demo terisolasi: hanya data sintetis di direktori sementara."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

CLI = Path(__file__).resolve().parents[1] / "study_session.py"


def main():
    with tempfile.TemporaryDirectory() as folder:
        db = Path(folder) / "demo.db"
        def run(*args, expected=0):
            result = subprocess.run([sys.executable, str(CLI), "--db", str(db), *args], capture_output=True, text=True, check=False)
            assert result.returncode == expected, result.stderr
            return json.loads(result.stdout) if result.stdout else None
        run("init")
        run("add", "--topic", "Python", "--minutes", "25", "--start", "2026-10-12T08:00:00+07:00")
        run("add", "--topic", "SQL", "--minutes", "40", "--start", "2026-10-13T09:00:00+07:00")
        run("add", "--topic", "Python", "--minutes", "35", "--start", "2026-10-14T10:00:00+07:00")
        run("add", "--topic", "Ditolak", "--minutes", "-1", "--start", "2026-10-14T10:00:00Z", expected=2)
        before = db.read_bytes()
        summary = run("summary", "--week", "2026-10-15")
        assert summary["session_count"] == 3 and summary["total_minutes"] == 100
        output = Path(folder) / "sesi.csv"
        run("export", "--week", "2026-10-15", "--output", str(output))
        run("export", "--week", "2026-10-15", "--output", str(output), expected=2)
        assert db.read_bytes() == before
        print(json.dumps(summary, indent=2))
        print("Demo lulus: 3 sesi, 100 menit; input negatif dan overwrite ditolak.")


if __name__ == "__main__":
    main()
