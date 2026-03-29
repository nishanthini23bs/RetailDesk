import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import datetime
import sqlite3
import os
import subprocess
import threading

try:
    import cv2
    import zxingcpp
    CV2_AVAILABLE = True
except Exception:
    CV2_AVAILABLE = False

def pyzbar_decode(frame):
    """Decode barcodes using zxingcpp with preprocessing for better detection"""
    try:
        # Try original first
        results = zxingcpp.read_barcodes(frame)
        if not results:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            results = zxingcpp.read_barcodes(gray)
        if not results:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.equalizeHist(gray)
            results = zxingcpp.read_barcodes(gray)

        class FakeBC:
            def __init__(self, r):
                self.data = r.text.encode('utf-8')
                pos = r.position
                xs = [pos.top_left.x, pos.top_right.x,
                      pos.bottom_left.x, pos.bottom_right.x]
                ys = [pos.top_left.y, pos.top_right.y,
                      pos.bottom_left.y, pos.bottom_right.y]
                x, y = min(xs), min(ys)
                self.rect = type('R', (), {
                    'x': x, 'y': y,
                    'width': max(xs)-x,
                    'height': max(ys)-y
                })()
        return [FakeBC(r) for r in results]
    except Exception:
        return []

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

DB_PATH = "db/billing.db"


