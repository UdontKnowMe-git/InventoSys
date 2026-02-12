from backend.database import DatabaseManager
import requests

class InventoryService:
    def __init__(self):
        self.db = DatabaseManager()

    def get_network_status(self):
        """Simple check for the UI lights."""
        try:
            requests.get("https://www.google.com", timeout=2)
            return True
        except:
            return False

    def sync_data(self):
        """Triggers the full Upload/Download sync."""
        return self.db.perform_full_sync()

    def login_user(self, username, password):
        query = "SELECT role FROM users WHERE username = ? AND password = ?"
        result = self.db.fetch_one(query, (username, password))
        return (True, result[0]) if result else (False, None)

    def add_user(self, username, password, role):
        query = "INSERT INTO users (username, password, role) VALUES (?, ?, ?)"
        if self.db.execute_query(query, (username, password, role)):
            return True, "User added successfully."
        return False, "Username already exists."

    def delete_user(self, username, current_user):
        if username == current_user:
            return False, "You cannot delete yourself!"
        query = "DELETE FROM users WHERE username = ?"
        if self.db.execute_query(query, (username,)):
            return True, "User deleted."
        return False, "Failed to delete user."

    def change_password(self, username, new_password):
        query = "UPDATE users SET password = ? WHERE username = ?"
        if self.db.execute_query(query, (new_password, username)):
            return True, "Password updated successfully."
        return False, "Failed to update password."

    def get_all_users(self):
        res = self.db.execute_query("SELECT username, role FROM users", is_read=True)
        return res if res else []

    def add_product(self, sku, name, cost, price, min_stock):
        if not sku or not name:
            return False, "SKU and Name are required."
        query = "INSERT INTO products (sku, name, stock_qty, unit_cost, retail_price, min_stock) VALUES (?, ?, 0, ?, ?, ?)"
        if self.db.execute_query(query, (sku, name, cost, price, min_stock)):
            return True, "Product added."
        return False, "SKU already exists."

    def delete_product(self, sku):
        check = self.db.fetch_one("SELECT name FROM products WHERE sku = ?", (sku,))
        if not check:
            return False, "Product not found."
        query = "DELETE FROM products WHERE sku = ?"
        if self.db.execute_query(query, (sku,)):
            return True, f"Product '{check[0]}' deleted."
        return False, "Failed to delete."

    def get_all_products(self, search_term=""):
        if search_term:
            query = "SELECT * FROM products WHERE name LIKE ? OR sku LIKE ?"
            res = self.db.execute_query(query, (f'%{search_term}%', f'%{search_term}%'), is_read=True)
        else:
            res = self.db.execute_query("SELECT * FROM products", is_read=True)
        return res if res else []

    def process_transaction(self, sku, trans_type, quantity):
        products = self.db.execute_query("SELECT id, stock_qty, name FROM products WHERE sku = ?", (sku,), is_read=True)
        if not products:
            return False, "Product not found."
        
        prod_id, current_stock, name = products[0]
        try:
            qty = int(quantity)
            if qty <= 0: return False, "Quantity must be positive."
        except ValueError:
            return False, "Invalid quantity."

        new_stock = current_stock + qty if trans_type == "IN" else current_stock - qty
        if trans_type == "OUT" and new_stock < 0:
            return False, f"Insufficient stock! Current: {current_stock}"

        # Update Stock
        update_q = "UPDATE products SET stock_qty = ? WHERE id = ?"
        self.db.execute_query(update_q, (new_stock, prod_id))

        # Record Transaction
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        trans_q = "INSERT INTO transactions (product_id, type, quantity, timestamp) VALUES (?, ?, ?, ?)"
        self.db.execute_query(trans_q, (prod_id, trans_type, qty, timestamp))

        return True, f"Transaction recorded. New Stock: {new_stock}"