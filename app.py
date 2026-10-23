import csv
import io
import os
import sqlite3
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta
from functools import wraps

from flask import Flask, Response, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or "smartplate-local-development-only-change-me"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "smartplate.db")

DAY_ADJUSTMENTS = {
    0: 0.075,
    1: 0.04,
    2: 0.03,
    3: 0.025,
    4: 0.05,
    5: -0.02,
    6: -0.08,
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    db.close()
    return user


def login_required(*allowed_roles):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = current_user()
            if user is None:
                flash("Please log in to continue.", "error")
                return redirect(url_for("login"))
            if allowed_roles and user["role"] not in allowed_roles:
                flash("You do not have permission to access that page.", "error")
                return redirect(url_for("home"))
            return func(*args, **kwargs)

        return wrapper

    return decorator


@app.context_processor
def inject_user():
    return {"current_user": current_user()}


def init_db():
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('student', 'staff', 'admin')),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS food_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            category TEXT NOT NULL CHECK (category IN ('breakfast', 'lunch', 'dinner')),
            price REAL NOT NULL,
            quantity_available INTEGER NOT NULL DEFAULT 0,
            is_available INTEGER NOT NULL DEFAULT 1,
            image_url TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id TEXT UNIQUE NOT NULL,
            user_id INTEGER NOT NULL,
            food_item_id INTEGER NOT NULL,
            booking_date TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('confirmed', 'cancelled')),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (food_item_id) REFERENCES food_items(id)
        );

        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            food_item_id INTEGER NOT NULL,
            rating INTEGER NOT NULL,
            comment TEXT,
            served_date TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (food_item_id) REFERENCES food_items(id)
        );

        CREATE TABLE IF NOT EXISTS waste_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            food_item_id INTEGER NOT NULL,
            quantity_prepared INTEGER NOT NULL,
            quantity_served INTEGER NOT NULL,
            leftover_kg REAL NOT NULL,
            reason TEXT NOT NULL,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (food_item_id) REFERENCES food_items(id)
        );
        """
    )
    db.commit()

    try:
        db.execute("ALTER TABLE bookings ADD COLUMN is_served INTEGER DEFAULT 0")
        db.commit()
    except Exception:
        pass

    seed_demo_content(db)
    db.close()


def seed_demo_content(db):
    admin_pw = generate_password_hash("admin1234")
    admin_user = db.execute("SELECT id FROM users WHERE email = ?", ("admin@pccoe.edu",)).fetchone()
    if not admin_user:
        db.execute(
            "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
            ("PCCOE Canteen Administrator", "admin@pccoe.edu", admin_pw, "admin"),
        )
    else:
        db.execute(
            "UPDATE users SET password = ?, role = 'admin' WHERE email = ?",
            (admin_pw, "admin@pccoe.edu"),
        )
    db.commit()


@app.route("/")
def home():
    db = get_db()
    counts = {
        "meals_served": db.execute("SELECT COALESCE(SUM(quantity), 0) FROM bookings WHERE status = 'confirmed' AND is_served = 1").fetchone()[0],
        "confirmed_bookings": db.execute("SELECT COALESCE(SUM(quantity), 0) FROM bookings WHERE status = 'confirmed'").fetchone()[0],
        "food_items": db.execute("SELECT COUNT(*) FROM food_items").fetchone()[0],
        "waste_saved": db.execute("SELECT COALESCE(SUM(leftover_kg), 0) FROM waste_records").fetchone()[0],
        "active_students": db.execute("SELECT COUNT(*) FROM users WHERE role = 'student'").fetchone()[0],
    }
    db.close()
    return render_template("home.html", stats=counts)


@app.route("/poster")
def dt_poster():
    return render_template("poster.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        db.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["user_role"] = user["role"]
            flash("Login successful.", "success")
            if user["role"] == "student":
                return redirect(url_for("student_dashboard"))
            if user["role"] == "staff":
                return redirect(url_for("staff_dashboard"))
            return redirect(url_for("admin_dashboard"))

        flash("Invalid email or password. Please try again.", "error")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        # Registration is strictly for students
        role = "student"

        if not name or not email or not password:
            flash("Please complete all required fields.", "error")
            return render_template("register.html")

        db = get_db()
        existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            db.close()
            flash("This email is already registered. Please log in.", "error")
            return redirect(url_for("login"))

        db.execute(
            "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
            (name, email, generate_password_hash(password), role),
        )
        db.commit()
        db.close()

        flash("Student registration successful! Please log in to pre-book meals.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))


@app.route("/dashboard")
def dashboard_redirect():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    if user["role"] == "student":
        return redirect(url_for("student_dashboard"))
    if user["role"] == "staff":
        return redirect(url_for("staff_dashboard"))
    return redirect(url_for("admin_dashboard"))


@app.route("/student", methods=["GET", "POST"])
@login_required("student")
def student_dashboard():
    user = current_user()
    db = get_db()

    if request.method == "POST":
        action = request.form.get("action")

        if action == "book":
            item_id = int(request.form.get("item_id"))
            quantity = int(request.form.get("quantity", 0))
            booking_date = request.form.get("booking_date")
            item = db.execute("SELECT * FROM food_items WHERE id = ?", (item_id,)).fetchone()

            if not item or not item["is_available"]:
                flash("This meal is not available right now.", "error")
                return redirect(url_for("student_dashboard"))
            if not booking_date:
                flash("Please choose a valid booking date.", "error")
                return redirect(url_for("student_dashboard"))
            if quantity <= 0:
                flash("Booking quantity must be at least 1.", "error")
                return redirect(url_for("student_dashboard"))

            booking_dt = datetime.strptime(booking_date, "%Y-%m-%d")
            today = datetime.now()
            if booking_dt.date() < today.date():
                flash("Past dates cannot be booked.", "error")
                return redirect(url_for("student_dashboard"))

            existing = db.execute(
                "SELECT id FROM bookings WHERE user_id = ? AND food_item_id = ? AND booking_date = ? AND status = 'confirmed'",
                (user["id"], item_id, booking_date),
            ).fetchone()
            if existing:
                flash("You already have a confirmed booking for this meal on that date.", "error")
                return redirect(url_for("student_dashboard"))

            if quantity > item["quantity_available"]:
                flash(f"Only {item['quantity_available']} portions are available for this meal.", "error")
                return redirect(url_for("student_dashboard"))

            booking_code = f"SP-{uuid.uuid4().hex[:8].upper()}"
            db.execute(
                "INSERT INTO bookings (booking_id, user_id, food_item_id, booking_date, quantity, status) VALUES (?, ?, ?, ?, ?, 'confirmed')",
                (booking_code, user["id"], item_id, booking_date, quantity),
            )
            new_quantity = max(0, item["quantity_available"] - quantity)
            db.execute(
                "UPDATE food_items SET quantity_available = ?, is_available = ? WHERE id = ?",
                (new_quantity, 1 if new_quantity > 0 else 0, item_id),
            )
            db.commit()
            flash(f"Booking confirmed! Your ID is {booking_code}.", "success")
            return redirect(url_for("student_dashboard"))

        if action == "cancel":
            booking_id = request.form.get("booking_id")
            booking = db.execute(
                "SELECT b.*, f.category, f.quantity_available FROM bookings b JOIN food_items f ON f.id = b.food_item_id WHERE b.booking_id = ? AND b.user_id = ?",
                (booking_id, user["id"]),
            ).fetchone()
            if not booking:
                flash("The selected booking could not be found.", "error")
                return redirect(url_for("student_dashboard"))
            if booking["status"] != "confirmed":
                flash("Only confirmed bookings can be cancelled.", "error")
                return redirect(url_for("student_dashboard"))

            if booking["is_served"]:
                flash("This meal has already been served and cannot be cancelled.", "error")
                return redirect(url_for("student_dashboard"))

            booking_dt = datetime.strptime(booking["booking_date"], "%Y-%m-%d").date()
            if booking_dt < date.today():
                flash("Past meal bookings cannot be cancelled.", "error")
                return redirect(url_for("student_dashboard"))

            db.execute(
                "UPDATE bookings SET status = 'cancelled' WHERE booking_id = ?",
                (booking_id,),
            )
            db.execute(
                "UPDATE food_items SET quantity_available = quantity_available + ?, is_available = 1 WHERE id = ?",
                (booking["quantity"], booking["food_item_id"]),
            )
            db.commit()
            flash("Booking cancelled successfully.", "success")
            return redirect(url_for("student_dashboard"))

        if action == "feedback":
            item_id = int(request.form.get("food_item_id"))
            rating = int(request.form.get("rating", 0))
            comment = request.form.get("comment", "").strip()
            served_date = request.form.get("served_date")

            if not served_date or rating < 1 or rating > 5:
                flash("Please provide a valid rating and served date.", "error")
                return redirect(url_for("student_dashboard"))

            db.execute(
                "INSERT INTO feedback (user_id, food_item_id, rating, comment, served_date) VALUES (?, ?, ?, ?, ?)",
                (user["id"], item_id, rating, comment, served_date),
            )
            db.commit()
            flash("Feedback submitted successfully.", "success")
            return redirect(url_for("student_dashboard"))

    menu_items = db.execute("SELECT * FROM food_items ORDER BY category, name").fetchall()
    user_bookings = db.execute(
        """
        SELECT b.*, f.name AS item_name, f.category
        FROM bookings b
        JOIN food_items f ON f.id = b.food_item_id
        WHERE b.user_id = ?
        ORDER BY b.booking_date DESC, b.created_at DESC
        """,
        (user["id"],),
    ).fetchall()

    today_bookings = [b for b in user_bookings if b["booking_date"] == date.today().isoformat() and b["status"] == "confirmed"]
    upcoming = [b for b in user_bookings if b["booking_date"] >= date.today().isoformat() and b["status"] == "confirmed"]
    history = [b for b in user_bookings if b["booking_date"] < date.today().isoformat() or b["status"] == "cancelled"]

    db.close()
    return render_template(
        "student_dashboard.html",
        menu_items=menu_items,
        today_bookings=today_bookings,
        upcoming=upcoming,
        history=history,
        user=user,
        today=date.today(),
    )


@app.route("/staff", methods=["GET", "POST"])
@login_required("staff", "admin")
def staff_dashboard():
    user = current_user()
    db = get_db()

    if request.method == "POST":
        action = request.form.get("action")

        if action == "serve_booking":
            booking_id = request.form.get("booking_id")
            db.execute("UPDATE bookings SET is_served = 1 WHERE booking_id = ?", (booking_id,))
            db.commit()
            flash(f"Order #{booking_id} marked as served! Meal handed over.", "success")
            return redirect(url_for("staff_dashboard"))

        if action == "unserve_booking":
            booking_id = request.form.get("booking_id")
            db.execute("UPDATE bookings SET is_served = 0 WHERE booking_id = ?", (booking_id,))
            db.commit()
            flash(f"Order #{booking_id} status returned to pending pickup.", "info")
            return redirect(url_for("staff_dashboard"))

        if action == "quick_stock":
            item_id = int(request.form.get("item_id", 0))
            delta = int(request.form.get("delta", 0))
            item = db.execute("SELECT quantity_available FROM food_items WHERE id = ?", (item_id,)).fetchone()
            if item:
                new_qty = max(0, item["quantity_available"] + delta)
                db.execute(
                    "UPDATE food_items SET quantity_available = ?, is_available = ? WHERE id = ?",
                    (new_qty, 1 if new_qty > 0 else 0, item_id),
                )
                db.commit()
                flash(f"Inventory portion count updated ({'+' if delta > 0 else ''}{delta}).", "success")
            return redirect(url_for("staff_dashboard"))

        if action == "add_menu_item":
            name = request.form.get("name", "").strip()
            description = request.form.get("description", "").strip()
            category = request.form.get("category")
            price = float(request.form.get("price", 0))
            quantity = int(request.form.get("quantity", 0))
            image_url = request.form.get("image_url", "").strip() or "https://images.unsplash.com/photo-1547592180-85f173990554?auto=format&fit=crop&w=900&q=80"
            is_available = 1 if request.form.get("is_available") == "on" else 0
            if not name or not category:
                flash("Meal name and category are required.", "error")
                return redirect(url_for("staff_dashboard"))
            db.execute(
                "INSERT INTO food_items (name, description, category, price, quantity_available, is_available, image_url) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (name, description, category, price, quantity, is_available, image_url),
            )
            db.commit()
            flash("Menu item added successfully.", "success")
            return redirect(url_for("staff_dashboard"))

        if action == "edit_menu_item":
            item_id = int(request.form.get("item_id"))
            db.execute(
                "UPDATE food_items SET name = ?, description = ?, category = ?, price = ?, quantity_available = ?, is_available = ? WHERE id = ?",
                (
                    request.form.get("name", "").strip(),
                    request.form.get("description", "").strip(),
                    request.form.get("category"),
                    float(request.form.get("price", 0)),
                    int(request.form.get("quantity", 0)),
                    1 if request.form.get("is_available") == "on" else 0,
                    item_id,
                ),
            )
            db.commit()
            flash("Menu item updated.", "success")
            return redirect(url_for("staff_dashboard"))

        if action == "delete_menu_item":
            item_id = int(request.form.get("item_id"))
            db.execute("DELETE FROM food_items WHERE id = ?", (item_id,))
            db.execute("DELETE FROM bookings WHERE food_item_id = ?", (item_id,))
            db.execute("DELETE FROM feedback WHERE food_item_id = ?", (item_id,))
            db.execute("DELETE FROM waste_records WHERE food_item_id = ?", (item_id,))
            db.commit()
            flash("Menu item removed.", "success")
            return redirect(url_for("staff_dashboard"))

        if action == "load_sample_menu":
            sample_items = [
                ("Poha & Chai Combo", "Traditional Maharashtrian flattened rice cooked with turmeric, onions, peanuts, and green chillies.", "breakfast", 45.0, 60, 1, "https://images.unsplash.com/photo-1631452180519-c014fe946bc7?auto=format&fit=crop&w=900&q=80"),
                ("Masala Dosa with Sambar", "Crispy fermented crepe served with lentil stew and fresh coconut chutney.", "breakfast", 65.0, 50, 1, "https://images.unsplash.com/photo-1589301760014-d929f3979dbc?auto=format&fit=crop&w=900&q=80"),
                ("PCCOE Special Veg Thali", "Nutritious lunch thali with 2 rotis, paneer sabzi, dal tadka, steamed rice, and salad.", "lunch", 100.0, 80, 1, "https://images.unsplash.com/photo-1546793665-c74683f339c1?auto=format&fit=crop&w=900&q=80"),
                ("Paneer Rice Bowl", "Fragrant jeera rice bowl topped with spiced paneer tikka gravy.", "lunch", 85.0, 55, 1, "https://images.unsplash.com/photo-1512058564366-18510be2db19?auto=format&fit=crop&w=900&q=80"),
                ("Dal Khichdi & Papad", "Comfort food of yellow lentils and rice with cumin ghee tempering.", "dinner", 75.0, 50, 1, "https://images.unsplash.com/photo-1547592166-23ac45744acd?auto=format&fit=crop&w=900&q=80"),
            ]
            db.executemany(
                "INSERT INTO food_items (name, description, category, price, quantity_available, is_available, image_url) VALUES (?, ?, ?, ?, ?, ?, ?)",
                sample_items,
            )
            db.commit()
            flash("Sample PCCOE canteen menu items loaded successfully.", "success")
            return redirect(url_for("staff_dashboard"))

        if action == "clear_all_menu":
            db.execute("DELETE FROM food_items")
            db.commit()
            flash("All menu items cleared.", "info")
            return redirect(url_for("staff_dashboard"))

        if action == "record_waste":
            item_id = int(request.form.get("food_item_id"))
            prepared = int(request.form.get("quantity_prepared", 0))
            served = int(request.form.get("quantity_served", 0))
            leftover_kg = float(request.form.get("leftover_kg", 0))
            reason = request.form.get("reason", "").strip()
            notes = request.form.get("notes", "").strip()
            waste_date = request.form.get("waste_date")

            if not waste_date or prepared <= 0 or reason == "":
                flash("Please provide a valid waste record with a reason.", "error")
                return redirect(url_for("staff_dashboard"))
            if served < 0 or leftover_kg < 0:
                flash("Waste values cannot be negative.", "error")
                return redirect(url_for("staff_dashboard"))

            db.execute(
                "INSERT INTO waste_records (date, food_item_id, quantity_prepared, quantity_served, leftover_kg, reason, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (waste_date, item_id, prepared, served, leftover_kg, reason, notes),
            )
            db.commit()
            flash("Waste record saved successfully.", "success")
            return redirect(url_for("staff_dashboard"))

    search = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "all")
    date_filter = request.args.get("date", date.today().isoformat())

    query = "SELECT b.*, u.name AS student_name, f.name AS item_name FROM bookings b JOIN users u ON u.id = b.user_id JOIN food_items f ON f.id = b.food_item_id WHERE 1=1"
    params = []
    if search:
        query += " AND (u.name LIKE ? OR f.name LIKE ? OR b.booking_id LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like, like])
    if status_filter != "all":
        query += " AND b.status = ?"
        params.append(status_filter)
    if date_filter:
        query += " AND b.booking_date = ?"
        params.append(date_filter)
    query += " ORDER BY b.booking_date DESC, b.created_at DESC"
    bookings = db.execute(query, params).fetchall()

    menu_items = db.execute("SELECT * FROM food_items ORDER BY category, name").fetchall()
    today = date.today()
    demand_rows = []
    for item in menu_items:
        avg_recent = db.execute(
            "SELECT COALESCE(AVG(quantity), 0) FROM bookings WHERE food_item_id = ? AND booking_date >= ? AND status = 'confirmed'",
            (item["id"], (today - timedelta(days=30)).isoformat()),
        ).fetchone()[0]
        confirmed_today = db.execute(
            "SELECT COALESCE(SUM(quantity), 0) FROM bookings WHERE food_item_id = ? AND booking_date = ? AND status = 'confirmed'",
            (item["id"], today.isoformat()),
        ).fetchone()[0]
        waste_avg = db.execute(
            "SELECT COALESCE(AVG((leftover_kg / NULLIF(quantity_prepared, 0)) * 100), 0) FROM waste_records WHERE food_item_id = ?",
            (item["id"],),
        ).fetchone()[0]
        popularity = db.execute(
            "SELECT COALESCE(SUM(quantity), 0) FROM bookings WHERE food_item_id = ? AND booking_date >= ? AND status = 'confirmed'",
            (item["id"], (today - timedelta(days=7)).isoformat()),
        ).fetchone()[0]

        day_adjustment = DAY_ADJUSTMENTS.get(today.weekday(), 0.0)
        historical_average = float(avg_recent or 0.0)
        recommended = max(0, round(historical_average * (1 + day_adjustment) + confirmed_today * 1.15 + (waste_avg / 100) * historical_average + (popularity * 0.1), 0))
        estimated_surplus = max(0, recommended - confirmed_today)
        demand_rows.append(
            {
                "item": item,
                "historical_average": round(historical_average, 1),
                "confirmed_today": confirmed_today,
                "day_adjustment": round(day_adjustment * 100, 1),
                "waste_avg": round(waste_avg, 1),
                "recommended": recommended,
                "potential_surplus": estimated_surplus,
            }
        )

    today_bookings = db.execute(
        "SELECT COALESCE(SUM(quantity),0) FROM bookings WHERE booking_date = ? AND status = 'confirmed'",
        (today.isoformat(),),
    ).fetchone()[0]
    total_waste = db.execute(
        "SELECT COALESCE(SUM(leftover_kg),0) FROM waste_records WHERE date = ?",
        (today.isoformat(),),
    ).fetchone()[0]
    prepared_total = db.execute(
        "SELECT COALESCE(SUM(quantity_prepared), 0) FROM waste_records WHERE date = ?",
        (today.isoformat(),),
    ).fetchone()[0]
    waste_percentage = (total_waste / prepared_total * 100) if prepared_total else 0

    db.close()
    return render_template(
        "staff_dashboard.html",
        user=user,
        bookings=bookings,
        menu_items=menu_items,
        demand_rows=demand_rows,
        today_bookings=today_bookings,
        total_waste=round(total_waste, 2),
        waste_percentage=round(waste_percentage, 2),
        search=search,
        status_filter=status_filter,
        date_filter=date_filter,
    )


@app.route("/admin", methods=["GET"])
@login_required("admin")
def admin_dashboard():
    db = get_db()
    range_value = request.args.get("range", "7")
    item_filter = request.args.get("food_item", "all")
    custom_from = request.args.get("from_date")
    custom_to = request.args.get("to_date")

    if custom_from and custom_to:
        start_date = custom_from
        end_date = custom_to
    elif range_value == "today":
        start_date = end_date = date.today().isoformat()
    elif range_value == "7":
        start_date = (date.today() - timedelta(days=6)).isoformat()
        end_date = date.today().isoformat()
    elif range_value == "30":
        start_date = (date.today() - timedelta(days=29)).isoformat()
        end_date = date.today().isoformat()
    else:
        start_date = (date.today() - timedelta(days=6)).isoformat()
        end_date = date.today().isoformat()

    query = "SELECT b.*, f.name AS item_name FROM bookings b JOIN food_items f ON f.id = b.food_item_id WHERE b.booking_date BETWEEN ? AND ? AND b.status = 'confirmed'"
    params = [start_date, end_date]
    if item_filter != "all":
        query += " AND b.food_item_id = ?"
        params.append(int(item_filter))
    bookings = db.execute(query, params).fetchall()

    waste_query = "SELECT w.*, f.name AS item_name FROM waste_records w JOIN food_items f ON f.id = w.food_item_id WHERE w.date BETWEEN ? AND ?"
    waste_params = [start_date, end_date]
    if item_filter != "all":
        waste_query += " AND w.food_item_id = ?"
        waste_params.append(int(item_filter))
    waste_records = db.execute(waste_query, waste_params).fetchall()

    total_booked = sum(b["quantity"] for b in bookings)
    total_served = sum(r["quantity_served"] for r in waste_records)
    total_waste = sum(r["leftover_kg"] for r in waste_records)
    total_prepared = sum(r["quantity_prepared"] for r in waste_records)
    waste_percentage = (total_waste / total_prepared * 100) if total_prepared else 0

    baseline_waste = 18.0
    if total_prepared:
        waste_reduction = max(0, ((baseline_waste - waste_percentage) / baseline_waste) * 100)
    else:
        waste_reduction = 0
    money_saved = total_waste * 140

    chart_dates = []
    current = datetime.strptime(start_date, "%Y-%m-%d").date()
    stop = datetime.strptime(end_date, "%Y-%m-%d").date()
    while current <= stop:
        chart_dates.append(current.isoformat())
        current += timedelta(days=1)

    waste_by_day = {day: 0 for day in chart_dates}
    orders_by_day = {day: 0 for day in chart_dates}
    prepared_by_day = {day: 0 for day in chart_dates}
    served_by_day = {day: 0 for day in chart_dates}
    for record in waste_records:
        waste_by_day[record["date"]] = waste_by_day.get(record["date"], 0) + float(record["leftover_kg"])
        prepared_by_day[record["date"]] = prepared_by_day.get(record["date"], 0) + int(record["quantity_prepared"])
        served_by_day[record["date"]] = served_by_day.get(record["date"], 0) + int(record["quantity_served"])
    for booking in bookings:
        orders_by_day[booking["booking_date"]] = orders_by_day.get(booking["booking_date"], 0) + int(booking["quantity"])

    waste_by_item = defaultdict(float)
    popularity = defaultdict(int)
    for record in waste_records:
        waste_by_item[record["item_name"]] += float(record["leftover_kg"])
    for booking in bookings:
        popularity[booking["item_name"]] += int(booking["quantity"])

    observations = []
    if waste_records:
        top_item = max(waste_by_item.items(), key=lambda entry: entry[1])
        observations.append(f"{top_item[0]} contributed the most waste, with {top_item[1]:.1f} kg left over during the selected period.")
        if waste_percentage > 18:
            observations.append("Waste percentage is above the 18% sustainability benchmark; reduce portions or improve demand forecasting.")
        else:
            observations.append("Waste is below the target benchmark. Continue the current demand-planning rhythm.")
    else:
        observations.append("No waste records are available for the selected date range. Add a few waste entries to enable analysis.")

    food_items = db.execute("SELECT id, name FROM food_items ORDER BY name").fetchall()
    db.close()

    return render_template(
        "admin_dashboard.html",
        food_items=food_items,
        current_item=item_filter,
        range_value=range_value,
        from_date=custom_from,
        to_date=custom_to,
        stats={
            "total_booked": total_booked,
            "total_served": total_served,
            "total_waste": round(total_waste, 2),
            "waste_percentage": round(waste_percentage, 2),
            "waste_reduction": round(waste_reduction, 2),
            "money_saved": round(money_saved, 2),
        },
        chart_labels=chart_dates,
        waste_by_day={k: round(v, 2) for k, v in waste_by_day.items()},
        orders_by_day={k: v for k, v in orders_by_day.items()},
        waste_by_item={k: round(v, 2) for k, v in sorted(waste_by_item.items())},
        popular_items={k: v for k, v in sorted(popularity.items())},
        prepared_by_day={k: v for k, v in prepared_by_day.items()},
        served_by_day={k: v for k, v in served_by_day.items()},
        observations=observations,
    )


@app.route("/admin/export-csv")
@login_required("admin")
def export_csv():
    db = get_db()
    range_value = request.args.get("range", "7")
    item_filter = request.args.get("food_item", "all")
    custom_from = request.args.get("from_date")
    custom_to = request.args.get("to_date")

    if custom_from and custom_to:
        start_date = custom_from
        end_date = custom_to
    elif range_value == "today":
        start_date = end_date = date.today().isoformat()
    elif range_value == "7":
        start_date = (date.today() - timedelta(days=6)).isoformat()
        end_date = date.today().isoformat()
    elif range_value == "30":
        start_date = (date.today() - timedelta(days=29)).isoformat()
        end_date = date.today().isoformat()
    else:
        start_date = (date.today() - timedelta(days=6)).isoformat()
        end_date = date.today().isoformat()

    query = "SELECT w.date, f.name AS item_name, w.quantity_prepared, w.quantity_served, w.leftover_kg, w.reason, w.notes FROM waste_records w JOIN food_items f ON f.id = w.food_item_id WHERE w.date BETWEEN ? AND ?"
    params = [start_date, end_date]
    if item_filter != "all":
        query += " AND w.food_item_id = ?"
        params.append(int(item_filter))
    query += " ORDER BY w.date DESC"
    rows = db.execute(query, params).fetchall()
    db.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Food Item", "Prepared Qty", "Served Qty", "Leftover KG", "Reason", "Notes"])
    for row in rows:
        writer.writerow([
            row["date"],
            row["item_name"],
            row["quantity_prepared"],
            row["quantity_served"],
            row["leftover_kg"],
            row["reason"],
            row["notes"],
        ])

    csv_data = output.getvalue()
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=smartplate_waste_export.csv"},
    )


@app.route("/health")
def health_check():
    return {"status": "ok"}


init_db()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
