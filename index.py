import tkinter as tk
from tkinter import ttk, messagebox
import threading
from backend.service import InventoryService

class LoginApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Login | Inventory System")
        self.root.geometry("400x350")
        self.service = InventoryService()
        
        frame = ttk.Frame(root, padding=30)
        frame.pack(expand=True)
        
        ttk.Label(frame, text="INVENTORY LOGIN", font=("Arial", 16, "bold")).pack(pady=20)
        
        #simple Connection Check
        self.status_lbl = ttk.Label(frame, text="Checking connection...", font=("Arial", 8))
        self.status_lbl.pack(pady=5)
        self.check_network_status()

        ttk.Label(frame, text="Username:").pack(anchor="w")
        self.user_entry = ttk.Entry(frame, width=30)
        self.user_entry.pack(pady=5)
        
        ttk.Label(frame, text="Password:").pack(anchor="w")
        self.pass_entry = ttk.Entry(frame, width=30, show="*")
        self.pass_entry.pack(pady=5)
        
        ttk.Button(frame, text="LOGIN", command=self.login).pack(pady=20, fill="x")

    def check_network_status(self):
        is_online = self.service.get_network_status()
        if is_online:
            self.status_lbl.config(text="🟢 Internet Available", foreground="green")
        else:
            self.status_lbl.config(text="🔴 No Internet (Local Mode)", foreground="red")
        self.root.after(5000, self.check_network_status)

    def login(self):
        user = self.user_entry.get()
        pwd = self.pass_entry.get()
        success, role = self.service.login_user(user, pwd)
        
        if success:
            self.root.destroy()
            self.launch_main_app(user, role)
        else:
            messagebox.showerror("Login Failed", "Invalid Username or Password")

    def launch_main_app(self, user, role):
        new_root = tk.Tk()
        app = InventoryApp(new_root, current_user=user, user_role=role)
        new_root.mainloop()


