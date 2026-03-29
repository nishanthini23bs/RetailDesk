import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3

DB_PATH = "db/billing.db"


class InventoryEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("Inventory Editor")
        self.root.geometry("860x460")
        self.setup_ui()
        self.load_inventory()

    def setup_ui(self):
        # Treeview
        tree_frame = tk.Frame(self.root)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.tree = ttk.Treeview(tree_frame,
                                  columns=("ID","Barcode","Name","Price","Qty"),
                                  show="headings")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)

        widths = [50, 140, 240, 90, 80]
        for col, w in zip(("ID","Barcode","Name","Price","Qty"), widths):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w, anchor=tk.CENTER)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        # Edit form
        form = tk.Frame(self.root, pady=8)
        form.pack(fill=tk.X, padx=10)

        fields = [("ID", 6), ("Barcode", 18), ("Name", 28), ("Price", 10), ("Qty", 8)]
        self.entries = {}
        for col, (label, width) in enumerate(fields):
            tk.Label(form, text=f"{label}:").grid(row=0, column=col*2, padx=4)
            e = tk.Entry(form, width=width)
            e.grid(row=0, column=col*2+1, padx=4)
            self.entries[label] = e
        self.entries["ID"].config(state="readonly")

        # Buttons
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=8)
        tk.Button(btn_frame, text="✏️ Update Item", command=self.update_item,
                  width=16, bg="#81C784").pack(side=tk.LEFT, padx=6)
        tk.Button(btn_frame, text="🗑 Delete Item", command=self.delete_item,
                  width=16, bg="#EF9A9A").pack(side=tk.LEFT, padx=6)
        tk.Button(btn_frame, text="🔄 Refresh", command=self.load_inventory,
                  width=14).pack(side=tk.LEFT, padx=6)

    def load_inventory(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT id, barcode, name, price, quantity FROM items ORDER BY name")
            for row in cursor.fetchall():
                self.tree.insert("", tk.END, values=row)
            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("DB Error", str(e), parent=self.root)

    def on_select(self, event):
        sel = self.tree.focus()
        if not sel:
            return
        vals = self.tree.item(sel, 'values')
        labels = ["ID","Barcode","Name","Price","Qty"]
        for label, val in zip(labels, vals):
            e = self.entries[label]
            state = e.cget("state")
            if state == "readonly":
                e.config(state="normal")
                e.delete(0, tk.END)
                e.insert(0, val)
                e.config(state="readonly")
            else:
                e.delete(0, tk.END)
                e.insert(0, val)

    def update_item(self):
        try:
            item_id = int(self.entries["ID"].get())
            price   = float(self.entries["Price"].get())
            qty     = int(self.entries["Qty"].get())
            if qty < 0:
                raise ValueError("Qty cannot be negative")
        except ValueError as e:
            messagebox.showerror("Input Error", str(e), parent=self.root)
            return

        name    = self.entries["Name"].get().strip()
        barcode = self.entries["Barcode"].get().strip()
        if not name or not barcode:
            messagebox.showerror("Input Error", "Name and Barcode are required.", parent=self.root)
            return

        try:
            conn = sqlite3.connect(DB_PATH)
            conn.execute("""
                UPDATE items SET barcode=?, name=?, price=?, quantity=? WHERE id=?
            """, (barcode, name, price, qty, item_id))
            conn.commit()
            conn.close()
            messagebox.showinfo("Updated", "Item updated successfully.", parent=self.root)
            self.load_inventory()
        except sqlite3.Error as e:
            messagebox.showerror("DB Error", str(e), parent=self.root)

    def delete_item(self):
        item_id = self.entries["ID"].get()
        if not item_id:
            return
        if not messagebox.askyesno("Confirm", "Delete this item?", parent=self.root):
            return
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.execute("DELETE FROM items WHERE id=?", (item_id,))
            conn.commit()
            conn.close()
            messagebox.showinfo("Deleted", "Item deleted.", parent=self.root)
            self.load_inventory()
        except sqlite3.Error as e:
            messagebox.showerror("DB Error", str(e), parent=self.root)


if __name__ == "__main__":
    root = tk.Tk()
    InventoryEditor(root)
    root.mainloop()
