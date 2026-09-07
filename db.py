import sqlite3

def get_db():
    conn = sqlite3.connect("kirana_store.db", timeout=10.0)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for concurrency safety (Multiple bills / stock-in operations at once)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Inventory Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku_name TEXT UNIQUE NOT NULL,
            cost_price REAL NOT NULL,
            mrp REAL NOT NULL,
            quantity INTEGER NOT NULL,
            gst_percent REAL NOT NULL
        )
    """)
    
    # Bills Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT,
            payment_mode TEXT,
            subtotal REAL,
            cgst REAL,
            sgst REAL,
            total_amount REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Bill Items Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bill_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_id INTEGER,
            sku_name TEXT,
            quantity INTEGER,
            mrp REAL,
            gst_percent REAL,
            total REAL,
            FOREIGN KEY(bill_id) REFERENCES bills(id)
        )
    """)
    
    # Khata (Credit) Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS khata (
            customer_name TEXT PRIMARY KEY,
            balance REAL DEFAULT 0.0
        )
    """)
    
    # Standing Preferences Table (Lives outside context window across sessions)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS preferences (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully with concurrency support.")