class InventoryApp:
    def __init__(self, root, current_user, user_role):
        self.service = InventoryService()
        self.root = root
        self.current_user = current_user
        self.user_role = user_role
        
        self.root.title(f"Inventory System - User: {current_user} ({user_role})")
        self.root.state('zoomed')

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", rowheight=30, font=("Arial", 10))
        style.configure("Treeview.Heading", font=("Arial", 11, "bold"))
        
        #top bar
        self.top_bar = ttk.Frame(root, padding=10)
        self.top_bar.pack(fill="x", side="top")
        
        # 1. LOGOUT BUTTON (Added Here)
        ttk.Button(self.top_bar, text="🚪 Logout", command=self.logout).pack(side="right", padx=5)

        # 2. SYNC BUTTON
        self.sync_btn = ttk.Button(self.top_bar, text="🔄 SYNC DATA", command=self.run_sync)
        self.sync_btn.pack(side="right", padx=5)
        
        # 3. STATUS LABEL
        self.status_lbl = ttk.Label(self.top_bar, text="Ready (Local Mode)", font=("Arial", 10))
        self.status_lbl.pack(side="right", padx=10)

        # --- TABS ---
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(expand=True, fill="both", padx=10, pady=10)

        self.tab_dashboard = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_dashboard, text=" Dashboard ")
        
        self.tab_manage = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_manage, text=" Manage Products ")
        
        self.tab_trans = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_trans, text=" Transactions ")

        if self.user_role == "Admin":
            self.tab_users = ttk.Frame(self.notebook)
            self.notebook.add(self.tab_users, text=" User Management ")
            self.setup_user_management()

        self.setup_dashboard()
        self.setup_manage_products()
        self.setup_transactions()
        self.refresh_table()
        
        # AUTO SYNC ON STARTUP
        self.root.after(1000, self.run_sync_background)

    def logout(self):
        if messagebox.askyesno("Logout", "Are you sure you want to logout?"):
            self.root.destroy()
            # Relaunch the Login Application
            root = tk.Tk()
            app = LoginApp(root)
            root.mainloop()

    def run_sync(self):
        """Manual Sync Triggered by Button"""
        self.sync_btn.config(state="disabled", text="Syncing...")
        self.status_lbl.config(text="⏳ Syncing with Cloud...", foreground="blue")
        threading.Thread(target=self._sync_thread, daemon=True).start()

    def run_sync_background(self):
        """Silent Startup Sync"""
        self.status_lbl.config(text="⏳ Auto-Syncing...", foreground="blue")
        threading.Thread(target=self._sync_thread, daemon=True).start()

    def _sync_thread(self):
        success, msg = self.service.sync_data()
        self.root.after(0, lambda: self._post_sync_ui(success, msg))

    def _post_sync_ui(self, success, msg):
        self.sync_btn.config(state="normal", text="🔄 SYNC DATA")
        if success:
            self.status_lbl.config(text="✅ " + msg, foreground="green")
            self.refresh_table()
        else:
            self.status_lbl.config(text="❌ Sync Failed", foreground="red")
            if "Download Failed" in msg or "Upload Failed" in msg:
                print(msg) 

    def setup_dashboard(self):
        top_frame = ttk.Frame(self.tab_dashboard, padding=10)
        top_frame.pack(fill="x")
        
        ttk.Label(top_frame, text="Search:").pack(side="left")
        self.search_var = tk.StringVar()
        ttk.Entry(top_frame, textvariable=self.search_var).pack(side="left", padx=5)
        ttk.Button(top_frame, text="Go", command=self.refresh_table).pack(side="left")
        ttk.Button(top_frame, text="Reset", command=lambda: [self.search_var.set(""), self.refresh_table()]).pack(side="left", padx=5)

        ttk.Button(top_frame, text="Change Password", command=self.open_password_dialog).pack(side="right", padx=5)
        ttk.Button(top_frame, text="Delete Selected", command=self.delete_selected_product).pack(side="right", padx=5)
        
        cols = ("SKU", "Name", "Stock", "Cost", "Price", "Min Stock")
        self.tree = ttk.Treeview(self.tab_dashboard, columns=cols, show="headings")
        
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=120, anchor="center")

        sb = ttk.Scrollbar(self.tab_dashboard, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=sb.set)
        
        self.tree.pack(side="left", fill="both", expand=True, padx=10, pady=5)
        sb.pack(side="right", fill="y", pady=5)
        
        self.tree.tag_configure("low_stock", background="#ffdddd")

    def setup_manage_products(self):
        frame = ttk.LabelFrame(self.tab_manage, text="Add New Product", padding=20)
        frame.pack(padx=20, pady=20, fill="x")

        fields = [("SKU:", 0, 0), ("Name:", 0, 2), ("Cost Price:", 1, 0), ("Retail Price:", 1, 2), ("Min Stock:", 2, 0)]
        self.entries = {}

        for text, r, c in fields:
            ttk.Label(frame, text=text).grid(row=r, column=c, padx=10, pady=10, sticky="e")
            entry = ttk.Entry(frame)
            entry.grid(row=r, column=c+1, padx=10, pady=10, sticky="w")
            self.entries[text] = entry

        ttk.Button(frame, text="Save Product", command=self.save_product).grid(row=3, column=0, columnspan=4, pady=20)

    def setup_transactions(self):
        frame = ttk.LabelFrame(self.tab_trans, text="Record Stock Movement", padding=20)
        frame.pack(padx=20, pady=20, fill="x")

        ttk.Label(frame, text="Product SKU:").grid(row=0, column=0, padx=10, pady=10)
        self.trans_sku = ttk.Entry(frame)
        self.trans_sku.grid(row=0, column=1, padx=10, pady=10)

        ttk.Label(frame, text="Quantity:").grid(row=0, column=2, padx=10, pady=10)
        self.trans_qty = ttk.Entry(frame)
        self.trans_qty.grid(row=0, column=3, padx=10, pady=10)

        ttk.Label(frame, text="Type:").grid(row=1, column=0, padx=10, pady=10)
        self.trans_type = tk.StringVar(value="IN")
        ttk.Radiobutton(frame, text="Stock IN", variable=self.trans_type, value="IN").grid(row=1, column=1, sticky="w")
        ttk.Radiobutton(frame, text="Stock OUT", variable=self.trans_type, value="OUT").grid(row=1, column=2, sticky="w")

        ttk.Button(frame, text="Submit Transaction", command=self.submit_transaction).grid(row=2, column=0, columnspan=4, pady=20)
        # REPORT BUTTON (Admin only)
        if self.user_role in ["Admin", "Manager"]:
            ttk.Button(
                frame,
                text="📊 Generate CSV Report",
                command=self.generate_report
            ).grid(row=3, column=0, columnspan=4, pady=10)


    def setup_user_management(self):
        frame = ttk.LabelFrame(self.tab_users, text="Add New User", padding=20)
        frame.pack(padx=20, pady=20, fill="x")
        
        ttk.Label(frame, text="Username:").grid(row=0, column=0, padx=5)
        self.new_user_name = ttk.Entry(frame)
        self.new_user_name.grid(row=0, column=1, padx=5)
        
        ttk.Label(frame, text="Password:").grid(row=0, column=2, padx=5)
        self.new_user_pass = ttk.Entry(frame)
        self.new_user_pass.grid(row=0, column=3, padx=5)
        
        ttk.Label(frame, text="Role:").grid(row=0, column=4, padx=5)
        self.new_user_role = ttk.Combobox(frame, values=["Admin", "Employee"], state="readonly", width=10)
        self.new_user_role.current(1)
        self.new_user_role.grid(row=0, column=5, padx=5)
        
        ttk.Button(frame, text="Add User", command=self.add_new_user).grid(row=0, column=6, padx=10)
        
        ttk.Label(self.tab_users, text="Existing Users", font=("Arial", 12, "bold")).pack(pady=10)
        self.user_tree = ttk.Treeview(self.tab_users, columns=("Username", "Role"), show="headings", height=8)
        self.user_tree.heading("Username", text="Username")
        self.user_tree.heading("Role", text="Role")
        self.user_tree.pack(fill="x", padx=20)
        
        ttk.Button(self.tab_users, text="Delete Selected User", command=self.delete_selected_user).pack(pady=10)
        self.refresh_users()

    def refresh_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        rows = self.service.get_all_products(self.search_var.get())
        for row in rows:
            display_row = row[1:] 
            if row[3] <= row[6]:
                self.tree.insert("", "end", values=display_row, tags=("low_stock",))
            else:
                self.tree.insert("", "end", values=display_row)

    def save_product(self):
        try:
            sku = self.entries["SKU:"].get()
            name = self.entries["Name:"].get()
            cost = float(self.entries["Cost Price:"].get())
            price = float(self.entries["Retail Price:"].get())
            min_s = int(self.entries["Min Stock:"].get())
            
            success, msg = self.service.add_product(sku, name, cost, price, min_s)
            if success:
                messagebox.showinfo("Success", msg)
                self.refresh_table()
                for e in self.entries.values(): e.delete(0, tk.END)
            else:
                messagebox.showerror("Error", msg)
        except ValueError:
            messagebox.showerror("Error", "Please enter valid numbers for Price/Stock")

    def delete_selected_product(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Select a product to delete")
            return
        
        item = self.tree.item(selected[0])['values']
        sku, name = item[0], item[1]
        
        if messagebox.askyesno("Confirm", f"Delete product '{name}'?"):
            success, msg = self.service.delete_product(sku)
            if success:
                self.refresh_table()
                messagebox.showinfo("Deleted", msg)
            else:
                messagebox.showerror("Error", msg)

    def submit_transaction(self):
        sku = self.trans_sku.get()
        qty = self.trans_qty.get()
        t_type = self.trans_type.get()

        success, msg = self.service.process_transaction(sku, t_type, qty)

        if success:

            # 🚨 STOCK EMPTY ALERT
            if "STOCK EMPTY" in msg:
                messagebox.showerror("Stock Empty", msg)

            # ⚠️ LOW STOCK ALERT
            elif "LOW STOCK" in msg:
                messagebox.showwarning("Low Stock Alert", msg)

            # ✅ NORMAL TRANSACTION
            else:
                messagebox.showinfo("Success", msg)

            self.refresh_table()
            self.trans_sku.delete(0, tk.END)
            self.trans_qty.delete(0, tk.END)

        else:
            messagebox.showerror("Error", msg)


    def refresh_users(self):
        for item in self.user_tree.get_children():
            self.user_tree.delete(item)
        for u in self.service.get_all_users():
            self.user_tree.insert("", "end", values=u)

    def add_new_user(self):
        u = self.new_user_name.get()
        p = self.new_user_pass.get()
        r = self.new_user_role.get()
        if u and p:
            success, msg = self.service.add_user(u, p, r)
            if success:
                messagebox.showinfo("Success", msg)
                self.refresh_users()
                self.new_user_name.delete(0, tk.END)
                self.new_user_pass.delete(0, tk.END)
            else:
                messagebox.showerror("Error", msg)
        else:
            messagebox.showerror("Error", "Username/Password required")

    def delete_selected_user(self):
        selected = self.user_tree.selection()
        if selected:
            username = self.user_tree.item(selected[0])['values'][0]
            success, msg = self.service.delete_user(username, self.current_user)
            if success:
                messagebox.showinfo("Success", msg)
                self.refresh_users()
            else:
                messagebox.showerror("Error", msg)

    def open_password_dialog(self):
        top = tk.Toplevel(self.root)
        top.title("Change Password")
        top.geometry("350x250")
        
        ttk.Label(top, text="Old Password:").pack(pady=5)
        old_entry = ttk.Entry(top, show="*")
        old_entry.pack(pady=5)
        
        ttk.Label(top, text="New Password:").pack(pady=5)
        new_entry = ttk.Entry(top, show="*")
        new_entry.pack(pady=5)
        
        def update():
            old_pass = old_entry.get()
            new_pass = new_entry.get()
            
            valid_user, _ = self.service.login_user(self.current_user, old_pass)
            if not valid_user:
                messagebox.showerror("Error", "Old password is incorrect!")
                return
            if not new_pass:
                messagebox.showerror("Error", "New password cannot be empty.")
                return

            success, msg = self.service.change_password(self.current_user, new_pass)
            if success:
                messagebox.showinfo("Success", msg)
                top.destroy()
            else:
                messagebox.showerror("Error", msg)
        
        ttk.Button(top, text="Update Password", command=update).pack(pady=20)

    def generate_report(self):

        if self.user_role not in ["Admin", "Manager"]:
            messagebox.showerror("Access Denied", "Only Admin/Manager can generate reports.")
            return

        success, msg = self.service.generate_csv_report()

        if success:
            messagebox.showinfo("Report", msg)
        else:
            messagebox.showerror("Report", msg)


if __name__ == "__main__":
    root = tk.Tk()
    app = LoginApp(root)
    root.mainloop()