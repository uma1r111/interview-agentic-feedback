"""
One-time setup script to seed the users table with HR and Hiring Manager accounts.

Usage:
    python scripts/seed_users.py

Safe to re-run — existing users are skipped, not overwritten. To change a
password, delete the row from the users table first (or add an update path
if you need that later) and re-run this script.
"""
import sys
import os
import getpass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.auth import init_users_table, create_user, get_user

# Edit these two records if emails change. Passwords are prompted at runtime
# so they are never committed to source control or left sitting in a file.
ACCOUNTS = [
    {
        "email": "saba.hr@imperiumdynamics.com",
        "role": "hr",
        "display_name": "Saba",
    },
    {
        "email": "berkha.hm@imperiumdynamics.com",
        "role": "hiring_manager",
        "display_name": "Berkha",
    },
]


def main():
    print("=" * 60)
    print("USER SEED — AI Interview Feedback System")
    print("=" * 60)

    init_users_table()

    for account in ACCOUNTS:
        existing = get_user(account["email"])
        if existing:
            print(f"[skip] {account['email']} already exists (role: {existing['role']})")
            continue

        print(f"\nSetting up: {account['display_name']} <{account['email']}> ({account['role']})")
        while True:
            password = getpass.getpass("  Enter password: ")
            confirm = getpass.getpass("  Confirm password: ")
            if password != confirm:
                print("  Passwords did not match. Try again.")
                continue
            if len(password) < 8:
                print("  Password must be at least 8 characters. Try again.")
                continue
            break

        created = create_user(
            email=account["email"],
            password=password,
            role=account["role"],
            display_name=account["display_name"],
        )
        if created:
            print(f"  [OK] Account created for {account['email']}")
        else:
            print(f"  [Error] Could not create account for {account['email']}")

    print("\nDone. Accounts are ready for login.")


if __name__ == "__main__":
    main()