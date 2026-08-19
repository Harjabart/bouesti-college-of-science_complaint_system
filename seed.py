import os
from werkzeug.security import generate_password_hash
from app import app, db, User, Category

def seed_database():
    with app.app_context():
        # 1. Create database tables if they don't exist
        print("Creating database tables...")
        db.create_all()

        # 2. Seed Default Complaint Categories
        default_categories = [
            "Academic Affairs",
            "Bursary & Payments",
            "Hostel & Accommodation",
            "Library Services",
            "ICT & Portal Issues",
            "Facilities & Infrastructure",
            "General Misconduct / Security",
            "Other Enquiries"
        ]

        print("\n--- Seeding Complaint Categories ---")
        for cat_name in default_categories:
            existing_cat = Category.query.filter_by(name=cat_name).first()
            if not existing_cat:
                new_cat = Category(name=cat_name)
                db.session.add(new_cat)
                print(f" [ + ] Added category: {cat_name}")
            else:
                print(f" [ - ] Category already exists: {cat_name}")

        # 3. Seed Default Admin Account
        admin_email = "admin@bouesti.edu.ng"
        print("\n--- Seeding Default Admin Account ---")
        admin_user = User.query.filter_by(email=admin_email).first()

        if not admin_user:
            hashed_password = generate_password_hash("Admin@BOUESTI2026!", method="scrypt")
            admin_user = User(
                full_name="System Super Administrator",
                email=admin_email,
                matric_number="ADMIN/001",
                role="Admin",
                password_hash=hashed_password
            )
            db.session.add(admin_user)
            print(f" [ + ] Created Admin: {admin_email}")
            print(f"       Default Password: Admin@BOUESTI2026!")
        else:
            print(f" [ - ] Admin user already exists: {admin_email}")

        # Commit changes to database
        db.session.commit()
        print("\nDatabase seeding completed successfully!")

if __name__ == "__main__":
    seed_database()