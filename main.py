import tkinter as tk
from tkinter import ttk
from ledger import LedgerView
from restock import RestockManager
from add_items import AddItems
from pos_gui import PosApp
from inventory_editor import InventoryEditor
from db_setup import init_db
import sqlite3
import datetime

DB_PATH = "db/billing.db"


class MainApp:
    def __init__(self, root):
        self.root = root
        self.root.title("RetailDesk - Business Management System")
        self.root.configure(bg="#0f1923")
        self.root.resizable(True, True)
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{sw}x{sh}+0+0")
        self.root.after(200, lambda: self.root.state("zoomed"))
        init_db()
        self.build_ui()

    def build_ui(self):
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        # LEFT SIDEBAR
        sidebar = tk.Frame(self.root, bg="#0f1923", width=270)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)

        brand = tk.Frame(sidebar, bg="#0f1923", pady=28)
        brand.pack(fill=tk.X, padx=24)
        tk.Label(brand, text="RetailDesk", font=("Georgia", 22, "bold"),
                 bg="#0f1923", fg="#ffffff").pack(anchor=tk.W)
        tk.Label(brand, text="Business Management System",
                 font=("Arial", 8), bg="#0f1923", fg="#3a5a6e").pack(anchor=tk.W)

        tk.Frame(sidebar, bg="#1e2d3d", height=1).pack(fill=tk.X, padx=20, pady=8)

        tk.Label(sidebar, text="NAVIGATION", font=("Arial", 8, "bold"),
                 bg="#0f1923", fg="#2e4a5e").pack(anchor=tk.W, padx=28, pady=(12, 6))

        nav_items = [
            ("NEW BILL",            "Start a new customer transaction",     self.open_pos),
            ("PRODUCT CATALOGUE",   "Browse and manage your products",      self.open_inventory_editor),
            ("ADD PRODUCTS",        "Add new products to your store",       self.open_add_items),
            ("STOCK REPLENISHMENT", "Top up stock for low items",           self.open_restock),
            ("SALES & REPORTS",     "View revenue history and export data", self.open_ledger),
        ]
        for label, desc, cmd in nav_items:
            self._nav_btn(sidebar, label, desc, cmd)

        tk.Frame(sidebar, bg="#1e2d3d", height=1).pack(fill=tk.X, padx=20, pady=20)
        tk.Label(sidebar, text="v1.0  -  Offline Mode", font=("Arial", 8),
                 bg="#0f1923", fg="#2e4a5e").pack(anchor=tk.W, padx=28)

        # RIGHT CONTENT
        content = tk.Frame(self.root, bg="#111d27")
        content.grid(row=0, column=1, sticky="nsew")
        content.columnconfigure(0, weight=1)

        # Topbar
        topbar = tk.Frame(content, bg="#0d1820", height=64)
        topbar.pack(fill=tk.X)
        topbar.pack_propagate(False)
        tk.Label(topbar, text="Dashboard Overview", font=("Arial", 14, "bold"),
                 bg="#0d1820", fg="#cdd8e0").pack(side=tk.LEFT, padx=30, pady=20)
        tk.Label(topbar,
                 text=datetime.datetime.now().strftime("%A, %d %B %Y"),
                 font=("Arial", 11), bg="#0d1820", fg="#3a6070").pack(side=tk.RIGHT, padx=30, pady=20)

        # Stats cards
        stats_row = tk.Frame(content, bg="#111d27")
        stats_row.pack(fill=tk.X, padx=28, pady=22)
        stats = self._get_stats()
        card_data = [
            ("Today's Revenue",  "Rs. {:,.2f}".format(stats["today_revenue"]), "#00d4aa"),
            ("Bills Today",      str(stats["today_bills"]),                     "#4a9eff"),
            ("Total Products",   str(stats["total_products"]),                  "#a78bfa"),
            ("Low Stock Alerts", str(stats["low_stock"]),                       "#ffb347"),
        ]
        for title, value, accent in card_data:
            self._stat_card(stats_row, title, value, accent)

        tk.Label(content, text="Quick Actions", font=("Arial", 13, "bold"),
                 bg="#111d27", fg="#6a8fa0").pack(anchor=tk.W, padx=32, pady=(4, 10))

        # Action cards
        actions_frame = tk.Frame(content, bg="#111d27")
        actions_frame.pack(fill=tk.BOTH, expand=True, padx=28, pady=(0, 28))

        actions = [
            ("New Bill",
             "Create a customer bill,\nadd products to cart\nand print a PDF receipt.",
             "#00d4aa", "#09231e", self.open_pos),
            ("Product Catalogue",
             "Browse all products,\nupdate prices and names,\nremove discontinued items.",
             "#4a9eff", "#091828", self.open_inventory_editor),
            ("Add Products",
             "Register new products\nwith price and opening\nstock quantity.",
             "#a78bfa", "#150e28", self.open_add_items),
            ("Stock Replenishment",
             "Add stock to existing\nproducts when inventory\nis running low.",
             "#ffb347", "#261a07", self.open_restock),
            ("Sales & Reports",
             "View transaction history,\nfilter by date and export\nto Excel file.",
             "#ff6b6b", "#260d0d", self.open_ledger),
        ]
        for col, (title, desc, accent, bg, cmd) in enumerate(actions):
            self._action_card(actions_frame, col, title, desc, accent, bg, cmd)

    def _nav_btn(self, parent, label, desc, cmd):
        frame = tk.Frame(parent, bg="#0f1923", cursor="hand2")
        frame.pack(fill=tk.X, padx=10, pady=2)
        inner = tk.Frame(frame, bg="#0f1923", padx=16, pady=10)
        inner.pack(fill=tk.X)
        lbl1 = tk.Label(inner, text=label, font=("Arial", 10, "bold"),
                        bg="#0f1923", fg="#c8d8e4", cursor="hand2")
        lbl1.pack(anchor=tk.W)
        lbl2 = tk.Label(inner, text=desc, font=("Arial", 8),
                        bg="#0f1923", fg="#2e5060", cursor="hand2",
                        wraplength=210, justify=tk.LEFT)
        lbl2.pack(anchor=tk.W)

        all_w = [frame, inner, lbl1, lbl2]

        def on_enter(e):
            for w in all_w:
                try:
                    w.config(bg="#16283a")
                except Exception:
                    pass

        def on_leave(e):
            for w in all_w:
                try:
                    w.config(bg="#0f1923")
                except Exception:
                    pass

        def on_click(e):
            cmd()

        for w in all_w:
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)
            w.bind("<Button-1>", on_click)

    def _stat_card(self, parent, title, value, accent):
        card = tk.Frame(parent, bg="#16253a", padx=18, pady=16)
        card.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=7)
        tk.Label(card, text=title, font=("Arial", 9),
                 bg="#16253a", fg="#3a6070").pack(anchor=tk.W)
        tk.Label(card, text=value, font=("Arial", 22, "bold"),
                 bg="#16253a", fg=accent).pack(anchor=tk.W, pady=(6, 0))

    def _action_card(self, parent, col, title, desc, accent, bg, cmd):
        card = tk.Frame(parent, bg=bg, padx=20, pady=20, cursor="hand2")
        card.grid(row=0, column=col, sticky="nsew", padx=7)
        parent.columnconfigure(col, weight=1)
        tk.Label(card, text=title, font=("Arial", 12, "bold"),
                 bg=bg, fg=accent).pack(anchor=tk.W, pady=(0, 6))
        tk.Label(card, text=desc, font=("Arial", 9),
                 bg=bg, fg="#7a9aaa", justify=tk.LEFT).pack(anchor=tk.W)
        tk.Button(card, text="Open  >", font=("Arial", 9, "bold"),
                  bg=accent, fg="#050505", bd=0, padx=14, pady=6,
                  cursor="hand2", command=cmd,
                  activebackground=accent).pack(anchor=tk.W, pady=(14, 0))

    def _get_stats(self):
        s = {"today_revenue": 0.0, "today_bills": 0,
             "total_products": 0, "low_stock": 0}
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            c.execute("SELECT COALESCE(SUM(total),0) FROM sales WHERE date LIKE ?",
                      (today + "%",))
            s["today_revenue"] = c.fetchone()[0] or 0.0
            c.execute("SELECT COUNT(*) FROM sales WHERE date LIKE ?",
                      (today + "%",))
            s["today_bills"] = c.fetchone()[0] or 0
            c.execute("SELECT COUNT(*) FROM items")
            s["total_products"] = c.fetchone()[0] or 0
            c.execute("SELECT COUNT(*) FROM items WHERE quantity < 10")
            s["low_stock"] = c.fetchone()[0] or 0
            conn.close()
        except Exception:
            pass
        return s

    def open_ledger(self):
        w = tk.Toplevel(self.root)
        LedgerView(w)

    def open_restock(self):
        w = tk.Toplevel(self.root)
        RestockManager(w)

    def open_add_items(self):
        w = tk.Toplevel(self.root)
        AddItems(w)

    def open_pos(self):
        w = tk.Toplevel(self.root)
        PosApp(w)

    def open_inventory_editor(self):
        w = tk.Toplevel(self.root)
        InventoryEditor(w)


if __name__ == "__main__":
    root = tk.Tk()
    app = MainApp(root)
    root.mainloop()