class PosApp:
    def __init__(self, root):
        self.root = root
        self.window = root          # alias used in generate_pdf / print_pdf
        self.cart = []
        self.scanner_active = False

        self.init_db()
        self.setup_gui()

    # ------------------------------------------------------------------ DB --
    def init_db(self):
        os.makedirs("db", exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY, value TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                total REAL NOT NULL,
                invoice_number TEXT NOT NULL,
                table_number INTEGER
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sale_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_id INTEGER NOT NULL,
                item_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                FOREIGN KEY (sale_id) REFERENCES sales(id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                quantity INTEGER DEFAULT 0,
                barcode TEXT
            )
        """)

        cursor.execute("SELECT value FROM settings WHERE key='last_invoice_number'")
        if not cursor.fetchone():
            cursor.execute("INSERT INTO settings (key,value) VALUES ('last_invoice_number','10000')")

        # Add invoice_number column to sales if missing (migration)
        cursor.execute("PRAGMA table_info(sales)")
        cols = [r[1] for r in cursor.fetchall()]
        if 'invoice_number' not in cols:
            cursor.execute("ALTER TABLE sales ADD COLUMN invoice_number TEXT")

        conn.commit()
        conn.close()

    # ----------------------------------------------------------------- GUI --
    def setup_gui(self):
        self.root.title("Smart Billing POS")
        self.root.geometry("1100x720")
        self.root.configure(bg="#f0f0f0")

        # ── HEADER ──────────────────────────────────────────────────────────
        header = tk.Frame(self.root, bg="white", height=90)
        header.pack(fill=tk.X, padx=10, pady=5)

        # Logo placeholder / real image
        if PIL_AVAILABLE:
            try:
                logo_img = Image.open("logo.png").resize((70, 70))
                self.logo_photo = ImageTk.PhotoImage(logo_img)
                tk.Label(header, image=self.logo_photo, bg="white").pack(side=tk.LEFT, padx=15)
            except Exception:
                tk.Label(header, text="🏪", font=("Arial", 36), bg="white").pack(side=tk.LEFT, padx=15)
        else:
            tk.Label(header, text="🏪", font=("Arial", 36), bg="white").pack(side=tk.LEFT, padx=15)

        info = tk.Frame(header, bg="white")
        info.pack(side=tk.LEFT)
        tk.Label(info, text="My Store", font=("Arial", 20, "bold"), bg="white").pack(anchor=tk.W)
        tk.Label(info, text="123 Main Street, City - 000000", bg="white", font=("Arial", 10)).pack(anchor=tk.W)
        tk.Label(info, text="Phone: +91-XXXXXXXXXX", bg="white", font=("Arial", 10)).pack(anchor=tk.W)

        # Table # and Invoice # on the right
        right_header = tk.Frame(header, bg="white")
        right_header.pack(side=tk.RIGHT, padx=20)

        tbl = tk.Frame(right_header, bg="white")
        tbl.pack(anchor=tk.E)
        tk.Label(tbl, text="Table #:", bg="white", font=("Arial", 12)).pack(side=tk.LEFT)
        self.table_entry = tk.Entry(tbl, width=5, font=("Arial", 12))
        self.table_entry.pack(side=tk.LEFT, padx=4)

        self.invoice_header_var = tk.StringVar(value=f"Invoice #: {self.get_next_invoice_number()}")
        tk.Label(right_header, textvariable=self.invoice_header_var,
                 bg="white", font=("Arial", 12, "bold")).pack(anchor=tk.E, pady=4)

        # ── MAIN AREA ────────────────────────────────────────────────────────
        main = tk.Frame(self.root, bg="#f0f0f0")
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Left panel
        left = tk.Frame(main, bg="white", bd=1, relief=tk.GROOVE)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        # Search row
        sf = tk.Frame(left, bg="white", padx=10, pady=8)
        sf.pack(fill=tk.X)
        tk.Label(sf, text="Search Item:", bg="white", font=("Arial", 13)).pack(side=tk.LEFT)
        self.search_entry = tk.Entry(sf, font=("Arial", 13), width=26, bd=2, relief=tk.GROOVE)
        self.search_entry.pack(side=tk.LEFT, padx=6)
        self.search_entry.bind("<KeyRelease>", self.search_items)

        if CV2_AVAILABLE:
            tk.Button(sf, text="📷 Scan", font=("Arial", 11),
                      command=self.toggle_live_scanner, bg="#4DB6AC", fg="white", bd=0).pack(side=tk.LEFT, padx=4)

        # Search results listbox
        self.search_results = tk.Listbox(left, height=4, font=("Arial", 12))
        self.search_results.pack(fill=tk.X, padx=10, pady=2)
        self.search_results.items = []
        self.search_results.bind("<<ListboxSelect>>", self.select_item)

        # Barcode manual entry
        bf = tk.Frame(left, bg="white", padx=10, pady=6)
        bf.pack(fill=tk.X)
        tk.Label(bf, text="Barcode:", bg="white", font=("Arial", 13)).pack(side=tk.LEFT)
        self.barcode_entry = tk.Entry(bf, font=("Arial", 13), width=30, bd=2, relief=tk.GROOVE)
        self.barcode_entry.pack(side=tk.LEFT, padx=8)
        self.barcode_entry.bind("<Return>", self.process_barcode_entry)
        tk.Label(bf, text="↵ Enter to add", bg="white", font=("Arial", 9), fg="gray").pack(side=tk.LEFT)

        # ── PRODUCT PREVIEW CARD ─────────────────────────────────────────
        self.preview_frame = tk.Frame(left, bg="#e8f4f0",
                                      padx=12, pady=10,
                                      relief=tk.FLAT)
        self.preview_frame.pack(fill=tk.X, padx=10, pady=(0, 4))

        preview_top = tk.Frame(self.preview_frame, bg="#e8f4f0")
        preview_top.pack(fill=tk.X)

        tk.Label(preview_top, text="Scanned Product:",
                 font=("Arial", 9), bg="#e8f4f0",
                 fg="#666666").pack(side=tk.LEFT)

        self.preview_not_found = tk.Label(preview_top, text="",
                                          font=("Arial", 9),
                                          bg="#e8f4f0", fg="#cc0000")
        self.preview_not_found.pack(side=tk.RIGHT)

        details_row = tk.Frame(self.preview_frame, bg="#e8f4f0")
        details_row.pack(fill=tk.X, pady=(4, 0))

        self.preview_name = tk.Label(details_row, text="—  scan or type a barcode",
                                     font=("Arial", 12, "bold"),
                                     bg="#e8f4f0", fg="#2c3e50")
        self.preview_name.pack(side=tk.LEFT)

        right_info = tk.Frame(self.preview_frame, bg="#e8f4f0")
        right_info.pack(fill=tk.X)

        self.preview_price = tk.Label(right_info, text="",
                                      font=("Arial", 11),
                                      bg="#e8f4f0", fg="#27ae60")
        self.preview_price.pack(side=tk.LEFT, padx=(0, 16))

        self.preview_stock = tk.Label(right_info, text="",
                                      font=("Arial", 11),
                                      bg="#e8f4f0", fg="#e67e22")
        self.preview_stock.pack(side=tk.LEFT)

        self.preview_badge = tk.Label(right_info, text="",
                                      font=("Arial", 8, "bold"),
                                      bg="#e8f4f0", padx=8, pady=2)
        self.preview_badge.pack(side=tk.RIGHT)

        # Cart treeview
        tree_frame = tk.Frame(left, bg="white")
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)
        cols = ("S.No.", "ID", "Item Name", "Qty", "Price", "Subtotal")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=14)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        widths = [50, 50, 200, 60, 90, 90]
        for col, w in zip(cols, widths):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w, anchor=tk.CENTER)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # ── RIGHT PANEL ──────────────────────────────────────────────────────
        right = tk.Frame(main, bg="#0f1923", bd=0, width=280)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(6, 0))
        right.pack_propagate(False)

        # ── CAMERA SECTION ───────────────────────────────────────────────
        cam_header = tk.Frame(right, bg="#0d1820")
        cam_header.pack(fill=tk.X)
        tk.Label(cam_header, text="📷  Live Scanner",
                 font=("Arial", 10, "bold"),
                 bg="#0d1820", fg="#cdd8e0").pack(side=tk.LEFT, padx=10, pady=6)
        self.cam_status_lbl = tk.Label(cam_header, text="Off",
                                       font=("Arial", 9),
                                       bg="#0d1820", fg="#ff6b6b")
        self.cam_status_lbl.pack(side=tk.RIGHT, padx=10)

        # Live camera canvas
        self.cam_canvas = tk.Canvas(right, width=260, height=195,
                                    bg="#060e14",
                                    highlightthickness=1,
                                    highlightbackground="#1e2d3d")
        self.cam_canvas.pack(padx=10, pady=(4, 0))
        self._draw_cam_placeholder()

        # Camera toggle button
        self.cam_toggle_btn = tk.Button(right,
                                        text="▶  Start Live Scanner",
                                        font=("Arial", 10, "bold"),
                                        bg="#00d4aa", fg="#050505",
                                        bd=0, pady=6, cursor="hand2",
                                        command=self.toggle_live_scanner)
        self.cam_toggle_btn.pack(fill=tk.X, padx=10, pady=6)

        # If camera libs missing, show it clearly in UI without popup
        if not CV2_AVAILABLE or not PIL_AVAILABLE:
            self.cam_toggle_btn.config(
                text="📷  Camera not available",
                bg="#1a2a3a", fg="#3a6070",
                state=tk.DISABLED)
            self.cam_canvas.delete("all")
            self.cam_canvas.create_text(
                130, 97,
                text="Camera unavailable\n\nBill products by:\n• Search by name above\n• Type barcode + press Enter",
                fill="#3a6070", font=("Arial", 9),
                justify=tk.CENTER)

        ttk.Separator(right, orient="horizontal").pack(fill=tk.X, padx=10, pady=4)

        # ── BILLING ACTIONS ───────────────────────────────────────────────
        tk.Label(right, text="Billing Actions",
                 font=("Arial", 9, "bold"),
                 bg="#0f1923", fg="#3a6070").pack(anchor=tk.W, padx=12, pady=(4,2))

        btn_cfg = dict(font=("Arial", 11), bd=0, pady=7,
                       cursor="hand2", anchor=tk.W, padx=12)
        tk.Button(right, text="  🔄  Update Quantity",
                  bg="#2d4a2d", fg="#81C784",
                  command=self.update_quantity, **btn_cfg).pack(fill=tk.X, padx=10, pady=2)
        tk.Button(right, text="  ❌  Remove Item",
                  bg="#4a2020", fg="#EF9A9A",
                  command=self.clear_selected_items, **btn_cfg).pack(fill=tk.X, padx=10, pady=2)
        tk.Button(right, text="  🗑  Clear Cart",
                  bg="#3a3020", fg="#FFCC80",
                  command=self.clear_cart, **btn_cfg).pack(fill=tk.X, padx=10, pady=2)

        ttk.Separator(right, orient="horizontal").pack(fill=tk.X, padx=10, pady=8)

        # Totals
        totals = tk.Frame(right, bg="#0f1923")
        totals.pack(fill=tk.X, padx=14)
        tk.Label(totals, text="Items in cart",
                 bg="#0f1923", font=("Arial", 9), fg="#3a6070").pack(anchor=tk.W)
        self.qty_label = tk.Label(totals, text="0",
                                  bg="#0f1923", font=("Arial", 14, "bold"), fg="#4a9eff")
        self.qty_label.pack(anchor=tk.W)
        tk.Label(totals, text="Grand Total",
                 bg="#0f1923", font=("Arial", 9), fg="#3a6070").pack(anchor=tk.W, pady=(10,0))
        self.total_label = tk.Label(totals, text="Rs. 0.00",
                                    bg="#0f1923", font=("Arial", 20, "bold"), fg="#00d4aa")
        self.total_label.pack(anchor=tk.W)

        ttk.Separator(right, orient="horizontal").pack(fill=tk.X, padx=10, pady=10)

        tk.Button(right, text="  💾  Save Sale",
                  font=("Arial", 12, "bold"),
                  bg="#1a3a5c", fg="#90CAF9",
                  bd=0, pady=9, cursor="hand2", anchor=tk.W, padx=12,
                  command=self.save_sale).pack(fill=tk.X, padx=10, pady=2)
        tk.Button(right, text="  🖨  Save & Print PDF",
                  font=("Arial", 12, "bold"),
                  bg="#2d1f4a", fg="#ce93d8",
                  bd=0, pady=9, cursor="hand2", anchor=tk.W, padx=12,
                  command=self.save_and_print).pack(fill=tk.X, padx=10, pady=2)

    # ─────────────────────────── Live inline camera scanner ──────────────
    def _draw_cam_placeholder(self):
        self.cam_canvas.delete("all")
        self.cam_canvas.create_text(
            130, 97,
            text="📷\n\nPress  ▶ Start Live Scanner\nto scan products while billing",
            fill="#2a4a5e", font=("Arial", 9),
            justify=tk.CENTER)

    def toggle_live_scanner(self):
        if self.scanner_active:
            self._stop_live_scanner()
        else:
            self._start_live_scanner()

    def _start_live_scanner(self):
        self._live_last_scanned = ""
        if not CV2_AVAILABLE or not PIL_AVAILABLE:
            # Silently disable — show message in UI instead of popup
            self.cam_canvas.delete("all")
            self.cam_canvas.create_text(
                130, 80,
                text="Camera not available\n\nYou can still bill by:\n• Typing item name in Search\n• Typing barcode and press Enter",
                fill="#4a7090", font=("Arial", 9),
                justify=tk.CENTER)
            self.cam_toggle_btn.config(
                text="Camera not available",
                bg="#2a3a4a", fg="#4a7090",
                state=tk.DISABLED)
            return
        self.scanner_active = True
        self._live_last_scanned = ""
        self._live_frame = None
        self.cam_toggle_btn.config(text="■  Stop Scanner", bg="#3a0f0f", fg="#ff6b6b")
        self.cam_status_lbl.config(text="● Live", fg="#00d4aa")
        import threading
        threading.Thread(target=self._live_scan_loop, daemon=True).start()
        self._refresh_cam_canvas()

    def _stop_live_scanner(self):
        self.scanner_active = False
        self.cam_toggle_btn.config(text="▶  Start Live Scanner",
                                   bg="#00d4aa", fg="#050505")
        self.cam_status_lbl.config(text="Off", fg="#ff6b6b")
        if hasattr(self, '_live_cap') and self._live_cap:
            self._live_cap.release()
            self._live_cap = None
        self._draw_cam_placeholder()

    def _live_scan_loop(self):
        self._live_cap = cv2.VideoCapture(0)
        self._live_cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self._live_cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        while self.scanner_active:
            ret, frame = self._live_cap.read()
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
                # Draw green box
                pos = r.position
                pts = [(pos.top_left.x,    pos.top_left.y),
                       (pos.top_right.x,   pos.top_right.y),
                       (pos.bottom_right.x,pos.bottom_right.y),
                       (pos.bottom_left.x, pos.bottom_left.y)]
                for i in range(4):
                    cv2.line(frame, pts[i], pts[(i+1)%4], (0, 212, 170), 2)
                cv2.putText(frame, code, (pts[0][0], pts[0][1] - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 212, 170), 2)
                if code != getattr(self, "_live_last_scanned", ""):
                    self._live_last_scanned = code
                    self.root.after(0, self._on_live_scan, code)
                    break

            self._live_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        if hasattr(self, '_live_cap') and self._live_cap:
            self._live_cap.release()
            self._live_cap = None

    def _refresh_cam_canvas(self):
        if not self.scanner_active:
            return
        if getattr(self, "_live_frame", None) is not None and PIL_AVAILABLE:
            try:
                cw = self.cam_canvas.winfo_width() or 260
                ch = self.cam_canvas.winfo_height() or 195
                img = Image.fromarray(self._live_frame).resize((cw, ch))
                self._cam_tk_img = ImageTk.PhotoImage(img)
                self.cam_canvas.delete("all")
                self.cam_canvas.create_image(0, 0, anchor=tk.NW,
                                             image=self._cam_tk_img)
            except Exception:
                pass
        self.root.after(30, self._refresh_cam_canvas)

    def _on_live_scan(self, code):
        """Called when camera detects a barcode — looks up product and adds to cart"""
        # Always show detected barcode in field
        self.barcode_entry.delete(0, tk.END)
        self.barcode_entry.insert(0, code)

        item = self.lookup_item(code)
        if item:
            self.show_product_preview(item)
            self.add_to_cart(item)
            self.preview_frame.config(bg="#d5f5e3")
            self.root.after(800, lambda: self.preview_frame.config(bg="#e8f4f0"))
            # Allow same item to be scanned again after 2 seconds
            self.root.after(2000, lambda: setattr(self, '_live_last_scanned', ''))
        else:
            # Product not in DB — show the scanned code clearly
            self.preview_name.config(text=f"Scanned: {code}")
            self.preview_price.config(text="Not in inventory")
            self.preview_stock.config(text="")
            self.preview_badge.config(
                text=" ADD PRODUCT FIRST ",
                bg="#2a1a07", fg="#ffb347")
            self.preview_not_found.config(
                text="Go to Add Products, scan this barcode and fill details")
            # Reset so it can try again
            self.root.after(3000, lambda: setattr(self, '_live_last_scanned', ''))

    # --------------------------------------------------------- Barcode scan --
    def process_barcode_entry(self, event=None):
        barcode = self.barcode_entry.get().strip()
        if barcode:
            item = self.lookup_item(barcode)
            if item:
                self.show_product_preview(item)
                self.add_to_cart(item)
                self.barcode_entry.delete(0, tk.END)
            else:
                self.preview_name.config(text="— product not found")
                self.preview_price.config(text="")
                self.preview_stock.config(text="")
                self.preview_badge.config(text="")
                self.preview_not_found.config(
                    text=f"⚠ No product for barcode: {barcode}")

    def show_product_preview(self, item):
        """Show scanned product details in the preview card"""
        item_id, name, price = item[0], item[1], item[2]
        # Get current stock
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT quantity FROM items WHERE id=?", (item_id,))
        row = c.fetchone()
        stock = row[0] if row else 0
        conn.close()

        self.preview_name.config(text=name)
        self.preview_price.config(text=f"Price: Rs. {price:.2f}")
        self.preview_stock.config(text=f"Stock: {stock} units")
        self.preview_not_found.config(text="")

        if stock <= 0:
            self.preview_badge.config(
                text=" OUT OF STOCK ",
                bg="#fadbd8", fg="#c0392b")
        elif stock < 10:
            self.preview_badge.config(
                text=f" LOW STOCK ",
                bg="#fdebd0", fg="#e67e22")
        else:
            self.preview_badge.config(
                text=" IN STOCK ",
                bg="#d5f5e3", fg="#1e8449")

    def start_barcode_scan(self):
        if not CV2_AVAILABLE:
            messagebox.showwarning("Unavailable", "OpenCV not installed.", parent=self.root)
            return
        self.scanner_active = True
        threading.Thread(target=self.scan_barcode, daemon=True).start()

    def scan_barcode(self):
        cap = cv2.VideoCapture(0)
        while self.scanner_active:
            ret, frame = cap.read()
            if not ret:
                break
            decoded = pyzbar_decode(frame)
            if decoded:
                barcode = decoded[0].data.decode('utf-8')
                item = self.lookup_item(barcode)
                if item:
                    self.root.after(0, self.add_scanned_item, item)
                self.scanner_active = False
                break
            cv2.imshow('Barcode Scanner — press Q to cancel', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                self.scanner_active = False
                break
        cap.release()
        cv2.destroyAllWindows()

    def add_scanned_item(self, item):
        self.show_product_preview(item)
        self.add_to_cart(item)

    # --------------------------------------------------------- Search / Cart --
    def search_items(self, event=None):
        term = self.search_entry.get().strip()
        self.search_results.delete(0, tk.END)
        self.search_results.items = []
        if not term:
            return
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, price FROM items
            WHERE name LIKE ? OR CAST(id AS TEXT) LIKE ? OR barcode = ?
        """, (f'%{term}%', f'%{term}%', term))
        for item in cursor.fetchall():
            self.search_results.insert(tk.END, f"{item[1]}  —  ₹{item[2]:.2f}")
            self.search_results.items.append(item)
        conn.close()

    def select_item(self, event):
        w = event.widget
        if not w.curselection():
            return
        idx = w.curselection()[0]
        if idx < len(w.items):
            self.add_to_cart(w.items[idx])

    def lookup_item(self, term):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        # First try exact barcode match
        cursor.execute("SELECT id, name, price FROM items WHERE barcode = ?", (term,))
        item = cursor.fetchone()
        if not item:
            # Try name search
            cursor.execute("SELECT id, name, price FROM items WHERE name LIKE ?",
                          (f'%{term}%',))
            item = cursor.fetchone()
        if not item:
            # Try ID
            cursor.execute("SELECT id, name, price FROM items WHERE CAST(id AS TEXT) = ?",
                          (term,))
            item = cursor.fetchone()
        conn.close()
        return item

    def add_to_cart(self, item):
        for ci in self.cart:
            if ci['id'] == item[0]:
                ci['qty'] += 1
                ci['subtotal'] = round(ci['qty'] * ci['price'], 2)
                break
        else:
            self.cart.append({
                'id': item[0], 'name': item[1],
                'price': item[2], 'qty': 1, 'subtotal': item[2]
            })
        self.update_cart_display()

    def update_quantity(self):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0])['values']
        try:
            item_id = int(vals[1])
        except (ValueError, IndexError):
            return
        new_qty = simpledialog.askinteger(
            "Update Quantity", f"Quantity for {vals[2]}:",
            minvalue=1, initialvalue=vals[3], parent=self.root)
        if new_qty:
            for ci in self.cart:
                if ci['id'] == item_id:
                    ci['qty'] = new_qty
                    ci['subtotal'] = round(new_qty * ci['price'], 2)
                    break
            self.update_cart_display()

    def clear_selected_items(self):
        for sel in self.tree.selection():
            vals = self.tree.item(sel)['values']
            try:
                item_id = int(vals[1])
                self.cart = [ci for ci in self.cart if ci['id'] != item_id]
            except (ValueError, IndexError):
                pass
        self.update_cart_display()

    def clear_cart(self):
        self.cart.clear()
        self.update_cart_display()

    def update_cart_display(self):
        self.tree.delete(*self.tree.get_children())
        for i, ci in enumerate(self.cart, 1):
            self.tree.insert("", "end", values=(
                i, ci['id'], ci['name'], ci['qty'],
                f"₹{ci['price']:.2f}", f"₹{ci['subtotal']:.2f}"
            ))
        total = sum(ci['subtotal'] for ci in self.cart)
        qty   = sum(ci['qty']     for ci in self.cart)
        self.total_label.config(text=f"₹{total:.2f}")
        self.qty_label.config(text=str(qty))

    # ------------------------------------------------------------ Save sale --
    def save_sale(self):
        if not self.cart:
            messagebox.showwarning("Empty Cart", "Add items before saving.", parent=self.root)
            return None

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        low_stock = []
        try:
            cursor.execute("SELECT value FROM settings WHERE key='last_invoice_number'")
            last = int(cursor.fetchone()[0])
            invoice_number = f"HYP-{last + 1}"

            total    = sum(ci['subtotal'] for ci in self.cart)
            date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            table_no = self.table_entry.get() or None

            cursor.execute(
                "INSERT INTO sales (date,total,invoice_number,table_number) VALUES (?,?,?,?)",
                (date_str, total, invoice_number, table_no)
            )
            sale_id = cursor.lastrowid

            for ci in self.cart:
                cursor.execute(
                    "INSERT INTO sale_items (sale_id,item_id,quantity,price) VALUES (?,?,?,?)",
                    (sale_id, ci['id'], ci['qty'], ci['price'])
                )
                cursor.execute(
                    "UPDATE items SET quantity = quantity - ? WHERE id = ?",
                    (ci['qty'], ci['id'])
                )
                cursor.execute("SELECT quantity, name FROM items WHERE id=?", (ci['id'],))
                row = cursor.fetchone()
                if row and row[0] < 10:
                    low_stock.append(f"{row[1]} ({row[0]} left)")

            cursor.execute(
                "UPDATE settings SET value=? WHERE key='last_invoice_number'",
                (str(last + 1),)
            )
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            messagebox.showerror("DB Error", str(e), parent=self.root)
            return None
        finally:
            conn.close()

        if low_stock:
            messagebox.showwarning("Low Stock",
                "These items need restocking:\n• " + "\n• ".join(low_stock), parent=self.root)

        messagebox.showinfo("Saved", f"Sale saved!\nInvoice: {invoice_number}", parent=self.root)
        self.clear_cart()
        self.invoice_header_var.set(f"Invoice #: {self.get_next_invoice_number()}")
        return invoice_number

    # ---------------------------------------------------------- PDF / Print --
    def generate_pdf(self, invoice_number):
        try:
            user_home  = os.path.expanduser("~")
            downloads  = os.path.join(user_home, "Downloads")
            if not os.path.isdir(downloads):
                downloads = user_home
            invoice_dir = os.path.join(downloads, "invoices")
            os.makedirs(invoice_dir, exist_ok=True)

            ts       = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(invoice_dir, f"{invoice_number}_{ts}.pdf")

            conn = sqlite3.connect(DB_PATH)
            cur  = conn.cursor()
            cur.execute("SELECT id, date, total FROM sales WHERE invoice_number=?", (invoice_number,))
            row = cur.fetchone()
            if not row:
                messagebox.showerror("Error", "Invoice not found.", parent=self.root)
                conn.close()
                return None
            sale_id, date_str, total = row

            cur.execute("""
                SELECT items.name, sale_items.quantity, sale_items.price
                FROM sale_items
                JOIN items ON sale_items.item_id = items.id
                WHERE sale_items.sale_id = ?
            """, (sale_id,))
            items = cur.fetchall()
            conn.close()

            c = canvas.Canvas(filename, pagesize=letter)
            w, h = letter

            c.setFont("Helvetica-Bold", 16)
            c.drawString(72, h - 72,  "My Store")
            c.setFont("Helvetica", 12)
            c.drawString(72, h - 90,  "123 Main Street, City - 000000")
            c.drawString(72, h - 108, "Phone: +91-XXXXXXXXXX")

            c.drawString(72, h - 140, f"Invoice #: {invoice_number}")
            c.drawString(72, h - 156, f"Date:      {date_str}")
            c.drawString(72, h - 172, "Cashier:   Admin")

            y = h - 210
            c.setFont("Helvetica-Bold", 12)
            c.drawString(72,  y, "Item")
            c.drawString(300, y, "Qty")
            c.drawString(380, y, "Price")
            c.drawString(470, y, "Subtotal")
            c.line(72, y - 6, 540, y - 6)

            y -= 24
            c.setFont("Helvetica", 12)
            for name, qty, price in items:
                subtotal = qty * price
                c.drawString(72,  y, str(name))
                c.drawString(300, y, str(qty))
                c.drawString(380, y, f"Rs.{price:.2f}")
                c.drawString(470, y, f"Rs.{subtotal:.2f}")
                y -= 20

            c.line(72, y - 4, 540, y - 4)
            c.setFont("Helvetica-Bold", 14)
            c.drawString(380, y - 24, f"Total: Rs.{total:.2f}")
            c.save()

            if os.path.isfile(filename):
                messagebox.showinfo("Invoice Saved",
                    f"PDF saved to:\n{filename}", parent=self.root)
                return filename
            return None

        except Exception as e:
            messagebox.showerror("PDF Error", str(e), parent=self.root)
            return None

    def print_pdf(self, filename):
        if not filename or not os.path.exists(filename):
            messagebox.showerror("Print Error", "PDF file not found.", parent=self.root)
            return
        try:
            if os.name == 'nt':
                os.startfile(filename)
            elif os.name == 'posix':
                subprocess.run(["xdg-open", filename], check=False)
        except Exception as e:
            messagebox.showerror("Print Error", str(e), parent=self.root)

    def get_next_invoice_number(self):
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key='last_invoice_number'")
            result = cursor.fetchone()
            conn.close()
            return f"HYP-{int(result[0]) + 1}" if result else "HYP-10001"
        except Exception:
            return "HYP-10001"

    def save_and_print(self):
        invoice_number = self.save_sale()
        if invoice_number:
            pdf = self.generate_pdf(invoice_number)
            if pdf:
                self.print_pdf(pdf)


# Ensure db folder exists when module is imported standalone
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

if __name__ == "__main__":
    root = tk.Tk()
    app = PosApp(root)
    root.mainloop()