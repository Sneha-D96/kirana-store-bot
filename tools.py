import os
import sqlite3
from db import get_db
from pdf_pptx import generate_pdf_invoice, generate_pptx_deck

def receive_stock(sku_name: str, quantity: int = 1, cost_price: float = 0.0, mrp: float = 0.0, gst_percent: float = -1.0) -> str:
    """Record incoming stock or add a new product."""
    sku_name = sku_name.lower().strip()
    
    missing = []
    if cost_price <= 0: missing.append("Cost Price (CP)")
    if mrp <= 0: missing.append("MRP")
    if gst_percent < 0: missing.append("GST percentage")
        
    if missing:
        return f"Please provide the missing {', '.join(missing)} for **{sku_name.title()}** so I can update inventory."
        
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO inventory (sku_name, cost_price, mrp, quantity, gst_percent)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(sku_name) DO UPDATE SET
            quantity = quantity + excluded.quantity,
            cost_price = CASE WHEN excluded.cost_price > 0 THEN excluded.cost_price ELSE inventory.cost_price END,
            mrp = CASE WHEN excluded.mrp > 0 THEN excluded.mrp ELSE inventory.mrp END,
            gst_percent = CASE WHEN excluded.gst_percent >= 0 THEN excluded.gst_percent ELSE inventory.gst_percent END
    """, (sku_name, quantity, cost_price, mrp, gst_percent))
    conn.commit()
    conn.close()
    return f"Stock updated: {quantity} units of **{sku_name.title()}** added (Cost: ₹{cost_price}, MRP: ₹{mrp}, GST: {gst_percent}%)."

def query_stock(sku_name: str = "") -> str:
    """Check current available stock or prices."""
    conn = get_db()
    cursor = conn.cursor()
    if sku_name:
        search_term = sku_name.lower().strip()
        cursor.execute("SELECT * FROM inventory WHERE sku_name LIKE ?", (f"%{search_term}%",))
    else:
        cursor.execute("SELECT * FROM inventory")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return "No matching inventory found in DB."
    
    result = []
    for r in rows:
        result.append(f"{r['sku_name'].title()}: {r['quantity']} available | MRP: ₹{r['mrp']} | Cost: ₹{r['cost_price']}")
    return "\n".join(result)

def check_low_stock(threshold: int = 10) -> str:
    """Check for items running out of stock."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM inventory WHERE quantity <= ?", (threshold,))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return f"Stock is looking good. No items are at or below {threshold} units."
    
    result = [f"{r['sku_name'].title()}: only {r['quantity']} left" for r in rows]
    return f"Low stock alert (<= {threshold} units):\n" + "\n".join(result)

def cut_bill(items: list, payment_mode: str = "UPI", customer_name: str = "") -> str:
    """Generate a bill with strict Oversell Guard and Deduct Stock."""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("BEGIN TRANSACTION;")
        verified_items, subtotal, total_cgst, total_sgst = [], 0.0, 0.0, 0.0
        
        for item in items:
            search_name = item['sku_name'].lower().strip()
            cursor.execute("SELECT * FROM inventory WHERE sku_name LIKE ?", (f"%{search_name}%",))
            db_item = cursor.fetchone()
            
            if not db_item:
                conn.rollback()
                conn.close()
                return f"Error: Product '{item['sku_name']}' does not exist in inventory."
            
            if db_item['quantity'] < item['quantity']:
                conn.rollback()
                conn.close()
                return f"Oversell Refused: Only {db_item['quantity']} of '{db_item['sku_name'].title()}' in stock (Requested {item['quantity']})."
            
            item_total = db_item['mrp'] * item['quantity']
            gst_slab = db_item['gst_percent']
            base_price = item_total / (1 + (gst_slab / 100))
            gst_amount = item_total - base_price
            
            subtotal += base_price
            total_cgst += gst_amount / 2
            total_sgst += gst_amount / 2
            
            verified_items.append({
                "id": db_item['id'], "sku_name": db_item['sku_name'],
                "quantity": item['quantity'], "mrp": db_item['mrp'],
                "gst_percent": gst_slab, "total": item_total
            })

        grand_total = subtotal + total_cgst + total_sgst

        for vi in verified_items:
            cursor.execute("UPDATE inventory SET quantity = quantity - ? WHERE id = ?", (vi['quantity'], vi['id']))
            
        cursor.execute("""
            INSERT INTO bills (customer_name, payment_mode, subtotal, cgst, sgst, total_amount)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (customer_name, payment_mode, subtotal, total_cgst, total_sgst, grand_total))
        bill_id = cursor.lastrowid

        for vi in verified_items:
            cursor.execute("""
                INSERT INTO bill_items (bill_id, sku_name, quantity, mrp, gst_percent, total)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (bill_id, vi['sku_name'], vi['quantity'], vi['mrp'], vi['gst_percent'], vi['total']))

        if payment_mode.lower() == "khata" and customer_name:
            cursor.execute("""
                INSERT INTO khata (customer_name, balance) VALUES (?, ?)
                ON CONFLICT(customer_name) DO UPDATE SET balance = balance + excluded.balance
            """, (customer_name.lower(), grand_total))

        conn.commit()
        conn.close()
        return f"Bill #{bill_id} generated successfully! Total: ₹{grand_total:.2f} (CGST: ₹{total_cgst:.2f}, SGST: ₹{total_sgst:.2f} | Mode: {payment_mode})."
        
    except Exception as e:
        conn.rollback()
        conn.close()
        return f"Transaction Failed: {str(e)}"

