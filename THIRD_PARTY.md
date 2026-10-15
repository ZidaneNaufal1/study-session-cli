# Dependency dan sumber

Runtime hanya menggunakan standard library Python (termasuk modul sqlite3 dengan SQLite yang dibundel distribusi Python). Tidak ada kode, dataset, gambar atau aset pihak ketiga yang disalin ke proyek. Contoh dan fixture pengujian bersifat sintetis.

Workflow CI menggunakan actions/checkout@v4 dan actions/setup-python@v5; keduanya dijalankan oleh GitHub Actions dan tidak diperlukan saat menjalankan CLI lokal. Lisensi masing-masing tetap milik proyek asal. Lisensi MIT repositori ini berlaku untuk kode/dokumentasi proyek, bukan lisensi ulang Python/SQLite atau GitHub Actions.
