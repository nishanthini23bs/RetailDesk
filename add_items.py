import os
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
import threading

try:
    import cv2
    import zxingcpp
    from PIL import Image, ImageTk
    CV2_AVAILABLE = True
except Exception:
    CV2_AVAILABLE = False

DB_PATH = "db/billing.db"


def ensure_db():
    os.makedirs("db", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            barcode TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


class AddItems:
    def __init__(self, window):
        self.window = window
        self.window.title("Add Products")
        self.window.geometry("860x560")
        self.window.configure(bg="#0f1923")
        self.scanner_active = False
        self.cap = None
        self._current_frame = None
        self._last_scanned = ""
        ensure_db()
        self._build_ui()

    def _build_ui(self):
        # TOP BAR
        topbar = tk.Frame(self.window, bg="#0d1820", height=52)
        topbar.pack(fill=tk.X)
        topbar.pack_propagate(False)
        tk.Label(topbar, text="➕  Add Products to Inventory",
                 font=("Arial", 13, "bold"),
                 bg="#0d1820", fg="#cdd8e0").pack(side=tk.LEFT, padx=20, pady=14)
        self.cam_status = tk.Label(topbar, text="● Camera Off",
                                   font=("Arial", 10),
                                   bg="#0d1820", fg="#ff6b6b")
        self.cam_status.pack(side=tk.RIGHT, padx=20)

        # MAIN
        main = tk.Frame(self.window, bg="#0f1923")
        main.pack(fill=tk.BOTH, expand=True, padx=14, pady=12)
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        # ── LEFT: Camera ───────────────────────────────────────────────────
        left = tk.Frame(main, bg="#111d27", padx=12, pady=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        tk.Label(left, text="Scan Barcode (Optional)",
                 font=("Arial", 11, "bold"),
                 bg="#111d27", fg="#6a8fa0").pack(anchor=tk.W, pady=(0, 8))

        # Camera canvas
        self.cam_canvas = tk.Canvas(left, width=360, height=250,
                                    bg="#060e14",
                                    highlightthickness=1,
                                    highlightbackground="#1e2d3d")
        self.cam_canvas.pack(fill=tk.BOTH, expand=True)
        self._draw_placeholder()

        # Camera buttons
        btn_row = tk.Frame(left, bg="#111d27")
        btn_row.pack(fill=tk.X, pady=(10, 0))

        self.start_btn = tk.Button(btn_row, text="▶  Start Camera",
                                   font=("Arial", 10, "bold"),
                                   bg="#00d4aa", fg="#050505",
                                   bd=0, padx=14, pady=7,
                                   cursor="hand2",
                                   command=self.start_scanner)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.stop_btn = tk.Button(btn_row, text="■  Stop",
                                  font=("Arial", 10),
                                  bg="#2a3a4a", fg="#cdd8e0",
                                  bd=0, padx=14, pady=7,
                                  cursor="hand2",
                                  command=self.stop_scanner,
                                  state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT)

        # Scan result display
        self.scan_result = tk.Label(left, text="",
                                    font=("Arial", 10),
                                    bg="#111d27", fg="#00d4aa")
        self.scan_result.pack(anchor=tk.W, pady=(8, 0))

        tk.Label(left,
                 text="Tip: Hold barcode steady, 15-20cm from camera\nin good lighting for best results",
                 font=("Arial", 8), bg="#111d27", fg="#2e5060",
                 justify=tk.LEFT).pack(anchor=tk.W, pady=(6, 0))

        if not CV2_AVAILABLE:
            self.start_btn.config(state=tk.DISABLED,
                                  text="Camera unavailable",
                                  bg="#1a2a3a", fg="#3a6070")

        # ── RIGHT: Form ────────────────────────────────────────────────────
        right = tk.Frame(main, bg="#111d27", padx=20, pady=16)
        right.grid(row=0, column=1, sticky="nsew")

        tk.Label(right, text="Product Details",
                 font=("Arial", 11, "bold"),
                 bg="#111d27", fg="#6a8fa0").pack(anchor=tk.W, pady=(0, 14))

        fields = [
            ("Barcode",    "entry_barcode", "Scan or type manually"),
            ("Name",       "entry_name",    "Product name"),
            ("Price (Rs)", "entry_price",   "e.g. 50.00"),
            ("Quantity",   "entry_qty",     "Opening stock"),
        ]

        for label, attr, placeholder in fields:
            row = tk.Frame(right, bg="#111d27")
            row.pack(fill=tk.X, pady=6)
            tk.Label(row, text=label,
                     font=("Arial", 10), bg="#111d27",
                     fg="#6a8fa0", width=12, anchor=tk.W).pack(side=tk.LEFT)
            entry = tk.Entry(row, font=("Arial", 12),
                             bg="#162530", fg="#ffffff",
                             insertbackground="white",
                             relief=tk.FLAT, bd=8)
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
            setattr(self, attr, entry)

        # Buttons
        tk.Frame(right, bg="#1e2d3d", height=1).pack(fill=tk.X, pady=14)

        btn_frame = tk.Frame(right, bg="#111d27")
        btn_frame.pack(fill=tk.X)

        tk.Button(btn_frame, text="✅  Add / Restock",
                  font=("Arial", 11, "bold"),
                  bg="#00d4aa", fg="#050505",
                  bd=0, padx=16, pady=8,
                  cursor="hand2",
                  command=self.add_or_restock).pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(btn_frame, text="Clear",
                  font=("Arial", 10),
                  bg="#1e2d3d", fg="#6a8fa0",
                  bd=0, padx=12, pady=8,
                  cursor="hand2",
                  command=self.clear_fields).pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(btn_frame, text="Close",
                  font=("Arial", 10),
                  bg="#1e2d3d", fg="#6a8fa0",
                  bd=0, padx=12, pady=8,
                  cursor="hand2",
                  command=self.window.destroy).pack(side=tk.LEFT)

        # Status message
        self.status_lbl = tk.Label(right, text="",
                                   font=("Arial", 10),
                                   bg="#111d27", fg="#00d4aa",
                                   wraplength=300, justify=tk.LEFT)
        self.status_lbl.pack(anchor=tk.W, pady=(12, 0))

    # ─────────────────────────────────────── Camera ───────────────────────
    def _draw_placeholder(self):
        self.cam_canvas.delete("all")
        self.cam_canvas.create_text(
            180, 125,
            text="📷\n\nPress  ▶ Start Camera\nto scan product barcodes",
            fill="#2a4a5e", font=("Arial", 11),
            justify=tk.CENTER)

    def start_scanner(self):
        if not CV2_AVAILABLE:
            return
        self.scanner_active = True
        self._last_scanned = ""
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.cam_status.config(text="● Camera On", fg="#00d4aa")
        threading.Thread(target=self._scan_loop, daemon=True).start()
        self._update_canvas()

    def stop_scanner(self):
        self.scanner_active = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.cam_status.config(text="● Camera Off", fg="#ff6b6b")
        if self.cap:
            self.cap.release()
            self.cap = None
        self._draw_placeholder()

    def _scan_loop(self):
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)

        while self.scanner_active:
            ret, frame = self.cap.read()
            if not ret:
                break

            # Try multiple methods for best detection
            results = zxingcpp.read_barcodes(frame)
            if not results:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                results = zxingcpp.read_barcodes(gray)
            if not results:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                gray = cv2.equalizeHist(gray)
                results = zxingcpp.read_barcodes(gray)

            for r in results:
                code = r.text
                pos = r.position
                pts = [(pos.top_left.x,    pos.top_left.y),
                       (pos.top_right.x,   pos.top_right.y),
                       (pos.bottom_right.x,pos.bottom_right.y),
                       (pos.bottom_left.x, pos.bottom_left.y)]
                for i in range(4):
                    cv2.line(frame, pts[i], pts[(i+1)%4], (0, 212, 170), 2)
                cv2.putText(frame, code, (pts[0][0], pts[0][1] - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 212, 170), 2)
                if code != self._last_scanned:
                    self._last_scanned = code
                    self.window.after(0, self._on_scan, code)
                break

            self._current_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        if self.cap:
            self.cap.release()
            self.cap = None

    def _update_canvas(self):
        if not self.scanner_active:
            return
        if self._current_frame is not None:
            try:
                cw = self.cam_canvas.winfo_width() or 360
                ch = self.cam_canvas.winfo_height() or 250
                img = Image.fromarray(self._current_frame).resize((cw, ch))
                self._tk_img = ImageTk.PhotoImage(img)
                self.cam_canvas.delete("all")
                self.cam_canvas.create_image(0, 0, anchor=tk.NW,
                                             image=self._tk_img)
            except Exception:
                pass
        self.window.after(30, self._update_canvas)

    def _on_scan(self, code):
        """Barcode detected — fill the barcode field"""
        self.entry_barcode.delete(0, tk.END)
        self.entry_barcode.insert(0, code)
        self.scan_result.config(text=f"✅ Scanned: {code}")
        # Check if product already exists
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT name, price, quantity FROM items WHERE barcode=?", (code,))
        row = c.fetchone()
        conn.close()
        if row:
            self.entry_name.delete(0, tk.END)
            self.entry_name.insert(0, row[0])
            self.entry_price.delete(0, tk.END)
            self.entry_price.insert(0, str(row[1]))
            self.status_lbl.config(
                text=f"'{row[0]}' already exists with {row[2]} units.\nEnter quantity to add more stock.",
                fg="#ffb347")
        else:
            self.status_lbl.config(
                text="New product! Fill in name, price and quantity.",
                fg="#4a9eff")
        self.entry_name.focus()

    # ─────────────────────────────────────── Form actions ─────────────────
    def clear_fields(self):
        for e in (self.entry_barcode, self.entry_name,
                  self.entry_price, self.entry_qty):
            e.delete(0, tk.END)
        self.scan_result.config(text="")
        self.status_lbl.config(text="")
        self._last_scanned = ""

    def add_or_restock(self):
        bc    = self.entry_barcode.get().strip()
        name  = self.entry_name.get().strip()
        price = self.entry_price.get().strip()
        qty   = self.entry_qty.get().strip()

        if not all([bc, name, price, qty]):
            messagebox.showerror("Missing Fields",
                                 "All fields are required.",
                                 parent=self.window)
            return
        try:
            price_f = float(price)
            qty_i   = int(qty)
        except ValueError:
            messagebox.showerror("Invalid Input",
                                 "Price must be a number.\nQuantity must be a whole number.",
                                 parent=self.window)
            return
        if price_f < 0 or qty_i < 0:
            messagebox.showerror("Invalid Input",
                                 "Price and Quantity must be 0 or more.",
                                 parent=self.window)
            return

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute("INSERT INTO items (barcode,name,price,quantity) VALUES (?,?,?,?)",
                      (bc, name, price_f, qty_i))
            conn.commit()
            self.status_lbl.config(
                text=f"✅ '{name}' added with {qty_i} units.",
                fg="#00d4aa")
            messagebox.showinfo("Added",
                                f"'{name}' added successfully\nwith {qty_i} units.",
                                parent=self.window)
        except sqlite3.IntegrityError:
            c.execute("SELECT quantity FROM items WHERE barcode=?", (bc,))
            old_qty = c.fetchone()[0]
            new_qty = old_qty + qty_i
            c.execute("UPDATE items SET name=?, price=?, quantity=? WHERE barcode=?",
                      (name, price_f, new_qty, bc))
            conn.commit()
            self.status_lbl.config(
                text=f"✅ '{name}' restocked: {old_qty} → {new_qty} units.",
                fg="#00d4aa")
            messagebox.showinfo("Restocked",
                                f"'{name}'\nStock updated: {old_qty} → {new_qty} units.",
                                parent=self.window)
        finally:
            conn.close()
            self.clear_fields()