def manage_khata(customer_name: str, action: str, amount: float = 0.0) -> str:
    """Manage customer credit balances (Khata)."""
    conn = get_db()
    cursor = conn.cursor()
    search_name = customer_name.lower().strip()
    
    if action in ["balance", "query"]:
        cursor.execute("SELECT balance FROM khata WHERE LOWER(customer_name) LIKE ?", (f"%{search_name}%",))
        row = cursor.fetchone()
        conn.close()
        return f"{customer_name.title()}'s balance is ₹{row['balance']:.2f}" if row else f"No active khata found for {customer_name}."
    elif action == "pay":
        cursor.execute("UPDATE khata SET balance = balance - ? WHERE LOWER(customer_name) LIKE ?", (amount, f"%{search_name}%"))
        conn.commit()
        conn.close()
        return f"Recorded payment of ₹{amount} from {customer_name.title()}."
    elif action == "add":
        cursor.execute("""
            INSERT INTO khata (customer_name, balance) VALUES (?, ?)
            ON CONFLICT(customer_name) DO UPDATE SET balance = balance + excluded.balance
        """, (customer_name.lower(), amount))
        conn.commit()
        conn.close()
        return f"Added ₹{amount} credit to {customer_name.title()}'s khata."
        
    conn.close()
    return "Invalid khata action."

def send_khata_reminder(customer_name: str) -> str:
    """Generate a payment reminder message for a customer's khata balance."""
    conn = get_db()
    cursor = conn.cursor()
    search_name = customer_name.lower().strip()
    cursor.execute("SELECT customer_name, balance FROM khata WHERE LOWER(customer_name) LIKE ?", (f"%{search_name}%",))
    row = cursor.fetchone()
    conn.close()
    
    if not row or row['balance'] <= 0:
        return f"No outstanding balance found for {customer_name.title()}."
    
    return f"Reminder for {row['customer_name'].title()}: \"Dear {row['customer_name'].title()}, please clear your pending khata balance of ₹{row['balance']:.2f} at Sneha's Kirana Store. Thank you!\""

def set_preference(key: str, value: str) -> str:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO preferences (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))
    conn.commit()
    conn.close()
    return f"Preference saved persistently: {key} = {value}"

def get_preferences() -> str:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM preferences")
    rows = cursor.fetchall()
    conn.close()
    return "Default payment mode: UPI." if not rows else ", ".join([f"{r['key']}: {r['value']}" for r in rows])

def daily_close() -> str:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(total_amount), SUM(cgst + sgst), payment_mode FROM bills GROUP BY payment_mode")
    rows = cursor.fetchall()
    conn.close()
    if not rows: return "No sales recorded yet today."
    total_sales = sum(r[0] for r in rows if r[0])
    total_tax = sum(r[1] for r in rows if r[1])
    breakdown = [f"{r[2]}: ₹{r[0]:.2f}" for r in rows if r[2] and r[0]]
    return f"Daily Close Summary:\n- Total Sales: ₹{total_sales:.2f}\n- Total Tax Collected: ₹{total_tax:.2f}\n- Split: {' | '.join(breakdown)}"

def generate_latest_invoice_pdf() -> str:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM bills ORDER BY id DESC LIMIT 1")
    bill = cursor.fetchone()
    if not bill:
        conn.close()
        return None
    cursor.execute("SELECT * FROM bill_items WHERE bill_id = ?", (bill['id'],))
    items = cursor.fetchall()
    conn.close()
    return generate_pdf_invoice(bill['id'], dict(bill), [dict(i) for i in items])

def generate_sales_deck() -> str:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as orders, SUM(total_amount) as sales, SUM(cgst + sgst) as gst FROM bills")
    row = cursor.fetchone()
    cursor.execute("SELECT sku_name, SUM(quantity) as qty FROM bill_items GROUP BY sku_name ORDER BY qty DESC LIMIT 3")
    top_items = cursor.fetchall()
    cursor.execute("SELECT sku_name, quantity FROM inventory ORDER BY quantity ASC LIMIT 3")
    low_items = cursor.fetchall()
    conn.close()
    data = {
        "total_orders": row['orders'] or 0, "total_sales": row['sales'] or 0.0,
        "total_gst": row['gst'] or 0.0, "top_items": top_items, "low_items": low_items
    }
    return generate_pptx_deck(data)