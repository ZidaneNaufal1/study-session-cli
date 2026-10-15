# study-session-cli

[![Tests](https://github.com/ZidaneNaufal1/study-session-cli/actions/workflows/tests.yml/badge.svg)](https://github.com/ZidaneNaufal1/study-session-cli/actions/workflows/tests.yml)

Pencatat sesi belajar lokal untuk mahasiswa: simpan topik dan durasi di SQLite, lihat sesi dalam satu minggu, lalu ekspor ke CSV. Cocok untuk menjawab “minggu ini berapa menit belajar Python dan SQL?” tanpa akun atau koneksi internet.

## Mulai cepat

Python **3.10+** dengan modul bawaan `sqlite3`. Tidak membutuhkan paket pihak ketiga. Jalankan dari folder hasil clone:

```console
git clone https://github.com/ZidaneNaufal1/study-session-cli.git
cd study-session-cli
python study_session.py --db study.db init
python study_session.py --db study.db add --topic Python --minutes 25 --start 2026-10-12T08:00:00+07:00
python study_session.py --db study.db add --topic SQL --minutes 40 --start 2026-10-13T09:00:00+07:00
python study_session.py --db study.db summary --week 2026-10-15 --offset=+07:00
python study_session.py --db study.db list --week 2026-10-15
python study_session.py --db study.db export --week 2026-10-15 --output sesi-mingguan.csv
```

`--db` ditempatkan **sebelum** nama perintah. Defaultnya `study.db` di direktori kerja. Output sukses berupa JSON di stdout; kegagalan ditulis ke stderr. Exit code **0** = berhasil, **2** = input/operasi gagal (termasuk argumen CLI). `python study_session.py --help` menampilkan pilihan perintah.

Contoh ringkasan dari dua sesi di atas:

```json
{
  "week_start": "2026-10-12",
  "offset": "+07:00",
  "session_count": 2,
  "total_minutes": 65,
  "topics": [
    {"topic": "Python", "minutes": 25},
    {"topic": "SQL", "minutes": 40}
  ]
}
```

## Aturan pencatatan dan waktu

- Sesi diinput manual setelah belajar; bukan timer atau pengukur produktivitas otomatis.
- Topik 1–200 karakter Unicode setelah spasi tepi dihapus; karakter kontrol, format tersembunyi, dan pemisah baris ditolak. Pengelompokan peka huruf besar: `Python` berbeda dari `python`.
- Durasi bilangan bulat **1–1440 menit**. Durasi negatif, nol, pecahan dan lebih dari 24 jam ditolak sebelum insert.
- Waktu mulai harus `YYYY-MM-DDTHH:MM:SSZ` atau memakai offset seperti `+07:00`. Tidak menerima waktu tanpa offset, pecahan detik, leap second, atau jam 24:00. Tahun UTC 0002–9998.
- Waktu disimpan dalam UTC. Minggu dimulai **Senin 00:00**, sampai Senin berikutnya secara eksklusif, memakai offset tetap pilihan laporan (default `+07:00`). `--week` boleh tanggal mana saja dalam minggu tersebut. Untuk offset negatif gunakan `--offset=-05:00`.
- Satu sesi masuk seluruhnya ke minggu **waktu mulai**. Durasi yang melewati tengah malam/batas minggu tidak dipecah. Sesi tumpang tindih, duplikat, dan waktu masa depan diperbolehkan serta dihitung terpisah; angka ini total catatan, bukan waktu unik terverifikasi.
- Offset tetap -14:00 sampai +14:00; tidak menyediakan nama zona IANA atau perubahan daylight saving time. Tidak memerlukan database zona waktu tambahan pada Windows.
- `list`, `summary`, dan `export` dibatasi **10000 sesi per minggu**; jika lebih, operasi gagal tanpa laporan terpotong. Minggu kosong menghasilkan daftar/topik kosong, total nol, dan CSV header saja.

## Data lokal dan ekspor

`init` hanya membuat file baru dalam direktori yang sudah ada. File yang sudah ada tidak ditimpa. Database memakai application ID dan versi skema; database asing atau skema yang berubah ditolak. Penambahan memakai parameter SQL dan transaksi. Perintah baca menggunakan koneksi SQLite read-only; perintah `add` mengubah database. Jangan mengedit struktur SQLite secara manual.

CSV memakai UTF-8 BOM, kolom `id,topic,started_utc,minutes`, seluruh sel dikutip. Topik yang diawali `=`, `+`, `-`, atau `@` (setelah spasi) diberi apostrof untuk mengurangi risiko formula spreadsheet. Apostrof tersebut memang muncul dalam CSV; database tidak berubah. Saat membuka spreadsheet, tetap perlakukan data sebagai teks dan jangan menghapus perlindungannya tanpa memeriksa isi.

Ekspor hanya menulis file baru, menolak database dan jalur `-wal`, `-shm`, `-journal` miliknya. Tidak membuat direktori otomatis. Penulisan CSV eksklusif, tetapi **tidak atomik**: kegagalan disk/proses dapat menyisakan file baru parsial. Inisialisasi yang terhenti dapat menyisakan database baru belum lengkap. Gunakan nama file baru setelah memeriksa hasil yang gagal.

Gunakan file dan folder lokal tepercaya yang tidak diubah bersamaan oleh proses lain. Pemeriksaan path dan skema bukan sandbox untuk database jahat atau perlindungan terhadap pergantian path secara bersamaan. Symlink database akhir ditolak; folder induk symlink dan hardlink tidak diisolasi. SQLite dapat membuat file jurnal ketika menulis. Tutup program lain sebelum mencadangkan seluruh database; aplikasi tidak menyediakan backup otomatis, enkripsi, sinkronisasi, akun, edit/hapus sesi, atau impor CSV.

Topik dan waktu belajar dapat berisi informasi pribadi. Database dan CSV disimpan lokal dan tidak dikirim oleh program. Keduanya diabaikan oleh Git secara default. Semua contoh menggunakan data sintetis.

## Tes dan demo

```console
python -m unittest -v
python examples/run_demo.py
```

Tes mencakup validasi durasi/topik/tanggal, normalisasi UTC, batas minggu/tahun, perubahan offset, persistensi, database asing/versi salah, CSV Unicode/formula, perlindungan file, dan alur CLI. Demo membuat database sementara berisi tiga sesi, membuktikan total **100 menit** (Python 60, SQL 40), penolakan durasi negatif, dan pencegahan overwrite CSV. Tidak menyentuh database pribadi.

CI menjalankan tes dan demo dari checkout bersih pada Ubuntu/Windows dengan Python 3.10, 3.12, 3.14. Jika lingkungan sandbox membatasi folder sementara sistem, arahkan `TEMP` dan `TMP` ke folder kerja yang dapat ditulis sebelum menjalankan tes.

## Pemeliharaan dan kredit

Pemilik/maintainer: **Muhammad Zidane Naufal Azzam** ([ZidaneNaufal1](https://github.com/ZidaneNaufal1)). Dikembangkan dengan bantuan AI **Ciel / OpenAI Codex** untuk implementasi, pengujian dan dokumentasi. Lisensi [MIT](LICENSE). Lihat [CONTRIBUTING](CONTRIBUTING.md), [SECURITY](SECURITY.md), [CHANGELOG](CHANGELOG.md), dan [THIRD_PARTY](THIRD_PARTY.md).

Versi awal: 1.0.0. Rencana berikutnya: penghapusan satu sesi berdasarkan ID dengan konfirmasi dan pengujian rollback, sebelum penambahan impor atau sinkronisasi. Belum ada klaim adopsi atau kontribusi eksternal.

## English summary

An offline, dependency-free Python 3.10+ CLI for manually recording study topics and integer durations in SQLite. Explicit timestamp offsets normalize to UTC; weekly reports use a fixed offset and Monday boundaries. Sessions belong wholly to their start week; duplicates/overlaps remain independent. Includes JSON output, exclusive CSV export with formula-prefix escaping, schema/version checks, tests and a synthetic demo. No timer, IANA/DST zones, encryption, sync, editing or deletion in v1.0.0. Owned and maintained by Muhammad Zidane Naufal Azzam, with disclosed Ciel / OpenAI Codex assistance.
