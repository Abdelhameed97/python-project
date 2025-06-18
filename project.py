import psycopg2
import bcrypt
import getpass
import sys
import os
from datetime import datetime

# Color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

# Database configuration
DB_CONFIG = {
    "host": "localhost",
    "database": "loan_db",
    "user": "mido",
    "password": "12345"
}

def clear_screen():
    """Clear the terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header(title):
    """Print a colored header"""
    clear_screen()
    print(f"\n{Colors.BLUE}{'='*60}")
    print(f"{Colors.BOLD}{title.center(60)}{Colors.END}")
    print(f"{'='*60}{Colors.END}\n")

def print_success(message):
    """Print success message in green"""
    print(f"{Colors.GREEN}{Colors.BOLD}✓ {message}{Colors.END}")

def print_error(message):
    """Print error message in red"""
    print(f"{Colors.RED}{Colors.BOLD}✗ {message}{Colors.END}")

def print_warning(message):
    """Print warning message in yellow"""
    print(f"{Colors.YELLOW}{Colors.BOLD}⚠ {message}{Colors.END}")

class Database:
    def __init__(self):
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            self.create_tables()
            print_success("Database connection established")
        except psycopg2.Error as e:
            print_error(f"Database connection failed: {e}")
            sys.exit(1)
    
    def create_tables(self):
        with self.conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    password_hash VARCHAR(100) NOT NULL,
                    is_admin BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS loans (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    amount DECIMAL(10, 2) NOT NULL,
                    term INTEGER NOT NULL,
                    interest_rate DECIMAL(5, 2) NOT NULL,
                    status VARCHAR(20) DEFAULT 'pending',
                    balance DECIMAL(10, 2) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS payments (
                    id SERIAL PRIMARY KEY,
                    loan_id INTEGER REFERENCES loans(id),
                    amount DECIMAL(10, 2) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create admin user if not exists
            cursor.execute("SELECT 1 FROM users WHERE username = 'admin'")
            if not cursor.fetchone():
                password_hash = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode()
                cursor.execute(
                    "INSERT INTO users (username, password_hash, is_admin) VALUES (%s, %s, %s)",
                    ("admin", password_hash, True)
                )
            self.conn.commit()

    def execute(self, query, params=None, fetch=False):
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(query, params or ())
                if fetch:
                    return cursor.fetchall()
                self.conn.commit()
        except psycopg2.Error as e:
            print_error(f"Database error: {e}")
            return None

    def close(self):
        self.conn.close()

def show_main_menu():
    print_header("LOAN MANAGEMENT SYSTEM")
    print(f"{Colors.CYAN}1. Register")
    print("2. Login")
    print(f"3. Exit{Colors.END}")
    return input(f"\n{Colors.YELLOW}Choose option (1-3): {Colors.END}")

def register(db):
    print_header("REGISTER")
    username = input(f"{Colors.CYAN}Choose username: {Colors.END}")
    
    if db.execute("SELECT 1 FROM users WHERE username = %s", (username,), fetch=True):
        print_error("Username already exists!")
        return
    
    password = getpass.getpass(f"{Colors.CYAN}Choose password: {Colors.END}")
    confirm = getpass.getpass(f"{Colors.CYAN}Confirm password: {Colors.END}")
    
    if password != confirm:
        print_error("Passwords don't match!")
        return
    
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    db.execute(
        "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
        (username, password_hash)
    )
    print_success("Registration successful!")

def login(db):
    print_header("LOGIN")
    username = input(f"{Colors.CYAN}Username: {Colors.END}")
    password = getpass.getpass(f"{Colors.CYAN}Password: {Colors.END}")
    
    user = db.execute(
        "SELECT id, password_hash, is_admin FROM users WHERE username = %s",
        (username,), fetch=True
    )
    
    if not user or not bcrypt.checkpw(password.encode(), user[0][1].encode()):
        print_error("Invalid credentials!")
        return None
    
    print_success(f"Welcome, {username}!")
    return {"id": user[0][0], "username": username, "is_admin": user[0][2]}

def show_user_menu(db, user):
    while True:
        print_header(f"USER DASHBOARD ({user['username']})")
        
        # Basic options for all users
        options = [
            "1. Apply for loan",
            "2. View my loans",
            "3. Make payment",
            "4. Logout"
        ]
        
        # Add admin options if user is admin
        if user["is_admin"]:
            options.insert(3, "5. Review Pending Loans")
            options.insert(4, "6. Manage Users")
        
        # Print all options
        for option in options:
            print(option)
        
        choice = input(f"\n{Colors.YELLOW}Choose option: {Colors.END}")
        
        if choice == "1":
            apply_for_loan(db, user)
        elif choice == "2":
            view_loans(db, user)
        elif choice == "3":
            make_payment(db, user)
        elif choice == "4":
            break
        elif choice == "5" and user["is_admin"]:
            review_pending_loans(db)
        elif choice == "6" and user["is_admin"]:
            manage_users(db)
        else:
            print_error("Invalid choice!")
        
        input(f"\n{Colors.YELLOW}Press Enter to continue...{Colors.END}")

def apply_for_loan(db, user):
    print_header("APPLY FOR LOAN")
    
    try:
        amount = float(input(f"{Colors.CYAN}Loan amount ($): {Colors.END}"))
        term = int(input(f"{Colors.CYAN}Loan term (months): {Colors.END}"))
        
        if amount <= 0 or term <= 0:
            print_error("Amount and term must be positive!")
            return
        
        interest_rate = min(5.0 + (term / 12), 15.0)
        print(f"{Colors.YELLOW}Calculated interest rate: {interest_rate:.2f}%{Colors.END}")
        
        db.execute(
            """INSERT INTO loans (user_id, amount, term, interest_rate, balance)
            VALUES (%s, %s, %s, %s, %s)""",
            (user["id"], amount, term, interest_rate, amount)
        )
        print_success("Loan application submitted successfully!")
        
    except ValueError:
        print_error("Invalid input! Please enter numbers.")

def view_loans(db, user):
    print_header("YOUR LOANS")
    
    loans = db.execute(
        """SELECT id, amount, term, interest_rate, status, balance, created_at 
        FROM loans WHERE user_id = %s ORDER BY created_at DESC""",
        (user["id"],), fetch=True
    )
    
    if not loans:
        print_warning("You have no loans.")
        return
    
    for loan in loans:
        status_color = Colors.GREEN if loan[4] == 'approved' else (
            Colors.YELLOW if loan[4] == 'pending' else Colors.BLUE
        )
        
        print(f"\n{Colors.BOLD}Loan ID: {loan[0]}{Colors.END}")
        print(f"{Colors.CYAN}Amount: ${loan[1]:.2f}")
        print(f"Term: {loan[2]} months")
        print(f"Interest Rate: {loan[3]:.2f}%")
        print(f"Status: {status_color}{loan[4]}{Colors.END}")
        print(f"Balance: ${loan[5]:.2f}")
        print(f"Date: {loan[6].strftime('%Y-%m-%d')}")

def make_payment(db, user):
    print_header("MAKE PAYMENT")
    
    approved_loans = db.execute(
        """SELECT id, amount, balance FROM loans 
        WHERE user_id = %s AND status = 'approved'""",
        (user["id"],), fetch=True
    )
    
    if not approved_loans:
        print_warning("You have no approved loans.")
        return
    
    print(f"{Colors.CYAN}Your approved loans:{Colors.END}")
    for loan in approved_loans:
        print(f"ID: {loan[0]} - Amount: ${loan[1]:.2f} - Balance: ${loan[2]:.2f}")
    
    try:
        loan_id = int(input(f"\n{Colors.CYAN}Enter loan ID to pay: {Colors.END}"))
        amount = float(input(f"{Colors.CYAN}Payment amount ($): {Colors.END}"))
        
        selected_loan = None
        for loan in approved_loans:
            if loan[0] == loan_id:
                selected_loan = loan
                break
        
        if not selected_loan:
            print_error("Invalid loan ID!")
            return
        
        if amount <= 0:
            print_error("Amount must be positive!")
            return
        
        if amount > selected_loan[2]:
            print_error("Payment exceeds loan balance!")
            return
        
        new_balance = selected_loan[2] - amount
        db.execute(
            "UPDATE loans SET balance = %s WHERE id = %s",
            (new_balance, loan_id)
        )
        
        db.execute(
            "INSERT INTO payments (loan_id, amount) VALUES (%s, %s)",
            (loan_id, amount)
        )
        
        if new_balance == 0:
            db.execute(
                "UPDATE loans SET status = 'paid' WHERE id = %s",
                (loan_id,)
            )
        
        print_success("Payment successful!")
        
    except ValueError:
        print_error("Invalid input! Please enter numbers.")

def review_pending_loans(db):
    print_header("REVIEW PENDING LOANS")
    
    loans = db.execute(
        """SELECT l.id, u.username, l.amount, l.term, l.created_at 
        FROM loans l JOIN users u ON l.user_id = u.id 
        WHERE l.status = 'pending'""",
        fetch=True
    )
    
    if not loans:
        print_warning("No pending loans found.")
        return
    
    print(f"{Colors.CYAN}Pending Loans:{Colors.END}")
    for loan in loans:
        print(f"\nID: {loan[0]} | User: {loan[1]}")
        print(f"Amount: ${loan[2]:.2f} | Term: {loan[3]} months")
        print(f"Applied: {loan[4].strftime('%Y-%m-%d')}")
    
    try:
        loan_id = int(input(f"\n{Colors.YELLOW}Enter loan ID to approve/reject: {Colors.END}"))
        action = input(f"{Colors.YELLOW}Approve (A) or Reject (R)? {Colors.END}").lower()
        
        if action == 'a':
            db.execute("UPDATE loans SET status = 'approved' WHERE id = %s", (loan_id,))
            print_success("Loan approved!")
        elif action == 'r':
            db.execute("UPDATE loans SET status = 'rejected' WHERE id = %s", (loan_id,))
            print_warning("Loan rejected.")
        else:
            print_error("Invalid action!")
    except ValueError:
        print_error("Invalid input!")

def manage_users(db):
    print_header("MANAGE USERS")
    users = db.execute("SELECT id, username, is_admin FROM users", fetch=True)
    
    print(f"{Colors.CYAN}User List:{Colors.END}")
    for user in users:
        role = "Admin" if user[2] else "User"
        print(f"\nID: {user[0]} | Username: {user[1]} | Role: {role}")
    
    print("\nAdmin functions coming soon!")

def main():
    db = Database()
    
    try:
        while True:
            choice = show_main_menu()
            
            if choice == "1":
                register(db)
            elif choice == "2":
                user = login(db)
                if user:
                    show_user_menu(db, user)
            elif choice == "3":
                print(f"\n{Colors.GREEN}Goodbye!{Colors.END}")
                break
            else:
                print_error("Invalid choice!")
            
            input(f"\n{Colors.YELLOW}Press Enter to continue...{Colors.END}")
    finally:
        db.close()

if __name__ == "__main__":
    main()