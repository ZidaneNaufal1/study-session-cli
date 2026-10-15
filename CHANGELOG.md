# Changelog

## 1.0.0 — 2026-10-15

- Inisialisasi database SQLite baru, catat topik/durasi/waktu UTC, daftar dan ringkasan mingguan.
- Batas minggu Senin dengan offset eksplisit; input durasi dan waktu tervalidasi.
- Ekspor CSV Unicode ke file baru dengan perlindungan prefix formula.
- Pemeriksaan skema/versi, perintah baca read-only, transaksi SQL parameterized.
- Tes perilaku, demo sintetis, CI lintas OS/Python, dokumentasi Indonesia dan English summary.
- Validasi jam eksplisit menolak 24:00 secara konsisten pada seluruh versi Python yang didukung.
