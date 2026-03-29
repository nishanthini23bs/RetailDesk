import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import os

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

DB_PATH = "db/billing.db"


class LedgerView:
    def __init__(self, root):
        self.root = root
        self.root.title("Sales Ledger")
        self.root.geometry("1000x560")
        self.setup_ui()
        self.load_ledger()

    def setup_ui(self):
        top = tk.Frame(self.root, pady=8)
        top.pack(fill=tk.X, padx=10)

        tk.Label(top, text="Sales Ledger", font=("Arial", 15, "bold")).pack(side=tk.LEFT)

        btn_frame = tk.Frame(top)
        btn_frame.pack(side=tk.RIGHT)
        tk.Button(btn_frame, text="🔄 Refresh", command=self.load_ledger,
                  bg="#90CAF9", width=10).pack(side=tk.LEFT, padx=4)
        if PANDAS_AVAILABLE:
            tk.Button(btn_frame, text="📥 Export Excel", command=self.export_excel,
                      bg="#A5D6A7", width=14).pack(side=tk.LEFT, padx=4)

        # Filter row
        filter_row = tk.Frame(self.root)
        filter_row.pack(fill=tk.X, padx=10, pady=4)
        tk.Label(filter_row, text="Filter by date (YYYY-MM-DD):").pack(side=tk.LEFT)
        self.filter_entry = tk.Entry(filter_row, width=14)
        self.filter_entry.pack(side=tk.LEFT, padx=6)
        tk.Button(filter_row, text="Filter", command=self.load_ledger).pack(side=tk.LEFT)
        tk.Button(filter_row, text="Clear", command=self.clear_filter).pack(side=tk.LEFT, padx=4)

        # Treeview — Sales
        tk.Label(self.root, text="Sales", font=("Arial", 11, "bold")).pack(anchor=tk.W, padx=12)
        sales_frame = tk.Frame(self.root)
        sales_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)

        sales_cols = ("Invoice #", "Date", "Table", "Total (₹)")
        self.sales_tree = ttk.Treeview(sales_frame, columns=sales_cols, show="headings", height=8)
        vsb1 = ttk.Scrollbar(sales_frame, orient="vertical", command=self.sales_tree.yview)
        self.sales_tree.configure(yscrollcommand=vsb1.set)
        for col in sales_cols:
            self.sales_tree.heading(col, text=col)
            self.sales_tree.column(col, width=180, anchor=tk.CENTER)
        self.sales_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb1.pack(side=tk.RIGHT, fill=tk.Y)

        # Summary bar
        self.summary_label = tk.Label(self.root, text="", font=("Arial", 11),
                                      fg="#27ae60", anchor=tk.W)
        self.summary_label.pack(fill=tk.X, padx=14, pady=4)

    def load_ledger(self):
        date_filter = self.filter_entry.get().strip() if hasattr(self, 'filter_entry') else ""
        for row in self.sales_tree.get_children():
            self.sales_tree.delete(row)
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            if date_filter:
                c.execute("""
                    SELECT invoice_number, date, table_number, total
                    FROM sales WHERE date LIKE ?
                    ORDER BY date DESC
                """, (f"{date_filter}%",))
            else:
                c.execute("""
                    SELECT invoice_number, date, table_number, total
                    FROM sales ORDER BY date DESC
                """)
            rows = c.fetchall()
            for row in rows:
                inv, date, table, total = row
                self.sales_tree.insert("", tk.END,
                    values=(inv, date, table or "—", f"₹{total:.2f}"))

            grand_total = sum(r[3] for r in rows)
            self.summary_label.config(
                text=f"  Total sales: {len(rows)}   |   Grand total: ₹{grand_total:.2f}"
            )
            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("DB Error", str(e), parent=self.root)

    def clear_filter(self):
        self.filter_entry.delete(0, tk.END)
        self.load_ledger()

    def export_excel(self):
        if not PANDAS_AVAILABLE:
            messagebox.showwarning("Unavailable", "Install pandas and openpyxl to export.", parent=self.root)
            return
        try:
            conn = sqlite3.connect(DB_PATH)
            df_sales = pd.read_sql_query(
                "SELECT invoice_number, date, table_number, total FROM sales ORDER BY date DESC",
                conn
            )
            df_items = pd.read_sql_query("""
                SELECT s.invoice_number, i.name, si.quantity, si.price,
                       si.quantity * si.price AS subtotal
                FROM sale_items si
                JOIN sales s ON si.sale_id = s.id
                JOIN items i ON si.item_id = i.id
                ORDER BY s.date DESC
            """, conn)
            conn.close()

            downloads = os.path.join(os.path.expanduser("~"), "Downloads")
            os.makedirs(downloads, exist_ok=True)
            from datetime import datetime
            fname = os.path.join(downloads, f"Ledger_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx")

            with pd.ExcelWriter(fname, engine='openpyxl') as writer:
                df_sales.to_excel(writer, sheet_name='Sales Summary', index=False)
                df_items.to_excel(writer, sheet_name='Sale Items', index=False)

            messagebox.showinfo("Exported", f"Ledger exported to:\n{fname}", parent=self.root)
        except Exception as e:
            messagebox.showerror("Export Error", str(e), parent=self.root)


if __name__ == "__main__":
    root = tk.Tk()
    LedgerView(root)
    root.mainloop()
