import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import threading
from datetime import datetime

try:
    import cv2
    import zxingcpp
    CV2_AVAILABLE = True
except Exception:
    CV2_AVAILABLE = False

def decode(frame):
    """Decode barcodes using zxingcpp instead of pyzbar"""
    try:
        results = zxingcpp.read_barcodes(frame)
        class FakeBC:
            def __init__(self, r):
                self.data = r.text.encode('utf-8')
                pos = r.position
                xs = [pos.top_left.x, pos.top_right.x, pos.bottom_left.x, pos.bottom_right.x]
                ys = [pos.top_left.y, pos.top_right.y, pos.bottom_left.y, pos.bottom_right.y]
                x, y = min(xs), min(ys)
                self.rect = type('R', (), {'x':x,'y':y,'width':max(xs)-x,'height':max(ys)-y})()
        return [FakeBC(r) for r in results]
    except Exception:
        return []

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

DB_PATH = "db/billing.db"


class RestockManager:
    def __init__(self, window):
        self.window = window
        self.window.title("Stock Replenishment")
        self.window.geometry("860x580")
        self.window.configure(bg="#0f1923")
        self.scanner_active = False
        self.cap = None
        self.last_scanned = ""
        self._current_frame = None
        self.create_widgets()

    def create_widgets(self):
        # TOP BAR
        topbar = tk.Frame(self.window, bg="#0d1820", height=52)
        topbar.pack(fill=tk.X)
        topbar.pack_propagate(False)
        tk.Label(topbar, text="🔁  Stock Replenishment",
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

        tk.Label(left, text="Scan Product Barcode",
                 font=("Arial", 11, "bold"),
                 bg="#111d27", fg="#6a8fa0").pack(anchor=tk.W, pady=(0, 8))

        # Camera canvas - live feed shows here
        self.cam_canvas = tk.Canvas(left, width=360, height=260,
                                    bg="#060e14",
                                    highlightthickness=1,
                                    highlightbackground="#1e2d3d")
        self.cam_canvas.pack(fill=tk.BOTH, expand=True)
        self._draw_camera_placeholder()

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

        # Manual entry fallback
        tk.Label(left, text="Or enter barcode manually:",
                 font=("Arial", 8), bg="#111d27", fg="#3a6070").pack(anchor=tk.W, pady=(12, 2))
        manual_row = tk.Frame(left, bg="#111d27")
        manual_row.pack(fill=tk.X)
        self.barcode_entry = tk.Entry(manual_row, font=("Arial", 11),
                                      bg="#162530", fg="#ffffff",
                                      insertbackground="white",
                                      relief=tk.FLAT, bd=6)
        self.barcode_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.barcode_entry.bind("<Return>", lambda e: self._lookup(self.barcode_entry.get().strip()))
        tk.Button(manual_row, text="Lookup",
                  font=("Arial", 9, "bold"),
                  bg="#4a9eff", fg="#050505",
                  bd=0, padx=10, pady=6,
                  cursor="hand2",
                  command=lambda: self._lookup(self.barcode_entry.get().strip())).pack(side=tk.LEFT, padx=(6, 0))

        # ── RIGHT: Product info + restock ──────────────────────────────────
        right = tk.Frame(main, bg="#111d27", padx=16, pady=12)
        right.grid(row=0, column=1, sticky="nsew")

        tk.Label(right, text="Product Information",
                 font=("Arial", 11, "bold"),
                 bg="#111d27", fg="#6a8fa0").pack(anchor=tk.W, pady=(0, 10))

        # Info card
        card = tk.Frame(right, bg="#16253a", padx=18, pady=18)
        card.pack(fill=tk.X)

        fields = [
            ("Barcode",        "#4a9eff",  "bc_lbl"),
            ("Product Name",   "#ffffff",  "name_lbl"),
            ("Selling Price",  "#00d4aa",  "price_lbl"),
            ("Current Stock",  "#ffb347",  "stock_lbl"),
        ]
        for label, color, attr in fields:
            row = tk.Frame(card, bg="#16253a")
            row.pack(fill=tk.X, pady=4)
            tk.Label(row, text=label, font=("Arial", 9),
                     bg="#16253a", fg="#3a6070",
                     width=14, anchor=tk.W).pack(side=tk.LEFT)
            lbl = tk.Label(row, text="—",
                           font=("Arial", 12, "bold"),
                           bg="#16253a", fg=color)
            lbl.pack(side=tk.LEFT)
            setattr(self, attr, lbl)

        # Stock status badge
        self.badge = tk.Label(card, text="",
                              font=("Arial", 9, "bold"),
                              bg="#16253a", padx=10, pady=3)
        self.badge.pack(anchor=tk.W, pady=(6, 0))

        # Not found message
        self.not_found = tk.Label(right, text="",
                                  font=("Arial", 10),
                                  bg="#111d27", fg="#ff6b6b")
        self.not_found.pack(anchor=tk.W, pady=(6, 0))

        # Divider
        tk.Frame(right, bg="#1e2d3d", height=1).pack(fill=tk.X, pady=16)

        # Qty + Restock
        tk.Label(right, text="Quantity to Add",
                 font=("Arial", 11, "bold"),
                 bg="#111d27", fg="#6a8fa0").pack(anchor=tk.W)

        qty_row = tk.Frame(right, bg="#111d27")
        qty_row.pack(fill=tk.X, pady=(8, 0))
        self.qty_entry = tk.Entry(qty_row, font=("Arial", 14),
                                  bg="#162530", fg="#ffffff",
                                  insertbackground="white",
                                  relief=tk.FLAT, bd=8, width=10)
        self.qty_entry.pack(side=tk.LEFT)
        self.qty_entry.bind("<Return>", lambda e: self.process_restock())

        tk.Button(qty_row, text="✅  Confirm Restock",
                  font=("Arial", 11, "bold"),
                  bg="#00d4aa", fg="#050505",
                  bd=0, padx=18, pady=8,
                  cursor="hand2",
                  command=self.process_restock).pack(side=tk.LEFT, padx=(12, 0))

        # Recent restock log
        tk.Label(right, text="Recent Restocks",
                 font=("Arial", 10, "bold"),
                 bg="#111d27", fg="#6a8fa0").pack(anchor=tk.W, pady=(18, 6))

        log_frame = tk.Frame(right, bg="#111d27")
        log_frame.pack(fill=tk.BOTH, expand=True)

        cols = ("Product", "Qty Added", "New Stock", "Time")
        self.log_tree = ttk.Treeview(log_frame, columns=cols,
                                      show="headings", height=5)
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview",
                        background="#0f1923", foreground="#c8d8e4",
                        fieldbackground="#0f1923", rowheight=26,
                        font=("Arial", 9))
        style.configure("Treeview.Heading",
                        background="#16253a", foreground="#4a9eff",
                        font=("Arial", 9, "bold"))

        for col in cols:
            self.log_tree.heading(col, text=col)
            self.log_tree.column(col, width=90, anchor=tk.CENTER)
        self.log_tree.pack(fill=tk.BOTH, expand=True)

    # ──────────────────────────────────── Camera ──────────────────────────
    def _draw_camera_placeholder(self):
        self.cam_canvas.delete("all")
        self.cam_canvas.create_text(
            180, 130,
            text="📷\n\nPress  ▶ Start Camera\nto scan barcodes live",
            fill="#2a4a5e", font=("Arial", 11),
            justify=tk.CENTER)

    def start_scanner(self):
        if not CV2_AVAILABLE:
            messagebox.showwarning(
                "Camera Unavailable",
                "OpenCV is not installed.\nUse manual barcode entry below.",
                parent=self.window)
            return
        if not PIL_AVAILABLE:
            messagebox.showwarning(
                "PIL Missing",
                "Install Pillow for live preview:\npip install Pillow",
                parent=self.window)
            return
        self.scanner_active = True
        self.last_scanned = ""
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
        self._draw_camera_placeholder()

    def _scan_loop(self):
        self.cap = cv2.VideoCapture(0)
        while self.scanner_active:
            ret, frame = self.cap.read()
            if not ret:
                break
            decoded = decode(frame)
            for bc in decoded:
                code = bc.data.decode("utf-8")
                x, y, w, h = bc.rect
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 212, 170), 2)
                cv2.putText(frame, code, (x, y-8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 212, 170), 2)
                if code != self.last_scanned:
                    self.last_scanned = code
                    self.window.after(0, self._on_scan, code)
                break
            self._current_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        if self.cap:
            self.cap.release()
            self.cap = None

    def _update_canvas(self):
        if not self.scanner_active:
            return
        if self._current_frame is not None and PIL_AVAILABLE:
            try:
                cw = self.cam_canvas.winfo_width() or 360
                ch = self.cam_canvas.winfo_height() or 260
                img = Image.fromarray(self._current_frame).resize((cw, ch))
                self._tk_img = ImageTk.PhotoImage(img)
                self.cam_canvas.delete("all")
                self.cam_canvas.create_image(0, 0, anchor=tk.NW, image=self._tk_img)
            except Exception:
                pass
        self.window.after(30, self._update_canvas)

    def _on_scan(self, code):
        self.barcode_entry.delete(0, tk.END)
        self.barcode_entry.insert(0, code)
        self._lookup(code)
        self.qty_entry.focus()

    # ──────────────────────────────────── Lookup ──────────────────────────
    def _lookup(self, barcode):
        if not barcode:
            return
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT name, price, quantity FROM items WHERE barcode=?", (barcode,))
        row = c.fetchone()
        conn.close()

        self.not_found.config(text="")
        if row:
            name, price, qty = row
            self.bc_lbl.config(text=barcode)
            self.name_lbl.config(text=name)
            self.price_lbl.config(text=f"Rs. {price:.2f}")
            self.stock_lbl.config(text=f"{qty} units")
            if qty <= 0:
                self.badge.config(text="  OUT OF STOCK  ",
                                  bg="#3a0f0f", fg="#ff6b6b")
            elif qty < 10:
                self.badge.config(text=f"  LOW STOCK — only {qty} left  ",
                                  bg="#2a1a07", fg="#ffb347")
            else:
                self.badge.config(text="  IN STOCK  ",
                                  bg="#09231e", fg="#00d4aa")
        else:
            self.bc_lbl.config(text=barcode)
            self.name_lbl.config(text="—")
            self.price_lbl.config(text="—")
            self.stock_lbl.config(text="—")
            self.badge.config(text="")
            self.not_found.config(
                text=f"⚠  No product found for barcode: {barcode}")

    # ──────────────────────────────────── Restock ─────────────────────────
    def process_restock(self):
        barcode = self.barcode_entry.get().strip()
        if not barcode:
            messagebox.showerror("Error", "Scan or enter a barcode first.",
                                 parent=self.window)
            return
        try:
            qty = int(self.qty_entry.get().strip())
            if qty <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Enter a valid quantity (number > 0).",
                                 parent=self.window)
            return

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, name, price, quantity FROM items WHERE barcode=?",
                  (barcode,))
        row = c.fetchone()

        if row:
            item_id, name, price, old_qty = row
            new_qty = old_qty + qty
            c.execute("UPDATE items SET quantity=? WHERE barcode=?",
                      (new_qty, barcode))
        else:
            c.execute("INSERT INTO items (barcode,name,price,quantity) VALUES (?,?,?,?)",
                      (barcode, barcode, 0.0, qty))
            item_id = c.lastrowid
            name, price, new_qty = barcode, 0.0, qty

        try:
            c.execute("""INSERT INTO ledger
                         (date,type,item_id,item_name,quantity,price)
                         VALUES (?,?,?,?,?,?)""",
                      (datetime.now().strftime('%Y-%m-%d'),
                       'Purchase', item_id, name, qty, price))
        except sqlite3.Error:
            pass

        conn.commit()
        conn.close()

        # Update display
        self.stock_lbl.config(text=f"{new_qty} units")
        self.badge.config(text="  IN STOCK  ", bg="#09231e", fg="#00d4aa")

        # Add to log
        self.log_tree.insert("", 0, values=(
            name[:22],
            f"+{qty}",
            new_qty,
            datetime.now().strftime("%H:%M:%S")
        ))

        messagebox.showinfo("Restocked",
                            f"'{name}'\n+{qty} units added\nNew stock: {new_qty}",
                            parent=self.window)
        self.qty_entry.delete(0, tk.END)
        self.barcode_entry.delete(0, tk.END)
        self.last_scanned = ""
        self.bc_lbl.config(text="—")
        self.name_lbl.config(text="—")
        self.price_lbl.config(text="—")
        self.stock_lbl.config(text="—")
        self.badge.config(text="")