# 🧾 Retail Desk — POS & Inventory Management

A complete **offline billing and inventory management** desktop application built with **Python** and **Tkinter**. Designed for small retail businesses to manage sales, inventory, invoicing, and daily ledger — all without internet.

---

## ✅ Features

- 🛒 **POS System** — Add items by search or barcode scan, manage cart, save sales
- 📦 **Inventory Management** — Add, edit, delete, and restock items
- 📊 **Sales Ledger** — View all transactions, filter by date, export to Excel
- 🧾 **Invoice PDF Generation** — Auto-saved to Downloads/invoices/
- 📷 **Barcode Scanning** — Webcam-based scanner using OpenCV + pyzbar
- 💾 **Fully Offline** — Uses local SQLite database, no internet required
- 🖨 **Print Support** — Opens PDF for printing on Windows/macOS/Linux


---

## 💡 Tech Stack

| Technology | Purpose |
|---|---|
| Python 3.x | Core language |
| Tkinter | GUI framework |
| SQLite | Local database |
| ReportLab | PDF invoice generation |
| OpenCV + pyzbar | Barcode scanning |
| Pandas + openpyxl | Excel ledger export |
| Pillow | Logo image support |

---

## ⚙️ Installation

### 1. Clone the repository
```bash
git clone https://github.com/YOUR_USERNAME/Billing_App.git
cd Billing_App
```

### 2. (Recommended) Create a virtual environment
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

> **Windows note for pyzbar:** You may need to install the Visual C++ redistributable or use:
> `pip install pyzbar[scripts]`

---

## 🚀 Running the App

```bash
python main.py
```

The main dashboard opens with buttons for all modules.

---

## 📁 Project Structure

```
BillingApp/
├── main.py               # App entry point & dashboard
├── pos_gui.py            # POS billing screen
├── add_items.py          # Add new inventory items
├── inventory_editor.py   # Edit / delete inventory
├── restock.py            # Restock existing items
├── ledger.py             # Sales ledger & Excel export
├── barcode_scanner.py    # Standalone barcode scanner utility
├── db_setup.py           # Database initializer
├── requirements.txt      # Python dependencies
├── db/                   # SQLite database (auto-created)
└── invoices/             # Generated PDFs (auto-created)
```

---

## 📦 Build as Windows Executable

```bash
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed main.py
```

Output `.exe` will be in the `dist/` folder.

---

## 📌 Notes

- Tested on Windows 11
- Barcode scanning requires a webcam and good lighting
- The `db/` folder and database are auto-created on first run
- Invoices are saved to `~/Downloads/invoices/`

---

## 📜 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🙋 Author

Nishanthini BS
