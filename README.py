"""
CARE-MOTOR
Aplikasi Pencatatan Servis Motor Berkala (Computerized Automotive Reminder and Maintenance Tracker)
Teknologi: Python, Tkinter, SQLite
Jalankan: python main.py
Akun admin awal: username=admin, password=admin12345
Akun pengguna dibuat melalui menu registrasi.
"""

import csv
import hashlib
import os
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import date, datetime

DB_NAME = "care_motor.db"

INTERVAL_SERVIS = {
    # Servis berkala dan penggantian oli
    "Ganti Oli": 2000,  # nama kategori lama tetap didukung
    "Ganti Oli Mesin": 2000,
    "Ganti Oli Gardan": 5000,
    "Pemeriksaan Oli": 2000,

    # CVT dan transmisi
    "Membersihkan CVT": 8000,
    "Servis CVT": 8000,
    "Ganti V-Belt": 20000,
    "Ganti Roller CVT": 20000,
    "Ganti Kampas Kopling CVT": 20000,

    # Mesin, pembakaran, dan bahan bakar
    "Tune Up": 8000,
    "Servis Injeksi": 8000,
    "Pembersihan Throttle Body": 8000,
    "Servis Karburator": 8000,
    "Pembersihan Filter Udara": 4000,
    "Ganti Filter Udara": 8000,
    "Ganti Busi": 8000,
    "Pemeriksaan Mesin": 5000,

    # Rem, roda, dan kaki-kaki
    "Pemeriksaan Rem": 5000,
    "Servis Rem Depan": 5000,
    "Servis Rem Belakang": 5000,
    "Ganti Kampas Rem": 10000,
    "Pemeriksaan Ban": 5000,
    "Ganti Ban": 20000,
    "Pemeriksaan Bearing Roda": 10000,
    "Bearing Roda": 12000,

    # Kelistrikan dan pendingin
    "Pemeriksaan Aki": 5000,
    "Ganti Aki": 12000,
    "Pemeriksaan Lampu dan Kelistrikan": 6000,
    "Lampu dan Kelistrikan": 6000,
    "Pemeriksaan Sistem Pendingin": 6000,
    "Ganti Cairan Pendingin": 12000,
    "Cairan Pendingin": 12000,

    # Motor dengan rantai serta layanan umum
    "Pemeriksaan Rantai dan Gear": 5000,
    "Rantai dan Gear": 10000,
    "Servis Ringan": 5000,
    "Servis Berat": 10000,
    "Servis Umum": 5000,
}

BG = "#eef3f8"
DARK = "#17324d"
PRIMARY = "#1769aa"
GREEN = "#218c63"
ORANGE = "#d9822b"
RED = "#c0392b"


def koneksi():
    """Membuka koneksi database SQLite."""
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def hash_password(password):
    """Mengubah password menjadi hash sebelum disimpan."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def buat_database():
    """Membuat tabel jika database belum tersedia."""
    with koneksi() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nama TEXT NOT NULL,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user'
            );

            CREATE TABLE IF NOT EXISTS kendaraan (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                nomor_polisi TEXT NOT NULL,
                merk TEXT NOT NULL,
                tipe TEXT NOT NULL,
                tahun INTEGER NOT NULL,
                kilometer_saat_ini INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS riwayat_servis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_kendaraan INTEGER NOT NULL,
                jenis_servis TEXT NOT NULL,
                km_saat_servis INTEGER NOT NULL,
                tanggal_servis TEXT NOT NULL,
                biaya INTEGER NOT NULL DEFAULT 0,
                km_target_berikutnya INTEGER NOT NULL,
                catatan TEXT,
                FOREIGN KEY(id_kendaraan) REFERENCES kendaraan(id) ON DELETE CASCADE
            );
        """)
        # Migrasi database lama: tambahkan kolom role jika belum tersedia.
        kolom_user = {
            row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()
        }
        if "role" not in kolom_user:
            conn.execute(
                "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'"
            )

        # Akun admin awal dibuat hanya jika username admin belum tersedia.
        admin_ada = conn.execute(
            "SELECT id FROM users WHERE username = ?", ("admin",)
        ).fetchone()
        if not admin_ada:
            conn.execute(
                """INSERT INTO users(nama, username, password, role)
                   VALUES (?, ?, ?, ?)""",
                ("Administrator CARE-MOTOR", "admin",
                 hash_password("admin12345"), "admin")
            )


def rupiah(angka):
    return "Rp " + f"{int(angka):,}".replace(",", ".")


def format_km(angka):
    return f"{int(angka):,}".replace(",", ".") + " km"


class CareMotorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("CARE-MOTOR | Manajemen Perawatan Motor")
        self.root.geometry("1100x720")
        self.root.minsize(900, 600)
        self.root.configure(bg=BG)
        self.user = None
        self.kendaraan_aktif = None
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("Treeview", rowheight=27, font=("Arial", 10))
        self.style.configure("Treeview.Heading", font=("Arial", 10, "bold"))
        self.style.configure("TCombobox", padding=5)
        self.tampilkan_login()

    def bersihkan(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def judul(self, parent, teks, ukuran=18):
        tk.Label(parent, text=teks, bg=parent.cget("bg"), fg=DARK,
                 font=("Arial", ukuran, "bold")).pack(anchor="w", pady=(0, 12))

    def buat_tombol(self, parent, teks, perintah, warna=PRIMARY):
        return tk.Button(parent, text=teks, command=perintah, bg=warna,
                         fg="white", activebackground=warna, activeforeground="white",
                         relief="flat", padx=12, pady=8, cursor="hand2",
                         font=("Arial", 10, "bold"))

    # -------------------- AKUN --------------------
    def tampilkan_login(self):
        self.bersihkan()
        panel = tk.Frame(self.root, bg="white", padx=38, pady=32,
                         highlightbackground="#d7e0e8", highlightthickness=1)
        panel.place(relx=0.5, rely=0.5, anchor="center", width=410, height=430)

        tk.Label(panel, text="CARE-MOTOR", bg="white", fg=PRIMARY,
                 font=("Arial", 25, "bold")).pack(pady=(5, 4))
        tk.Label(panel, text="Manajemen Perawatan Sepeda Motor",
                 bg="white", fg="#5b6b79", font=("Arial", 10)).pack(pady=(0, 25))

        tk.Label(panel, text="Username", bg="white", anchor="w").pack(fill="x")
        self.login_username = tk.Entry(panel, font=("Arial", 11))
        self.login_username.pack(fill="x", ipady=7, pady=(4, 13))

        tk.Label(panel, text="Password", bg="white", anchor="w").pack(fill="x")
        self.login_password = tk.Entry(panel, show="*", font=("Arial", 11))
        self.login_password.pack(fill="x", ipady=7, pady=(4, 18))
        self.login_password.bind("<Return>", lambda event: self.proses_login())

        self.buat_tombol(panel, "MASUK", self.proses_login).pack(fill="x")
        tk.Button(panel, text="Belum punya akun? Daftar", command=self.tampilkan_registrasi,
                  bg="white", fg=PRIMARY, relief="flat", cursor="hand2").pack(pady=15)

    def tampilkan_registrasi(self):
        self.bersihkan()
        panel = tk.Frame(self.root, bg="white", padx=38, pady=28)
        panel.place(relx=0.5, rely=0.5, anchor="center", width=430, height=490)
        tk.Label(panel, text="BUAT AKUN CARE-MOTOR", bg="white", fg=PRIMARY,
                 font=("Arial", 19, "bold")).pack(pady=(5, 20))

        self.reg_nama = self.buat_input(panel, "Nama lengkap")
        self.reg_username = self.buat_input(panel, "Username")
        self.reg_password = self.buat_input(panel, "Password", rahasia=True)
        self.reg_konfirmasi = self.buat_input(panel, "Ulangi password", rahasia=True)

        self.buat_tombol(panel, "DAFTAR", self.proses_registrasi, GREEN).pack(fill="x", pady=(8, 4))
        tk.Button(panel, text="Kembali ke login", command=self.tampilkan_login,
                  bg="white", fg=PRIMARY, relief="flat").pack(pady=8)

    def buat_input(self, parent, label, rahasia=False):
        tk.Label(parent, text=label, bg="white", anchor="w").pack(fill="x")
        entry = tk.Entry(parent, show="*" if rahasia else "", font=("Arial", 10))
        entry.pack(fill="x", ipady=6, pady=(3, 10))
        return entry

    def proses_registrasi(self):
        nama = self.reg_nama.get().strip()
        username = self.reg_username.get().strip()
        password = self.reg_password.get()
        konfirmasi = self.reg_konfirmasi.get()

        if not nama or not username or not password or not konfirmasi:
            messagebox.showwarning("Data belum lengkap", "Semua kolom wajib diisi.")
            return
        if len(password) < 6:
            messagebox.showwarning("Password", "Password minimal 6 karakter.")
            return
        if password != konfirmasi:
            messagebox.showerror("Password", "Konfirmasi password tidak sama.")
            return

        try:
            with koneksi() as conn:
                conn.execute(
                    """INSERT INTO users(nama, username, password, role)
                       VALUES (?, ?, ?, 'user')""",
                    (nama, username, hash_password(password))
                )
            messagebox.showinfo("Berhasil", "Akun berhasil dibuat. Silakan login.")
            self.tampilkan_login()
        except sqlite3.IntegrityError:
            messagebox.showerror("Username digunakan", "Gunakan username yang berbeda.")

    def proses_login(self):
        username = self.login_username.get().strip()
        password = self.login_password.get()
        if not username or not password:
            messagebox.showwarning("Login", "Username dan password harus diisi.")
            return
        with koneksi() as conn:
            data = conn.execute(
                """SELECT id, nama, username, role FROM users
                   WHERE username=? AND password=?""",
                (username, hash_password(password))
            ).fetchone()
        if not data:
            messagebox.showerror("Login gagal", "Username atau password salah.")
            return
        self.user = {
            "id": data[0], "nama": data[1],
            "username": data[2], "role": data[3]
        }
        self.tampilkan_dashboard()

    # -------------------- DASHBOARD --------------------
    def tampilkan_dashboard(self):
        if self.user and self.user.get("role") == "admin":
            self.tampilkan_dashboard_admin()
        else:
            self.tampilkan_dashboard_pengguna()

    def data_grafik_dashboard(self, admin=False):
        """Mengambil data grafik 6 bulan terakhir dari database."""
        labels = []
        counts = []
        costs = []
        now = date.today()
        months = []
        for offset in range(5, -1, -1):
            year = now.year
            month = now.month - offset
            while month <= 0:
                month += 12
                year -= 1
            months.append(f"{year:04d}-{month:02d}")
            labels.append(datetime(year, month, 1).strftime("%b"))
        with koneksi() as conn:
            for period in months:
                if admin:
                    row = conn.execute("""
                        SELECT COUNT(*), COALESCE(SUM(r.biaya), 0)
                        FROM riwayat_servis r
                        WHERE substr(r.tanggal_servis, 1, 7)=?
                    """, (period,)).fetchone()
                else:
                    row = conn.execute("""
                        SELECT COUNT(*), COALESCE(SUM(r.biaya), 0)
                        FROM riwayat_servis r
                        JOIN kendaraan k ON k.id=r.id_kendaraan
                        WHERE k.user_id=? AND substr(r.tanggal_servis, 1, 7)=?
                    """, (self.user["id"], period)).fetchone()
                counts.append(row[0] or 0)
                costs.append(row[1] or 0)
            if admin:
                categories = conn.execute("""
                    SELECT jenis_servis, COUNT(*) FROM riwayat_servis
                    GROUP BY jenis_servis ORDER BY COUNT(*) DESC LIMIT 5
                """).fetchall()
            else:
                categories = conn.execute("""
                    SELECT r.jenis_servis, COUNT(*)
                    FROM riwayat_servis r JOIN kendaraan k ON k.id=r.id_kendaraan
                    WHERE k.user_id=? GROUP BY r.jenis_servis
                    ORDER BY COUNT(*) DESC LIMIT 5
                """, (self.user["id"],)).fetchall()
        return labels, counts, costs, categories

    def gambar_grafik_batang(self, canvas, labels, values, color=PRIMARY):
        """Menggambar grafik batang responsif; nilai berasal dari database."""
        canvas.delete("all")
        width = max(canvas.winfo_width(), 320)
        height = max(canvas.winfo_height(), 190)
        left, right, top, bottom = 38, width - 16, 18, height - 34
        canvas.create_line(left, top, left, bottom, fill="#cbd5df")
        canvas.create_line(left, bottom, right, bottom, fill="#cbd5df")
        maximum = max(values) if values else 0
        scale = maximum or 1
        slot = (right - left) / max(len(values), 1)
        for i, value in enumerate(values):
            x = left + slot * i + slot * 0.22
            bar_w = slot * 0.56
            bar_h = (bottom - top - 12) * value / scale if value else 2
            canvas.create_rectangle(x, bottom - bar_h, x + bar_w, bottom,
                                   fill=color, outline="")
            canvas.create_text(x + bar_w / 2, bottom - bar_h - 10,
                               text=str(value), fill=DARK, font=("Arial", 8))
            canvas.create_text(x + bar_w / 2, bottom + 15,
                               text=labels[i], fill="#657587", font=("Arial", 8))

    def gambar_grafik_garis(self, canvas, labels, values, color=ORANGE):
        """Menggambar tren biaya bulanan dari data servis."""
        canvas.delete("all")
        width = max(canvas.winfo_width(), 320)
        height = max(canvas.winfo_height(), 190)
        left, right, top, bottom = 48, width - 16, 18, height - 34
        maximum = max(values) if values else 0
        scale = maximum or 1
        for fraction in (0, .25, .5, .75, 1):
            y = bottom - (bottom - top) * fraction
            canvas.create_line(left, y, right, y, fill="#e5eaf0")
        points = []
        slot = (right - left) / max(len(values) - 1, 1)
        for i, value in enumerate(values):
            x = left + i * slot
            y = bottom - (bottom - top - 8) * value / scale
            points.extend((x, y))
            canvas.create_text(x, bottom + 15, text=labels[i],
                               fill="#657587", font=("Arial", 8))
            canvas.create_oval(x-4, y-4, x+4, y+4, fill=color, outline="white")
        if len(points) >= 4:
            canvas.create_line(*points, fill=color, width=3, smooth=True)
            for i in range(0, len(points), 2):
                canvas.create_oval(points[i]-4, points[i+1]-4,
                                   points[i]+4, points[i+1]+4,
                                   fill=color, outline="white")

    def gambar_grafik_donut(self, canvas, categories):
        """Menggambar distribusi jenis servis sebagai diagram donat."""
        canvas.delete("all")
        width = max(canvas.winfo_width(), 300)
        height = max(canvas.winfo_height(), 190)
        total = sum(row[1] for row in categories)
        cx, cy = width * .34, height * .52
        radius = min(65, height * .34)
        colors = [PRIMARY, ORANGE, GREEN, "#8e6bbf", "#d65b72"]
        if total:
            angle = 90
            for i, (name, count) in enumerate(categories):
                extent = 360 * count / total
                canvas.create_arc(cx-radius, cy-radius, cx+radius, cy+radius,
                                  start=angle, extent=extent, style="pieslice",
                                  outline="white", width=2,
                                  fill=colors[i % len(colors)])
                angle += extent
            canvas.create_oval(cx-radius*.57, cy-radius*.57,
                               cx+radius*.57, cy+radius*.57,
                               fill="white", outline="white")
            canvas.create_text(cx, cy, text=str(total), fill=DARK,
                               font=("Arial", 15, "bold"))
        else:
            canvas.create_oval(cx-radius, cy-radius, cx+radius, cy+radius,
                               outline="#dce3ea", width=18)
            canvas.create_text(cx, cy, text="0", fill=DARK,
                               font=("Arial", 15, "bold"))
        legend_x = width * .60
        for i, (name, count) in enumerate(categories[:5]):
            y = 35 + i * 27
            canvas.create_rectangle(legend_x, y, legend_x+10, y+10,
                                    fill=colors[i % len(colors)], outline="")
            canvas.create_text(legend_x+17, y+5,
                               text=f"{name[:18]} ({count})",
                               anchor="w", fill=DARK, font=("Arial", 8))
        if not categories:
            canvas.create_text(legend_x, 42, text="Belum ada data servis",
                               anchor="w", fill="#657587", font=("Arial", 9))

    def buat_panel_grafik(self, parent, title, kind, labels, values, categories=None):
        panel = tk.Frame(parent, bg="white", padx=14, pady=12,
                         highlightbackground="#dce4ec", highlightthickness=1)
        tk.Label(panel, text=title, bg="white", fg=DARK,
                 font=("Arial", 11, "bold")).pack(anchor="w")
        canvas = tk.Canvas(panel, height=190, bg="white", highlightthickness=0)
        canvas.pack(fill="both", expand=True, pady=(8, 0))
        def draw(_event=None):
            if kind == "bar":
                self.gambar_grafik_batang(canvas, labels, values, PRIMARY)
            elif kind == "line":
                self.gambar_grafik_garis(canvas, labels, values, ORANGE)
            else:
                self.gambar_grafik_donut(canvas, categories or [])
        canvas.bind("<Configure>", draw)
        panel.after(80, draw)
        return panel

    def buat_dashboard_modern(self, title, subtitle, cards, labels, counts,
                              costs, categories, actions, admin=False):
        """Layout dashboard bersama untuk member dan administrator."""
        self.bersihkan()
        shell = tk.Frame(self.root, bg=BG)
        shell.pack(fill="both", expand=True)

        sidebar = tk.Frame(shell, bg="#102b68", width=205)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        tk.Label(sidebar, text="CARE-MOTOR", bg="#102b68", fg="white",
                 font=("Arial", 19, "bold")).pack(anchor="w", padx=18, pady=(25, 4))
        tk.Label(sidebar, text="MOTORCYCLE CARE SYSTEM", bg="#102b68",
                 fg="#c9d8f5", font=("Arial", 7, "bold")).pack(anchor="w", padx=19, pady=(0, 30))
        nav = [
            ("⌂  Dashboard", self.tampilkan_dashboard),
            ("▣  Kendaraan", self.jendela_kendaraan if not admin else self.admin_data_kendaraan),
            ("⚙  Servis", self.menu_servis_pengguna if not admin else self.admin_menu_servis),
            ("▤  Laporan", self.jendela_laporan if not admin else self.admin_laporan_bulanan),
            ("◷  Jadwal", self.jendela_jadwal if not admin else self.admin_statistik_servis),
        ]
        if admin:
            nav.insert(1, ("♙  Data Member", self.admin_data_member))
        for label, command in nav:
            tk.Button(sidebar, text=label, command=command, anchor="w",
                      bg="#102b68", fg="white", activebackground="#1d438f",
                      activeforeground="white", relief="flat", padx=18,
                      pady=12, font=("Arial", 10, "bold"),
                      cursor="hand2").pack(fill="x", padx=7, pady=2)
        tk.Frame(sidebar, bg="#49639a", height=1).pack(fill="x", padx=16, pady=18)
        tk.Button(sidebar, text="↩  Kembali ke Login", command=self.logout,
                  bg="#d9822b", fg="white", activebackground="#bd6d22",
                  activeforeground="white", relief="flat", padx=10, pady=11,
                  font=("Arial", 9, "bold"), cursor="hand2").pack(
                      side="bottom", fill="x", padx=13, pady=20)

        main = tk.Frame(shell, bg=BG)
        main.pack(side="left", fill="both", expand=True)
        header = tk.Frame(main, bg="white", padx=24, pady=17)
        header.pack(fill="x")
        tk.Label(header, text=title, bg="white", fg="#182433",
                 font=("Arial", 19, "bold")).pack(side="left")
        tk.Label(header, text=subtitle, bg="white", fg="#667789",
                 font=("Arial", 9)).pack(side="right")
        content = tk.Frame(main, bg=BG, padx=20, pady=16)
        content.pack(fill="both", expand=True)

        card_row = tk.Frame(content, bg=BG)
        card_row.pack(fill="x", pady=(0, 14))
        for i, (label, value, color) in enumerate(cards):
            self.kartu(card_row, label, value, color).pack(
                side="left", fill="x", expand=True,
                padx=(0 if i == 0 else 6, 0 if i == len(cards)-1 else 6)
            )

        chart_row = tk.Frame(content, bg=BG)
        chart_row.pack(fill="x", pady=(0, 13))
        self.buat_panel_grafik(chart_row, "Jumlah Servis per Bulan", "bar",
                               labels, counts).pack(side="left", fill="both",
                                                    expand=True, padx=(0, 6))
        self.buat_panel_grafik(chart_row, "Tren Biaya Perawatan", "line",
                               labels, costs).pack(side="left", fill="both",
                                                   expand=True, padx=6)
        self.buat_panel_grafik(chart_row, "Jenis Servis", "donut", labels, [],
                               categories).pack(side="left", fill="both",
                                                expand=True, padx=(6, 0))

        action_panel = tk.Frame(content, bg="white", padx=14, pady=12)
        action_panel.pack(fill="both", expand=True)
        tk.Label(action_panel, text="MENU UTAMA", bg="white", fg=DARK,
                 font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 8))
        for index, (label, callback) in enumerate(actions):
            tk.Button(action_panel, text=label, command=callback,
                      bg="#f1f5fa", fg=DARK, activebackground="#dce8f7",
                      relief="flat", padx=8, pady=9, cursor="hand2",
                      font=("Arial", 9, "bold")).grid(
                          row=index // 4, column=index % 4,
                          sticky="ew", padx=5, pady=5)
        for col in range(4):
            action_panel.grid_columnconfigure(col, weight=1)
        footer = tk.Frame(content, bg=BG)
        footer.pack(fill="x", pady=(10, 0))
        tk.Label(footer, text="Grafik diperbarui berdasarkan data database CARE-MOTOR.",
                 bg=BG, fg="#687887", font=("Arial", 8)).pack(side="left")
        tk.Button(footer, text="↻  Refresh", command=self.tampilkan_dashboard,
                  bg=GREEN, fg="white", relief="flat", padx=14, pady=7,
                  cursor="hand2").pack(side="right")

    def tampilkan_dashboard_pengguna(self):
        """Dashboard member dengan grafik khusus data akun yang login."""
        labels, counts, costs, categories = self.data_grafik_dashboard(False)
        with koneksi() as conn:
            jumlah_motor = conn.execute(
                "SELECT COUNT(*) FROM kendaraan WHERE user_id=?",
                (self.user["id"],)).fetchone()[0]
            jumlah_servis = conn.execute("""
                SELECT COUNT(*) FROM riwayat_servis r
                JOIN kendaraan k ON k.id=r.id_kendaraan WHERE k.user_id=?
            """, (self.user["id"],)).fetchone()[0]
            total_biaya = conn.execute("""
                SELECT COALESCE(SUM(r.biaya),0) FROM riwayat_servis r
                JOIN kendaraan k ON k.id=r.id_kendaraan WHERE k.user_id=?
            """, (self.user["id"],)).fetchone()[0]
        upcoming = len(self.hitung_notifikasi())
        cards = [
            ("Kendaraan", str(jumlah_motor), PRIMARY),
            ("Total Servis", str(jumlah_servis), GREEN),
            ("Biaya Perawatan", rupiah(total_biaya), ORANGE),
            ("Pengingat Servis", str(upcoming), RED),
        ]
        actions = [
            ("Tambah Kendaraan", self.form_tambah_kendaraan),
            ("Data Kendaraan", self.jendela_kendaraan),
            ("Update Kilometer", self.form_update_km),
            ("Menu Servis", self.menu_servis_pengguna),
            ("Catat Servis", self.form_tambah_servis),
            ("Jadwal Berikutnya", self.jendela_jadwal),
            ("Notifikasi", self.jendela_notifikasi),
            ("Riwayat Servis", self.jendela_riwayat),
            ("Laporan Kendaraan", self.jendela_laporan),
            ("Analisis Perawatan", self.jendela_analisis),
            ("Ekspor CSV", self.ekspor_csv),
            ("Kembali ke Login", self.logout),
        ]
        self.buat_dashboard_modern(
            "Dashboard Member", f"Pengguna: {self.user['nama']}",
            cards, labels, counts, costs, categories, actions, False
        )

    # -------------------- MENU SERVIS PENGGUNA --------------------
    def menu_servis_pengguna(self):
        """Pusat layanan servis milik pengguna yang sedang login."""
        win = tk.Toplevel(self.root)
        win.title("Menu Servis Pengguna - CARE-MOTOR")
        win.geometry("900x620")
        win.configure(bg=BG)

        header = tk.Frame(win, bg=DARK, padx=20, pady=16)
        header.pack(fill="x")
        tk.Label(
            header, text="PUSAT LAYANAN SERVIS",
            bg=DARK, fg="white", font=("Arial", 18, "bold")
        ).pack(anchor="w")
        tk.Label(
            header, text=f"Pemilik akun: {self.user['nama']}",
            bg=DARK, fg="#dce8f2", font=("Arial", 10)
        ).pack(anchor="w", pady=(4, 0))

        body = tk.Frame(win, bg=BG, padx=20, pady=18)
        body.pack(fill="both", expand=True)

        with koneksi() as conn:
            jumlah_motor = conn.execute(
                "SELECT COUNT(*) FROM kendaraan WHERE user_id=?",
                (self.user["id"],)
            ).fetchone()[0]
            jumlah_servis = conn.execute("""
                SELECT COUNT(*) FROM riwayat_servis r
                JOIN kendaraan k ON k.id=r.id_kendaraan
                WHERE k.user_id=?
            """, (self.user["id"],)).fetchone()[0]
            total_biaya = conn.execute("""
                SELECT COALESCE(SUM(r.biaya), 0)
                FROM riwayat_servis r
                JOIN kendaraan k ON k.id=r.id_kendaraan
                WHERE k.user_id=?
            """, (self.user["id"],)).fetchone()[0]

        summary = tk.Frame(body, bg=BG)
        summary.pack(fill="x", pady=(0, 18))
        self.kartu(summary, "Kendaraan Terdaftar", str(jumlah_motor), PRIMARY).pack(
            side="left", fill="x", expand=True, padx=(0, 6)
        )
        self.kartu(summary, "Catatan Servis", str(jumlah_servis), GREEN).pack(
            side="left", fill="x", expand=True, padx=6
        )
        self.kartu(summary, "Total Biaya", rupiah(total_biaya), ORANGE).pack(
            side="left", fill="x", expand=True, padx=(6, 0)
        )

        panel = tk.Frame(body, bg="white", padx=18, pady=18)
        panel.pack(fill="both", expand=True)
        self.judul(panel, "Kelola Perawatan Kendaraan", 14)

        actions = [
            ("Tambah Catatan Servis", self.form_tambah_servis),
            ("Lihat Jadwal Servis", self.jendela_jadwal),
            ("Lihat Notifikasi", self.jendela_notifikasi),
            ("Riwayat Servis", self.jendela_riwayat),
            ("Laporan Kendaraan", self.jendela_laporan),
            ("Analisis Perawatan", self.jendela_analisis),
            ("Ringkasan Biaya Servis", self.jendela_ringkasan_biaya),
        ]
        for index, (label, callback) in enumerate(actions):
            self.buat_tombol(panel, label, callback).grid(
                row=index // 2, column=index % 2,
                sticky="ew", padx=7, pady=7
            )
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_columnconfigure(1, weight=1)

        tk.Label(
            body,
            text="Catatan: seluruh menu pengguna hanya menampilkan data kendaraan "
                 "dan servis milik akun yang sedang login.",
            bg=BG, fg="#536575", font=("Arial", 9), wraplength=820
        ).pack(anchor="w", pady=(12, 0))

    def ringkasan_servis_pengguna(self):
        """Mengambil ringkasan servis pengguna untuk dipakai beberapa tampilan."""
        with koneksi() as conn:
            total = conn.execute("""
                SELECT COUNT(*)
                FROM riwayat_servis r
                JOIN kendaraan k ON k.id=r.id_kendaraan
                WHERE k.user_id=?
            """, (self.user["id"],)).fetchone()[0]
            biaya = conn.execute("""
                SELECT COALESCE(SUM(r.biaya), 0)
                FROM riwayat_servis r
                JOIN kendaraan k ON k.id=r.id_kendaraan
                WHERE k.user_id=?
            """, (self.user["id"],)).fetchone()[0]
            jenis = conn.execute("""
                SELECT r.jenis_servis, COUNT(*) AS jumlah
                FROM riwayat_servis r
                JOIN kendaraan k ON k.id=r.id_kendaraan
                WHERE k.user_id=?
                GROUP BY r.jenis_servis
                ORDER BY jumlah DESC, r.jenis_servis ASC
                LIMIT 1
            """, (self.user["id"],)).fetchone()
        return {
            "total_servis": total,
            "total_biaya": biaya,
            "servis_terbanyak": jenis[0] if jenis else "-",
            "jumlah_servis_terbanyak": jenis[1] if jenis else 0,
        }


    def jendela_ringkasan_biaya(self):
        """Menampilkan rincian biaya servis milik akun yang sedang aktif."""
        summary = self.ringkasan_servis_pengguna()
        win = tk.Toplevel(self.root)
        win.title("Ringkasan Biaya Servis Pengguna")
        win.geometry("650x470")
        win.configure(bg="white")
        frame = tk.Frame(win, bg="white", padx=22, pady=20)
        frame.pack(fill="both", expand=True)

        tk.Label(
            frame, text="RINGKASAN PERAWATAN MOTOR",
            bg="white", fg=DARK, font=("Arial", 17, "bold")
        ).pack(anchor="w", pady=(0, 18))

        values = [
            ("Total catatan servis", summary["total_servis"]),
            ("Total pengeluaran", rupiah(summary["total_biaya"])),
            (
                "Rata-rata biaya per servis",
                rupiah(
                    summary["total_biaya"] / summary["total_servis"]
                    if summary["total_servis"] else 0
                )
            ),
            ("Servis paling sering", summary["servis_terbanyak"]),
            (
                "Jumlah servis terbanyak",
                summary["jumlah_servis_terbanyak"]
            ),
        ]

        for label, value in values:
            line = tk.Frame(frame, bg="#edf3f8", padx=14, pady=12)
            line.pack(fill="x", pady=5)
            tk.Label(
                line, text=label, bg="#edf3f8", fg=DARK,
                font=("Arial", 10, "bold")
            ).pack(side="left")
            tk.Label(
                line, text=str(value), bg="#edf3f8", fg=PRIMARY,
                font=("Arial", 10, "bold")
            ).pack(side="right")

        tk.Label(
            frame,
            text="Ringkasan dihitung dari seluruh riwayat servis kendaraan "
                 "yang terdaftar pada akun ini.",
            bg="white", fg="#647585", wraplength=580,
            font=("Arial", 9)
        ).pack(anchor="w", pady=(12, 0))

        self.buat_tombol(
            frame, "TUTUP", win.destroy, RED
        ).pack(anchor="e", pady=(18, 0))

    def kartu(self, parent, label, nilai, warna):
        frame = tk.Frame(parent, bg=warna, padx=15, pady=14)
        tk.Label(frame, text=label, bg=warna, fg="white",
                 font=("Arial", 10)).pack(anchor="w")
        tk.Label(frame, text=nilai, bg=warna, fg="white",
                 font=("Arial", 15, "bold")).pack(anchor="w", pady=(5, 0))
        return frame


    # -------------------- DASHBOARD ADMIN --------------------
    def tampilkan_dashboard_admin(self):
        """Dashboard administrator dengan grafik seluruh data member."""
        labels, counts, costs, categories = self.data_grafik_dashboard(True)
        with koneksi() as conn:
            total_member = conn.execute(
                "SELECT COUNT(*) FROM users WHERE role='user'"
            ).fetchone()[0]
            total_motor = conn.execute("SELECT COUNT(*) FROM kendaraan").fetchone()[0]
            total_servis = conn.execute("SELECT COUNT(*) FROM riwayat_servis").fetchone()[0]
            total_biaya = conn.execute(
                "SELECT COALESCE(SUM(biaya),0) FROM riwayat_servis"
            ).fetchone()[0]
        cards = [
            ("Total Member", str(total_member), PRIMARY),
            ("Total Kendaraan", str(total_motor), GREEN),
            ("Total Servis", str(total_servis), ORANGE),
            ("Total Biaya", rupiah(total_biaya), RED),
        ]
        actions = [
            ("Data Member", self.admin_data_member),
            ("Semua Kendaraan", self.admin_data_kendaraan),
            ("Semua Riwayat Servis", self.admin_data_servis),
            ("Statistik Servis", self.admin_statistik_servis),
            ("Laporan Bulanan", self.admin_laporan_bulanan),
            ("Pencarian Data", self.admin_pencarian),
            ("Ekspor Member", self.admin_ekspor_member),
            ("Ekspor Kendaraan", self.admin_ekspor_kendaraan),
            ("Ekspor Servis", self.admin_ekspor_servis),
            ("Input Data Kendaraan", self.admin_form_tambah_kendaraan),
            ("Menu Servis Umum", self.admin_menu_servis),
            ("Kembali ke Login", self.logout),
        ]
        self.buat_dashboard_modern(
            "Vehicle & Service Overview",
            f"Administrator: {self.user['nama']}",
            cards, labels, counts, costs, categories, actions, True
        )

    def buat_tabel_admin(self, title, columns, headings, widths):
        """Membuat jendela tabel admin dengan konfigurasi kolom seragam."""
        win = tk.Toplevel(self.root)
        win.title(title)
        win.geometry("1150x620")
        win.configure(bg="white")
        outer = tk.Frame(win, bg="white", padx=16, pady=16)
        outer.pack(fill="both", expand=True)
        tk.Label(
            outer, text=title.upper(), bg="white", fg=DARK,
            font=("Arial", 16, "bold")
        ).pack(anchor="w", pady=(0, 12))
        table_frame = tk.Frame(outer, bg="white")
        table_frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(
            table_frame, columns=columns, show="headings",
            selectmode="browse"
        )
        for col, heading, width in zip(columns, headings, widths):
            tree.heading(col, text=heading)
            tree.column(col, width=width, anchor="center")
        vertical = ttk.Scrollbar(
            table_frame, orient="vertical", command=tree.yview
        )
        horizontal = ttk.Scrollbar(
            table_frame, orient="horizontal", command=tree.xview
        )
        tree.configure(
            yscrollcommand=vertical.set,
            xscrollcommand=horizontal.set
        )
        tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        return win, outer, tree

    def admin_data_member(self):
        """Admin dapat melihat semua member dan jumlah aset/servis tiap member."""
        win, outer, tree = self.buat_tabel_admin(
            "Data Member CARE-MOTOR",
            ("id", "nama", "username", "motor", "servis", "biaya"),
            ("ID", "Nama Member", "Username", "Jumlah Motor",
             "Total Servis", "Total Biaya Servis"),
            (55, 220, 150, 110, 110, 170)
        )
        with koneksi() as conn:
            rows = conn.execute("""
                SELECT u.id, u.nama, u.username,
                    COUNT(DISTINCT k.id) AS jumlah_motor,
                    COUNT(DISTINCT r.id) AS jumlah_servis,
                    COALESCE(SUM(r.biaya), 0) AS total_biaya
                FROM users u
                LEFT JOIN kendaraan k ON k.user_id=u.id
                LEFT JOIN riwayat_servis r ON r.id_kendaraan=k.id
                WHERE u.role='user'
                GROUP BY u.id, u.nama, u.username
                ORDER BY u.id DESC
            """).fetchall()
        for row in rows:
            tree.insert(
                "", "end",
                values=(row[0], row[1], row[2], row[3], row[4],
                        rupiah(row[5]))
            )

        buttons = tk.Frame(outer, bg="white")
        buttons.pack(fill="x", pady=(12, 0))
        self.buat_tombol(
            buttons, "LIHAT DETAIL MEMBER",
            lambda: self.admin_detail_member(tree), GREEN
        ).pack(side="left")
        self.buat_tombol(
            buttons, "TUTUP", win.destroy, RED
        ).pack(side="right")

    def admin_detail_member(self, member_tree):
        """Menampilkan kendaraan dan riwayat servis milik member terpilih."""
        selected = member_tree.selection()
        if not selected:
            messagebox.showwarning(
                "Pilih Member", "Pilih satu member terlebih dahulu."
            )
            return
        values = member_tree.item(selected[0], "values")
        member_id = int(values[0])
        member_name = values[1]

        detail = tk.Toplevel(self.root)
        detail.title(f"Detail Member - {member_name}")
        detail.geometry("1000x650")
        detail.configure(bg=BG)
        wrapper = tk.Frame(detail, bg=BG, padx=15, pady=15)
        wrapper.pack(fill="both", expand=True)
        tk.Label(
            wrapper, text=f"DETAIL MEMBER: {member_name}",
            bg=BG, fg=DARK, font=("Arial", 16, "bold")
        ).pack(anchor="w", pady=(0, 10))

        vehicle_frame = tk.LabelFrame(
            wrapper, text="Kendaraan Terdaftar",
            bg="white", padx=8, pady=8
        )
        vehicle_frame.pack(fill="both", expand=True, pady=5)
        vehicle_cols = ("nopol", "merk", "tipe", "tahun", "km")
        vehicle_tree = ttk.Treeview(
            vehicle_frame, columns=vehicle_cols, show="headings", height=6
        )
        for col, label, width in zip(
            vehicle_cols,
            ("Nomor Polisi", "Merk", "Tipe", "Tahun", "Kilometer"),
            (130, 120, 160, 80, 120)
        ):
            vehicle_tree.heading(col, text=label)
            vehicle_tree.column(col, width=width, anchor="center")
        vehicle_tree.pack(fill="both", expand=True)

        service_frame = tk.LabelFrame(
            wrapper, text="Riwayat Servis Member",
            bg="white", padx=8, pady=8
        )
        service_frame.pack(fill="both", expand=True, pady=5)
        service_cols = ("tanggal", "nopol", "motor", "jenis", "km", "biaya")
        service_tree = ttk.Treeview(
            service_frame, columns=service_cols,
            show="headings", height=7
        )
        for col, label, width in zip(
            service_cols,
            ("Tanggal", "Nopol", "Motor", "Jenis Servis", "KM", "Biaya"),
            (100, 110, 150, 150, 100, 130)
        ):
            service_tree.heading(col, text=label)
            service_tree.column(col, width=width, anchor="center")
        service_tree.pack(fill="both", expand=True)

        with koneksi() as conn:
            vehicles = conn.execute("""
                SELECT id, nomor_polisi, merk, tipe, tahun, kilometer_saat_ini
                FROM kendaraan WHERE user_id=? ORDER BY id DESC
            """, (member_id,)).fetchall()
            services = conn.execute("""
                SELECT r.tanggal_servis, k.nomor_polisi, k.merk, k.tipe,
                       r.jenis_servis, r.km_saat_servis, r.biaya
                FROM riwayat_servis r
                JOIN kendaraan k ON k.id=r.id_kendaraan
                WHERE k.user_id=?
                ORDER BY r.tanggal_servis DESC, r.id DESC
            """, (member_id,)).fetchall()

        for row in vehicles:
            vehicle_tree.insert(
                "", "end",
                values=(row[1], row[2], row[3], row[4], format_km(row[5]))
            )
        for row in services:
            service_tree.insert(
                "", "end",
                values=(row[0], row[1], f"{row[2]} {row[3]}",
                        row[4], format_km(row[5]), rupiah(row[6]))
            )

    def admin_form_tambah_kendaraan(self):
        """Admin mendaftarkan kendaraan dan menentukan pemilik/member."""
        with koneksi() as conn:
            members = conn.execute(
                "SELECT id, nama, username FROM users WHERE role='user' ORDER BY nama"
            ).fetchall()
        if not members:
            messagebox.showinfo("Data Member", "Belum ada member. Minta pengguna membuat akun terlebih dahulu.")
            return

        win = self.jendela_form("Input Data Kendaraan (Admin)")
        tk.Label(win, text="Pilih pemilik kendaraan", bg="white").pack(anchor="w")
        owner = ttk.Combobox(
            win, state="readonly",
            values=[f"{m[0]} | {m[1]} (@{m[2]})" for m in members]
        )
        owner.pack(fill="x", pady=(3, 12))
        owner.current(0)

        fields = {}
        for label in ("Nomor Polisi", "Merk", "Tipe", "Tahun", "Kilometer Saat Ini"):
            fields[label] = self.buat_input(win, label)

        def simpan():
            nopol = fields["Nomor Polisi"].get().strip().upper()
            merk = fields["Merk"].get().strip()
            tipe = fields["Tipe"].get().strip()
            try:
                owner_id = int(owner.get().split("|")[0].strip())
                tahun = int(fields["Tahun"].get())
                km = int(fields["Kilometer Saat Ini"].get())
                if not nopol or not merk or not tipe:
                    raise ValueError
                if tahun < 1900 or tahun > date.today().year + 1 or km < 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror(
                    "Input tidak valid",
                    "Pilih pemilik dan lengkapi nomor polisi, merk, tipe, tahun, serta kilometer."
                )
                return
            try:
                with koneksi() as conn:
                    conn.execute(
                        """INSERT INTO kendaraan
                           (user_id, nomor_polisi, merk, tipe, tahun, kilometer_saat_ini)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (owner_id, nopol, merk, tipe, tahun, km)
                    )
            except sqlite3.IntegrityError as error:
                messagebox.showerror("Gagal menyimpan", f"Data kendaraan tidak dapat disimpan: {error}")
                return
            messagebox.showinfo("Berhasil", "Data kendaraan berhasil ditambahkan ke akun member.")
            win.destroy()
            self.tampilkan_dashboard()

        self.buat_tombol(win, "SIMPAN DATA KENDARAAN", simpan, GREEN).pack(fill="x", pady=10)

    def admin_menu_servis(self):
        """Pusat menu servis umum untuk administrator."""
        win = tk.Toplevel(self.root)
        win.title("Menu Servis Umum - CARE-MOTOR")
        win.geometry("720x500")
        win.configure(bg=BG)
        frame = tk.Frame(win, bg=BG, padx=22, pady=20)
        frame.pack(fill="both", expand=True)
        tk.Label(
            frame, text="PUSAT MENU SERVIS UMUM",
            bg=BG, fg=DARK, font=("Arial", 18, "bold")
        ).pack(anchor="w", pady=(0, 6))
        tk.Label(
            frame,
            text="Kelola catatan servis, pantau jenis perawatan, dan lihat rekap servis seluruh member.",
            bg=BG, fg="#5b6b79", wraplength=650
        ).pack(anchor="w", pady=(0, 16))

        actions = [
            ("Seluruh Riwayat Servis", self.admin_data_servis),
            ("Statistik Servis", self.admin_statistik_servis),
            ("Laporan Servis Bulanan", self.admin_laporan_bulanan),
            ("Pencarian Data Servis", self.admin_pencarian),
            ("Ekspor Data Servis", self.admin_ekspor_servis),
        ]
        panel = tk.Frame(frame, bg="white", padx=16, pady=16)
        panel.pack(fill="both", expand=True)
        for index, (label, callback) in enumerate(actions):
            self.buat_tombol(panel, label, callback).grid(
                row=index // 2, column=index % 2, sticky="ew",
                padx=7, pady=8
            )
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_columnconfigure(1, weight=1)
        self.buat_tombol(frame, "TUTUP", win.destroy, RED).pack(anchor="e", pady=(12, 0))

    def admin_data_kendaraan(self):
        """Menampilkan semua kendaraan yang terdaftar di aplikasi."""
        win, outer, tree = self.buat_tabel_admin(
            "Seluruh Kendaraan Terdaftar",
            ("id", "pemilik", "username", "nopol", "merk",
             "tipe", "tahun", "km"),
            ("ID", "Nama Pemilik", "Username", "Nomor Polisi",
             "Merk", "Tipe", "Tahun", "Kilometer"),
            (50, 170, 120, 120, 100, 130, 70, 110)
        )
        with koneksi() as conn:
            rows = conn.execute("""
                SELECT k.id, u.nama, u.username, k.nomor_polisi,
                       k.merk, k.tipe, k.tahun, k.kilometer_saat_ini
                FROM kendaraan k
                JOIN users u ON u.id=k.user_id
                ORDER BY k.id DESC
            """).fetchall()
        for row in rows:
            tree.insert(
                "", "end",
                values=(row[0], row[1], row[2], row[3], row[4],
                        row[5], row[6], format_km(row[7]))
            )
        self.buat_tombol(
            outer, "TUTUP", win.destroy, RED
        ).pack(anchor="e", pady=(10, 0))

    def admin_data_servis(self):
        """Menampilkan seluruh transaksi/catatan servis seluruh member."""
        win, outer, tree = self.buat_tabel_admin(
            "Seluruh Riwayat Servis",
            ("id", "pemilik", "nopol", "motor", "jenis",
             "tanggal", "km", "biaya", "target"),
            ("ID", "Nama Member", "Nomor Polisi", "Motor",
             "Jenis Servis", "Tanggal", "KM Servis",
             "Biaya", "Target Berikutnya"),
            (50, 160, 110, 150, 130, 100, 100, 120, 130)
        )
        with koneksi() as conn:
            rows = conn.execute("""
                SELECT r.id, u.nama, k.nomor_polisi, k.merk, k.tipe,
                       r.jenis_servis, r.tanggal_servis,
                       r.km_saat_servis, r.biaya,
                       r.km_target_berikutnya
                FROM riwayat_servis r
                JOIN kendaraan k ON k.id=r.id_kendaraan
                JOIN users u ON u.id=k.user_id
                ORDER BY r.tanggal_servis DESC, r.id DESC
            """).fetchall()
        for row in rows:
            tree.insert(
                "", "end",
                values=(row[0], row[1], row[2], f"{row[3]} {row[4]}",
                        row[5], row[6], format_km(row[7]),
                        rupiah(row[8]), format_km(row[9]))
            )
        self.buat_tombol(
            outer, "TUTUP", win.destroy, RED
        ).pack(anchor="e", pady=(10, 0))

    def admin_statistik_servis(self):
        """Rekap agregat: total servis, biaya, kendaraan, dan jenis servis."""
        win = tk.Toplevel(self.root)
        win.title("Statistik Servis CARE-MOTOR")
        win.geometry("800x600")
        win.configure(bg="white")
        frame = tk.Frame(win, bg="white", padx=20, pady=20)
        frame.pack(fill="both", expand=True)

        with koneksi() as conn:
            member_count = conn.execute(
                "SELECT COUNT(*) FROM users WHERE role='user'"
            ).fetchone()[0]
            vehicle_count = conn.execute(
                "SELECT COUNT(*) FROM kendaraan"
            ).fetchone()[0]
            service_count = conn.execute(
                "SELECT COUNT(*) FROM riwayat_servis"
            ).fetchone()[0]
            cost_total = conn.execute(
                "SELECT COALESCE(SUM(biaya), 0) FROM riwayat_servis"
            ).fetchone()[0]
            avg_cost = conn.execute(
                "SELECT COALESCE(AVG(biaya), 0) FROM riwayat_servis"
            ).fetchone()[0]
            service_types = conn.execute("""
                SELECT jenis_servis, COUNT(*) AS total,
                       COALESCE(SUM(biaya), 0) AS biaya
                FROM riwayat_servis
                GROUP BY jenis_servis
                ORDER BY total DESC, jenis_servis
            """).fetchall()
            vehicle_types = conn.execute("""
                SELECT merk, tipe, COUNT(*) AS total
                FROM kendaraan
                GROUP BY merk, tipe
                ORDER BY total DESC, merk, tipe
            """).fetchall()

        tk.Label(
            frame, text="STATISTIK SELURUH APLIKASI",
            bg="white", fg=DARK, font=("Arial", 18, "bold")
        ).pack(anchor="w", pady=(0, 15))
        stats = [
            ("Total Member", member_count),
            ("Total Kendaraan", vehicle_count),
            ("Total Servis", service_count),
            ("Total Biaya Servis", rupiah(cost_total)),
            ("Rata-rata Biaya Servis", rupiah(avg_cost)),
        ]
        for label, value in stats:
            row = tk.Frame(frame, bg="#edf3f8", padx=12, pady=8)
            row.pack(fill="x", pady=3)
            tk.Label(
                row, text=label, bg="#edf3f8", fg=DARK,
                font=("Arial", 10, "bold")
            ).pack(side="left")
            tk.Label(
                row, text=str(value), bg="#edf3f8", fg=PRIMARY,
                font=("Arial", 10, "bold")
            ).pack(side="right")

        tk.Label(
            frame, text="RINCIAN BERDASARKAN JENIS SERVIS",
            bg="white", fg=DARK, font=("Arial", 12, "bold")
        ).pack(anchor="w", pady=(18, 7))
        service_tree = ttk.Treeview(
            frame, columns=("jenis", "total", "biaya"),
            show="headings", height=6
        )
        for col, title, width in (
            ("jenis", "Jenis Servis", 250),
            ("total", "Jumlah Catatan", 150),
            ("biaya", "Total Biaya", 200),
        ):
            service_tree.heading(col, text=title)
            service_tree.column(col, width=width, anchor="center")
        service_tree.pack(fill="x")
        for row in service_types:
            service_tree.insert(
                "", "end", values=(row[0], row[1], rupiah(row[2]))
            )

        tk.Label(
            frame, text="JENIS MOTOR YANG TERDAFTAR",
            bg="white", fg=DARK, font=("Arial", 12, "bold")
        ).pack(anchor="w", pady=(16, 7))
        vehicle_tree = ttk.Treeview(
            frame, columns=("merk", "tipe", "jumlah"),
            show="headings", height=5
        )
        for col, title, width in (
            ("merk", "Merk", 180), ("tipe", "Tipe", 220),
            ("jumlah", "Jumlah Kendaraan", 160)
        ):
            vehicle_tree.heading(col, text=title)
            vehicle_tree.column(col, width=width, anchor="center")
        vehicle_tree.pack(fill="x")
        for row in vehicle_types:
            vehicle_tree.insert("", "end", values=row)


    def admin_laporan_bulanan(self):
        """Menyajikan jumlah servis dan biaya yang tercatat per bulan."""
        win = tk.Toplevel(self.root)
        win.title("Laporan Servis Bulanan - CARE-MOTOR")
        win.geometry("900x570")
        win.configure(bg="white")
        frame = tk.Frame(win, bg="white", padx=18, pady=18)
        frame.pack(fill="both", expand=True)

        tk.Label(
            frame, text="LAPORAN SERVIS PER BULAN",
            bg="white", fg=DARK, font=("Arial", 17, "bold")
        ).pack(anchor="w", pady=(0, 12))

        columns = ("bulan", "jumlah", "biaya", "rata")
        tree = ttk.Treeview(frame, columns=columns, show="headings")
        headings = [
            ("bulan", "Bulan", 180),
            ("jumlah", "Jumlah Servis", 160),
            ("biaya", "Total Biaya", 180),
            ("rata", "Rata-rata Biaya", 180),
        ]
        for col, title, width in headings:
            tree.heading(col, text=title)
            tree.column(col, width=width, anchor="center")
        tree.pack(fill="both", expand=True)

        with koneksi() as conn:
            rows = conn.execute("""
                SELECT substr(tanggal_servis, 1, 7) AS periode,
                       COUNT(*) AS jumlah,
                       COALESCE(SUM(biaya), 0) AS total,
                       COALESCE(AVG(biaya), 0) AS rata
                FROM riwayat_servis
                GROUP BY substr(tanggal_servis, 1, 7)
                ORDER BY periode DESC
            """).fetchall()

        total_jumlah = 0
        total_biaya = 0
        for periode, jumlah, biaya, rata in rows:
            total_jumlah += jumlah
            total_biaya += biaya
            tree.insert(
                "", "end",
                values=(periode, jumlah, rupiah(biaya), rupiah(rata))
            )

        summary = tk.Frame(frame, bg="#edf3f8", padx=12, pady=10)
        summary.pack(fill="x", pady=(12, 0))
        tk.Label(
            summary, text=f"Total catatan servis: {total_jumlah}",
            bg="#edf3f8", fg=DARK, font=("Arial", 10, "bold")
        ).pack(anchor="w")
        tk.Label(
            summary, text=f"Total biaya tercatat: {rupiah(total_biaya)}",
            bg="#edf3f8", fg=DARK, font=("Arial", 10, "bold")
        ).pack(anchor="w", pady=(4, 0))

        if not rows:
            tk.Label(
                frame, text="Belum ada data servis untuk dibuat laporan.",
                bg="white", fg="#657786"
            ).pack(pady=10)

        self.buat_tombol(
            frame, "TUTUP", win.destroy, RED
        ).pack(anchor="e", pady=(12, 0))

    def admin_hitung_member_aktif(self):
        """Menghitung member yang pernah memasukkan kendaraan ke aplikasi."""
        with koneksi() as conn:
            return conn.execute("""
                SELECT COUNT(DISTINCT u.id)
                FROM users u
                JOIN kendaraan k ON k.user_id=u.id
                WHERE u.role='user'
            """).fetchone()[0]

    def admin_hitung_member_belum_ada_motor(self):
        """Menghitung member yang belum mendaftarkan kendaraan."""
        with koneksi() as conn:
            return conn.execute("""
                SELECT COUNT(*)
                FROM users u
                WHERE u.role='user'
                  AND NOT EXISTS (
                      SELECT 1 FROM kendaraan k WHERE k.user_id=u.id
                  )
            """).fetchone()[0]

    def admin_hitung_motor_per_merk(self):
        """Menghasilkan rekap jumlah motor berdasarkan merk."""
        with koneksi() as conn:
            return conn.execute("""
                SELECT merk, COUNT(*) AS jumlah
                FROM kendaraan
                GROUP BY merk
                ORDER BY jumlah DESC, merk ASC
            """).fetchall()

    def admin_hitung_servis_per_jenis(self):
        """Menghasilkan rekap jumlah catatan untuk setiap jenis servis."""
        with koneksi() as conn:
            return conn.execute("""
                SELECT jenis_servis, COUNT(*) AS jumlah,
                       COALESCE(SUM(biaya), 0) AS total_biaya
                FROM riwayat_servis
                GROUP BY jenis_servis
                ORDER BY jumlah DESC, jenis_servis ASC
            """).fetchall()

    def admin_data_ringkas(self):
        """Mengambil metrik utama admin dalam satu fungsi yang mudah diuji."""
        with koneksi() as conn:
            member = conn.execute(
                "SELECT COUNT(*) FROM users WHERE role='user'"
            ).fetchone()[0]
            kendaraan = conn.execute(
                "SELECT COUNT(*) FROM kendaraan"
            ).fetchone()[0]
            servis = conn.execute(
                "SELECT COUNT(*) FROM riwayat_servis"
            ).fetchone()[0]
            biaya = conn.execute(
                "SELECT COALESCE(SUM(biaya), 0) FROM riwayat_servis"
            ).fetchone()[0]
        return {
            "member": member,
            "kendaraan": kendaraan,
            "servis": servis,
            "biaya": biaya,
            "member_aktif": self.admin_hitung_member_aktif(),
            "member_tanpa_motor": self.admin_hitung_member_belum_ada_motor(),
        }

    def admin_pencarian(self):
        """Pencarian sederhana lintas member, kendaraan, dan riwayat servis."""
        win = tk.Toplevel(self.root)
        win.title("Pencarian Data CARE-MOTOR")
        win.geometry("1050x600")
        win.configure(bg="white")
        frame = tk.Frame(win, bg="white", padx=16, pady=16)
        frame.pack(fill="both", expand=True)
        tk.Label(
            frame, text="CARI MEMBER / NOMOR POLISI / MOTOR / SERVIS",
            bg="white", fg=DARK, font=("Arial", 15, "bold")
        ).pack(anchor="w", pady=(0, 10))
        entry = tk.Entry(frame, font=("Arial", 11))
        entry.pack(fill="x", pady=5)
        tree = ttk.Treeview(
            frame,
            columns=("kategori", "pemilik", "kendaraan", "detail", "tanggal"),
            show="headings"
        )
        for col, title, width in (
            ("kategori", "Kategori", 100), ("pemilik", "Pemilik", 170),
            ("kendaraan", "Kendaraan / Nopol", 220),
            ("detail", "Detail", 300), ("tanggal", "Tanggal", 120)
        ):
            tree.heading(col, text=title)
            tree.column(col, width=width, anchor="center")
        tree.pack(fill="both", expand=True, pady=8)

        def cari():
            keyword = entry.get().strip()
            if not keyword:
                messagebox.showwarning(
                    "Pencarian", "Masukkan kata kunci pencarian."
                )
                return
            for item in tree.get_children():
                tree.delete(item)
            like = f"%{keyword}%"
            with koneksi() as conn:
                members = conn.execute("""
                    SELECT nama, username FROM users
                    WHERE role='user' AND (nama LIKE ? OR username LIKE ?)
                """, (like, like)).fetchall()
                vehicles = conn.execute("""
                    SELECT u.nama, k.nomor_polisi, k.merk, k.tipe,
                           k.tahun, k.kilometer_saat_ini
                    FROM kendaraan k JOIN users u ON u.id=k.user_id
                    WHERE k.nomor_polisi LIKE ? OR k.merk LIKE ?
                       OR k.tipe LIKE ? OR u.nama LIKE ?
                """, (like, like, like, like)).fetchall()
                services = conn.execute("""
                    SELECT u.nama, k.nomor_polisi, k.merk, k.tipe,
                           r.jenis_servis, r.tanggal_servis
                    FROM riwayat_servis r
                    JOIN kendaraan k ON k.id=r.id_kendaraan
                    JOIN users u ON u.id=k.user_id
                    WHERE r.jenis_servis LIKE ? OR r.catatan LIKE ?
                       OR u.nama LIKE ? OR k.nomor_polisi LIKE ?
                """, (like, like, like, like)).fetchall()

            for row in members:
                tree.insert(
                    "", "end",
                    values=("Member", row[0], "-", f"Username: {row[1]}", "-")
                )
            for row in vehicles:
                tree.insert(
                    "", "end",
                    values=("Kendaraan", row[0], row[1],
                            f"{row[2]} {row[3]} | Tahun {row[4]} | "
                            f"{format_km(row[5])}", "-")
                )
            for row in services:
                tree.insert(
                    "", "end",
                    values=("Servis", row[0], row[1],
                            f"{row[2]} {row[3]} | {row[4]}", row[5])
                )
            if not tree.get_children():
                messagebox.showinfo(
                    "Pencarian", "Data yang cocok tidak ditemukan."
                )

        controls = tk.Frame(frame, bg="white")
        controls.pack(fill="x")
        self.buat_tombol(controls, "CARI", cari, GREEN).pack(side="left")
        self.buat_tombol(controls, "TUTUP", win.destroy, RED).pack(side="right")
        entry.bind("<Return>", lambda event: cari())

    def admin_ekspor_member(self):
        """Ekspor daftar akun member tanpa menyertakan password."""
        with koneksi() as conn:
            rows = conn.execute("""
                SELECT id, nama, username FROM users
                WHERE role='user' ORDER BY id
            """).fetchall()
        self.simpan_csv_admin(
            "data_member.csv",
            ["ID", "Nama", "Username"],
            rows
        )

    def admin_ekspor_kendaraan(self):
        """Ekspor semua kendaraan beserta nama pemiliknya."""
        with koneksi() as conn:
            rows = conn.execute("""
                SELECT u.nama, u.username, k.nomor_polisi, k.merk,
                       k.tipe, k.tahun, k.kilometer_saat_ini
                FROM kendaraan k JOIN users u ON u.id=k.user_id
                ORDER BY u.nama, k.nomor_polisi
            """).fetchall()
        self.simpan_csv_admin(
            "data_kendaraan.csv",
            ["Nama Pemilik", "Username", "Nomor Polisi", "Merk",
             "Tipe", "Tahun", "Kilometer"],
            rows
        )

    def admin_ekspor_servis(self):
        """Ekspor semua riwayat servis dan identitas pemilik kendaraan."""
        with koneksi() as conn:
            rows = conn.execute("""
                SELECT u.nama, k.nomor_polisi, k.merk, k.tipe,
                       r.jenis_servis, r.tanggal_servis,
                       r.km_saat_servis, r.biaya,
                       r.km_target_berikutnya, r.catatan
                FROM riwayat_servis r
                JOIN kendaraan k ON k.id=r.id_kendaraan
                JOIN users u ON u.id=k.user_id
                ORDER BY r.tanggal_servis DESC
            """).fetchall()
        self.simpan_csv_admin(
            "data_riwayat_servis.csv",
            ["Nama Member", "Nomor Polisi", "Merk", "Tipe",
             "Jenis Servis", "Tanggal", "KM Servis", "Biaya",
             "Target Berikutnya", "Catatan"],
            rows
        )

    def simpan_csv_admin(self, nama_awal, headers, rows):
        """Dialog penyimpanan CSV bersama penanganan kesalahan file."""
        if not rows:
            messagebox.showinfo(
                "Ekspor CSV", "Tidak ada data untuk diekspor."
            )
            return
        lokasi = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile=nama_awal
        )
        if not lokasi:
            return
        try:
            with open(
                lokasi, "w", newline="", encoding="utf-8-sig"
            ) as output:
                writer = csv.writer(output)
                writer.writerow(headers)
                writer.writerows(rows)
            messagebox.showinfo(
                "Ekspor Berhasil", f"Data berhasil disimpan ke:\n{lokasi}"
            )
        except OSError as error:
            messagebox.showerror(
                "Ekspor Gagal", f"Tidak dapat menyimpan file:\n{error}"
            )

    def logout(self):
        if messagebox.askyesno("Logout", "Yakin ingin keluar dari akun?"):
            self.user = None
            self.kendaraan_aktif = None
            self.tampilkan_login()

    # -------------------- KENDARAAN --------------------
    def ambil_kendaraan(self):
        with koneksi() as conn:
            return conn.execute("""
                SELECT id, nomor_polisi, merk, tipe, tahun, kilometer_saat_ini
                FROM kendaraan WHERE user_id=? ORDER BY id DESC
            """, (self.user["id"],)).fetchall()

    def form_tambah_kendaraan(self, kembali_ke_data=False):
        """Member memasukkan data motor miliknya sendiri."""
        win = self.jendela_form("Input Data Motor Saya")
        fields = {}
        for label in ("Nomor Polisi", "Merk", "Tipe", "Tahun", "Kilometer Saat Ini"):
            fields[label] = self.buat_input(win, label)
        def simpan():
            nopol = fields["Nomor Polisi"].get().strip().upper()
            merk = fields["Merk"].get().strip()
            tipe = fields["Tipe"].get().strip()
            try:
                tahun = int(fields["Tahun"].get())
                km = int(fields["Kilometer Saat Ini"].get())
                if not nopol or not merk or not tipe:
                    raise ValueError
                if tahun < 1900 or tahun > date.today().year + 1 or km < 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Input tidak valid", "Lengkapi data. Tahun dan kilometer harus berupa angka yang valid.")
                return
            with koneksi() as conn:
                conn.execute("""INSERT INTO kendaraan
                    (user_id, nomor_polisi, merk, tipe, tahun, kilometer_saat_ini)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (self.user["id"], nopol, merk, tipe, tahun, km))
            messagebox.showinfo("Berhasil", "Data motor berhasil disimpan ke akun Anda.")
            win.destroy()
            if kembali_ke_data:
                self.jendela_kendaraan()
            else:
                self.tampilkan_dashboard()
        self.buat_tombol(win, "SIMPAN DATA MOTOR SAYA", simpan, GREEN).pack(fill="x", pady=10)

    def jendela_form(self, title):
        win = tk.Toplevel(self.root)
        win.title(title)
        win.configure(bg="white")
        win.geometry("420x560")
        win.transient(self.root)
        win.grab_set()
        frame = tk.Frame(win, bg="white", padx=24, pady=20)
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text=title, bg="white", fg=DARK,
                 font=("Arial", 16, "bold")).pack(anchor="w", pady=(0, 15))
        return frame

    def pilih_kendaraan(self, parent, wajib=True):
        data = self.ambil_kendaraan()
        if not data:
            messagebox.showinfo("Kendaraan", "Tambahkan kendaraan terlebih dahulu.")
            return None, None
        pilihan = ttk.Combobox(parent, state="readonly",
            values=[f"{d[0]} | {d[1]} | {d[2]} {d[3]}" for d in data])
        pilihan.pack(fill="x", pady=(3, 12))
        pilihan.current(0)
        return pilihan, data

    def jendela_kendaraan(self):
        win = tk.Toplevel(self.root)
        win.title("Data Kendaraan")
        win.geometry("850x430")
        frame = tk.Frame(win, padx=15, pady=15)
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text="DATA KENDARAAN SAYA", font=("Arial", 16, "bold")).pack(anchor="w", pady=8)
        tk.Label(
            frame,
            text="Tambahkan motor milik Anda sendiri melalui tombol di bawah ini.",
            font=("Arial", 9), fg="#526273"
        ).pack(anchor="w", pady=(0, 8))
        tk.Button(
            frame, text="+ INPUT DATA MOTOR SAYA",
            command=lambda: self.form_tambah_kendaraan(kembali_ke_data=True),
            bg=GREEN, fg="white", activebackground="#218838",
            relief="flat", padx=14, pady=9, cursor="hand2",
            font=("Arial", 10, "bold")
        ).pack(anchor="w", pady=(0, 10))
        cols = ("id", "nopol", "merk", "tipe", "tahun", "km")
        tree = ttk.Treeview(frame, columns=cols, show="headings")
        headings = ["ID", "Nomor Polisi", "Merk", "Tipe", "Tahun", "Kilometer"]
        widths = [45, 130, 100, 130, 70, 110]
        for col, heading, width in zip(cols, headings, widths):
            tree.heading(col, text=heading)
            tree.column(col, width=width, anchor="center")
        tree.pack(fill="both", expand=True)
        for row in self.ambil_kendaraan():
            tree.insert("", "end", values=(row[0], row[1], row[2], row[3], row[4], format_km(row[5])))

    def form_update_km(self):
        win = self.jendela_form("Update Kilometer")
        tk.Label(win, text="Pilih kendaraan", bg="white").pack(anchor="w")
        pilihan, data = self.pilih_kendaraan(win)
        if pilihan is None:
            win.destroy()
            return
        entry = self.buat_input(win, "Kilometer terbaru")
        def simpan():
            try:
                km_baru = int(entry.get())
                selected_id = int(pilihan.get().split("|")[0].strip())
                lama = next(d[5] for d in data if d[0] == selected_id)
                if km_baru < lama:
                    messagebox.showerror("Tidak valid", f"Kilometer tidak boleh berkurang. KM saat ini: {format_km(lama)}")
                    return
            except (ValueError, StopIteration):
                messagebox.showerror("Input", "Masukkan kilometer berupa angka bulat.")
                return
            with koneksi() as conn:
                conn.execute("UPDATE kendaraan SET kilometer_saat_ini=? WHERE id=? AND user_id=?",
                             (km_baru, selected_id, self.user["id"]))
            messagebox.showinfo("Berhasil", "Kilometer kendaraan diperbarui.")
            win.destroy()
            self.tampilkan_dashboard()
        self.buat_tombol(win, "UPDATE", simpan, GREEN).pack(fill="x", pady=10)

    # -------------------- SERVIS & PENGINGAT --------------------
    def form_tambah_servis(self):
        win = self.jendela_form("Catat Riwayat Servis")
        tk.Label(win, text="Pilih kendaraan", bg="white").pack(anchor="w")
        pilihan, data = self.pilih_kendaraan(win)
        if pilihan is None:
            win.destroy()
            return
        tk.Label(win, text="Jenis servis", bg="white").pack(anchor="w")
        jenis = ttk.Combobox(win, state="readonly", values=list(INTERVAL_SERVIS.keys()))
        jenis.pack(fill="x", pady=(3, 12))
        jenis.current(0)
        tanggal = self.buat_input(win, "Tanggal servis (YYYY-MM-DD)")
        tanggal.insert(0, date.today().strftime("%d-%m-%Y"))
        km = self.buat_input(win, "Kilometer saat servis")
        biaya = self.buat_input(win, "Biaya servis (angka)")
        catatan = self.buat_input(win, "Catatan (boleh kosong)")
        def simpan():
            try:
                kendaraan_id = int(pilihan.get().split("|")[0].strip())
                km_servis = int(km.get())
                biaya_servis = int(biaya.get())
                tanggal_obj = datetime.strptime(tanggal.get().strip(), "%d-%m-%Y").date()
                kendaraan = next(d for d in data if d[0] == kendaraan_id)
                if km_servis < 0 or biaya_servis < 0:
                    raise ValueError
                if km_servis > kendaraan[5]:
                    messagebox.showerror("Kilometer", "KM servis tidak boleh melebihi kilometer kendaraan saat ini.")
                    return
                interval = INTERVAL_SERVIS[jenis.get()]
                target = km_servis + interval
            except ValueError:
                messagebox.showerror("Input tidak valid", "Periksa tanggal (DD-MM-YYYY), kilometer, dan biaya.")
                return
            with koneksi() as conn:
                conn.execute("""INSERT INTO riwayat_servis
                    (id_kendaraan, jenis_servis, km_saat_servis, tanggal_servis,
                     biaya, km_target_berikutnya, catatan)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (kendaraan_id, jenis.get(), km_servis, tanggal_obj.isoformat(),
                     biaya_servis, target, catatan.get().strip()))
            messagebox.showinfo("Berhasil", f"Riwayat tersimpan.\nTarget servis berikutnya: {format_km(target)}")
            win.destroy()
            self.tampilkan_dashboard()
        self.buat_tombol(win, "SIMPAN RIWAYAT", simpan, GREEN).pack(fill="x", pady=10)

    def ambil_semua_riwayat(self):
        with koneksi() as conn:
            return conn.execute("""
                SELECT r.id, k.id, k.nomor_polisi, k.merk, k.tipe,
                       r.jenis_servis, r.tanggal_servis, r.km_saat_servis,
                       r.biaya, r.km_target_berikutnya, r.catatan,
                       k.kilometer_saat_ini
                FROM riwayat_servis r
                JOIN kendaraan k ON k.id=r.id_kendaraan
                WHERE k.user_id=?
                ORDER BY r.tanggal_servis DESC, r.id DESC
            """, (self.user["id"],)).fetchall()

    def hitung_notifikasi(self):
        # Jadwal dihitung dari catatan servis terakhir untuk setiap jenis servis.
        kendaraan = self.ambil_kendaraan()
        hasil = []
        riwayat = self.ambil_semua_riwayat()
        for motor in kendaraan:
            motor_id, nopol, merk, tipe, tahun, km_sekarang = motor
            terakhir = {}
            for row in riwayat:
                if row[1] == motor_id and row[5] not in terakhir:
                    terakhir[row[5]] = row
            for jenis, row in terakhir.items():
                target = row[9]
                sisa = target - km_sekarang
                if sisa < 0:
                    status = "TERLAMBAT"
                elif sisa < 500:
                    status = "MENDEKATI SERVIS"
                else:
                    status = "MASIH AMAN"
                hasil.append({
                    "nopol": nopol, "motor": f"{merk} {tipe}", "jenis": jenis,
                    "km": km_sekarang, "target": target, "sisa": sisa, "status": status
                })
        return hasil

    def jendela_jadwal(self):
        """Menampilkan target servis berikutnya untuk setiap kendaraan."""
        win = tk.Toplevel(self.root)
        win.title("Jadwal Servis Berikutnya - CARE-MOTOR")
        win.geometry("900x450")
        frame = tk.Frame(win, padx=15, pady=15)
        frame.pack(fill="both", expand=True)

        tk.Label(
            frame, text="JADWAL SERVIS BERIKUTNYA",
            font=("Arial", 16, "bold")
        ).pack(anchor="w", pady=8)

        cols = ("nopol", "motor", "jenis", "km", "target", "sisa")
        tree = ttk.Treeview(frame, columns=cols, show="headings")
        headings = [
            "Nomor Polisi", "Motor", "Jenis Servis",
            "KM Saat Ini", "Target Berikutnya", "Sisa/Jarak"
        ]
        widths = [120, 150, 140, 120, 140, 120]
        for col, heading, width in zip(cols, headings, widths):
            tree.heading(col, text=heading)
            tree.column(col, width=width, anchor="center")
        tree.pack(fill="both", expand=True)

        data = self.hitung_notifikasi()
        for item in data:
            sisa = item["sisa"]
            if sisa < 0:
                keterangan = format_km(abs(sisa)) + " terlambat"
            else:
                keterangan = format_km(sisa) + " tersisa"
            tree.insert(
                "", "end",
                values=(
                    item["nopol"], item["motor"], item["jenis"],
                    format_km(item["km"]), format_km(item["target"]),
                    keterangan
                )
            )

        if not data:
            tk.Label(
                frame, text="Belum ada riwayat servis untuk membuat jadwal.",
                fg="#657786"
            ).pack(pady=10)

    def jendela_notifikasi(self):
        win = tk.Toplevel(self.root)
        win.title("Jadwal dan Notifikasi Servis")
        win.geometry("900x470")
        frame = tk.Frame(win, padx=15, pady=15)
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text="PEMANTAUAN JADWAL SERVIS", font=("Arial", 16, "bold")).pack(anchor="w", pady=8)
        cols = ("nopol", "motor", "jenis", "km", "target", "status", "sisa")
        tree = ttk.Treeview(frame, columns=cols, show="headings")
        for c, h, w in zip(cols, ["Nopol", "Motor", "Jenis Servis", "KM Saat Ini", "Target", "Status", "Selisih"], [100, 120, 120, 100, 100, 145, 100]):
            tree.heading(c, text=h)
            tree.column(c, width=w, anchor="center")
        tree.pack(fill="both", expand=True)
        data = self.hitung_notifikasi()
        for d in data:
            selisih = format_km(abs(d["sisa"])) + (" terlambat" if d["sisa"] < 0 else " tersisa")
            tree.insert("", "end", values=(d["nopol"], d["motor"], d["jenis"],
                format_km(d["km"]), format_km(d["target"]), d["status"], selisih))
        if not data:
            tk.Label(frame, text="Belum ada riwayat servis untuk dihitung.", fg="#657786").pack(pady=10)

    def jendela_riwayat(self):
        win = tk.Toplevel(self.root)
        win.title("Riwayat Servis")
        win.geometry("1050x480")
        frame = tk.Frame(win, padx=15, pady=15)
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text="SELURUH RIWAYAT SERVIS", font=("Arial", 16, "bold")).pack(anchor="w", pady=8)
        cols = ("tanggal", "nopol", "motor", "jenis", "km", "biaya", "target", "catatan")
        tree = ttk.Treeview(frame, columns=cols, show="headings")
        heads = ["Tanggal", "Nopol", "Motor", "Jenis", "KM Servis", "Biaya", "Target Berikutnya", "Catatan"]
        widths = [90, 90, 110, 110, 90, 100, 120, 180]
        for c, h, w in zip(cols, heads, widths):
            tree.heading(c, text=h)
            tree.column(c, width=w, anchor="center")
        tree.pack(fill="both", expand=True)
        for r in self.ambil_semua_riwayat():
            tree.insert("", "end", values=(r[6], r[2], f"{r[3]} {r[4]}", r[5],
                format_km(r[7]), rupiah(r[8]), format_km(r[9]), r[10] or "-"))

    # -------------------- LAPORAN & ANALISIS --------------------
    def jendela_laporan(self):
        data_motor = self.ambil_kendaraan()
        if not data_motor:
            messagebox.showinfo("Laporan", "Belum ada kendaraan.")
            return
        win = tk.Toplevel(self.root)
        win.title("Laporan Kendaraan")
        win.geometry("650x570")
        frame = tk.Frame(win, bg="white", padx=22, pady=18)
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text="LAPORAN CARE-MOTOR", bg="white", fg=PRIMARY,
                 font=("Arial", 19, "bold")).pack(anchor="w", pady=(0, 12))
        tk.Label(frame, text="Pilih kendaraan", bg="white").pack(anchor="w")
        pilih = ttk.Combobox(frame, state="readonly",
            values=[f"{d[0]} | {d[1]} | {d[2]} {d[3]}" for d in data_motor])
        pilih.pack(fill="x", pady=7)
        pilih.current(0)
        area = tk.Text(frame, height=20, font=("Consolas", 10), wrap="word")
        area.pack(fill="both", expand=True, pady=8)
        def tampilkan():
            motor_id = int(pilih.get().split("|")[0].strip())
            motor = next(d for d in data_motor if d[0] == motor_id)
            records = [r for r in self.ambil_semua_riwayat() if r[1] == motor_id]
            total = sum(r[8] for r in records)
            target_terdekat = min(
                [r for r in self.hitung_notifikasi() if r["nopol"] == motor[1]],
                key=lambda x: x["sisa"], default=None
            )
            area.delete("1.0", "end")
            area.insert("end", "====================================\n")
            area.insert("end", "          CARE-MOTOR REPORT\n")
            area.insert("end", "====================================\n")
            area.insert("end", f"Nomor Polisi : {motor[1]}\n")
            area.insert("end", f"Motor        : {motor[2]} {motor[3]}\n")
            area.insert("end", f"Tahun        : {motor[4]}\n")
            area.insert("end", f"KM Saat Ini  : {format_km(motor[5])}\n")
            area.insert("end", f"Total Servis : {len(records)} kali\n")
            area.insert("end", f"Total Biaya  : {rupiah(total)}\n")
            area.insert("end", f"Rata-rata    : {rupiah(total / len(records)) if records else rupiah(0)}\n")
            if target_terdekat:
                area.insert("end", f"Servis       : {target_terdekat['jenis']}\n")
                area.insert("end", f"Target       : {format_km(target_terdekat['target'])}\n")
                area.insert("end", f"Status       : {target_terdekat['status']}\n")
            else:
                area.insert("end", "Jadwal       : Belum ada riwayat servis\n")
            area.insert("end", "====================================\n")
        self.buat_tombol(frame, "BUAT LAPORAN", tampilkan).pack(anchor="e")
        tampilkan()

    def jendela_analisis(self):
        win = tk.Toplevel(self.root)
        win.title("Analisis Perawatan")
        win.geometry("760x560")
        frame = tk.Frame(win, padx=18, pady=18)
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text="ANALISIS PERAWATAN MOTOR", font=("Arial", 17, "bold")).pack(anchor="w", pady=8)
        area = tk.Text(frame, font=("Consolas", 10), wrap="word")
        area.pack(fill="both", expand=True)
        records = self.ambil_semua_riwayat()
        jumlah_per_jenis = {}
        total_biaya = sum(r[8] for r in records)
        for r in records:
            jumlah_per_jenis[r[5]] = jumlah_per_jenis.get(r[5], 0) + 1
        area.insert("end", f"Jumlah catatan servis : {len(records)}\n")
        area.insert("end", f"Total pengeluaran     : {rupiah(total_biaya)}\n")
        area.insert("end", f"Rata-rata per servis  : {rupiah(total_biaya / len(records)) if records else rupiah(0)}\n\n")
        area.insert("end", "PERINGKAT SERVIS PALING SERING\n")
        if jumlah_per_jenis:
            for nomor, (jenis, jumlah) in enumerate(sorted(jumlah_per_jenis.items(),
                    key=lambda item: item[1], reverse=True), start=1):
                area.insert("end", f"{nomor}. {jenis}: {jumlah} kali\n")
        else:
            area.insert("end", "Belum ada data servis.\n")
        area.insert("end", "\nPREDIKSI BIAYA TAHUNAN\n")
        # Estimasi sederhana dari rata-rata biaya per bulan yang tercatat.
        tanggal_valid = []
        for r in records:
            try:
                tanggal_valid.append(datetime.strptime(r[6], "%Y-%m-%d").date())
            except ValueError:
                pass
        if records and tanggal_valid:
            rentang_bulan = max(1, (max(tanggal_valid).year - min(tanggal_valid).year) * 12
                                + max(tanggal_valid).month - min(tanggal_valid).month + 1)
            prediksi = (total_biaya / rentang_bulan) * 12
            area.insert("end", f"Perkiraan biaya 12 bulan: {rupiah(prediksi)}\n")
            area.insert("end", "Catatan: estimasi berdasarkan rata-rata biaya dari data yang sudah dicatat.\n")
        else:
            area.insert("end", "Belum cukup data tanggal servis untuk membuat estimasi.\n")

        area.insert("end", "\nPROGRESS MENUJU SERVIS BERIKUTNYA\n")
        notifikasi = self.hitung_notifikasi()
        if not notifikasi:
            area.insert("end", "Belum ada jadwal servis yang dapat dihitung.\n")
        for d in notifikasi:
            interval = INTERVAL_SERVIS.get(d["jenis"], 0)
            # Persentase berdasarkan kilometer yang telah ditempuh sejak servis terakhir.
            km_terpakai = max(0, d["km"] - (d["target"] - interval))
            persen = min(100, int((km_terpakai / interval) * 100)) if interval else 0
            terisi = int(persen / 5)
            area.insert("end", f"\n{d['nopol']} - {d['jenis']}\n")
            area.insert("end", f"[{'#' * terisi}{'-' * (20 - terisi)}] {persen}%\n")
            area.insert("end", f"Target: {format_km(d['target'])} | Saat ini: {format_km(d['km'])}\n")

    def ekspor_csv(self):
        records = self.ambil_semua_riwayat()
        if not records:
            messagebox.showinfo("Ekspor CSV", "Belum ada riwayat servis untuk diekspor.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV", "*.csv")],
            initialfile="laporan_mototrack.csv"
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as file:
                writer = csv.writer(file)
                writer.writerow(["Tanggal", "Nomor Polisi", "Merk", "Tipe", "Jenis Servis",
                                 "KM Servis", "Biaya", "Target Berikutnya", "Catatan"])
                for r in records:
                    writer.writerow([r[6], r[2], r[3], r[4], r[5], r[7], r[8], r[9], r[10]])
            messagebox.showinfo("Berhasil", f"Laporan berhasil diekspor ke:\n{path}")
        except OSError as error:
            messagebox.showerror("Gagal mengekspor", str(error))


if __name__ == "__main__":
    buat_database()
    root = tk.Tk()
    app = CareMotorApp(root)
    root.mainloop()
