"""Flask application for the Smart Vehicle Service Management System."""

import os
from datetime import date
from functools import wraps

import psycopg
from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database import get_connection

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
if not app.config["SECRET_KEY"]:
    raise RuntimeError("Set a strong SECRET_KEY environment variable before running Flask.")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("role") != "admin":
            flash("Administrator access is required.", "error")
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)

    return wrapped


def customer_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("role") != "customer":
            flash("Please log in with a customer account to continue.", "error")
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)

    return wrapped


def fetch_all(sql, params=()):
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(sql, params)
        return cursor.fetchall()
    finally:
        connection.close()


def fetch_one(sql, params=()):
    rows = fetch_all(sql, params)
    return rows[0] if rows else None


def execute(sql, params=()):
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(sql, params)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def render_database_error(error):
    app.logger.exception("Database operation failed: %s", error)
    flash("The database request failed. Check the form values and database connection.", "error")


@app.context_processor
def template_context():
    return {
        "current_user": session.get("display_name"),
        "user_role": session.get("role"),
        "now_date": date.today().isoformat(),
    }


@app.route("/")
def index():
    return redirect(url_for("dashboard") if session.get("user_id") else url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        account_type = request.form.get("account_type", "customer")
        try:
            if account_type == "admin":
                account = fetch_one(
                    "SELECT admin_id, username, password_hash FROM admin WHERE username = %s",
                    (username,),
                )
                if account and check_password_hash(account["password_hash"], password):
                    session.clear()
                    session.update(
                        user_id=account["admin_id"],
                        display_name=account["username"],
                        role="admin",
                    )
                    return redirect(url_for("dashboard"))
            else:
                account = fetch_one(
                    "SELECT customer_id, full_name, email, password_hash FROM customers WHERE email = %s",
                    (username.lower(),),
                )
                if account and check_password_hash(account["password_hash"], password):
                    session.clear()
                    session.update(
                        user_id=account["customer_id"],
                        display_name=account["full_name"],
                        email=account["email"],
                        role="customer",
                    )
                    return redirect(url_for("dashboard"))
            flash("The username/email or password was not recognized.", "error")
        except (psycopg.Error, RuntimeError) as error:
            render_database_error(error)
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if not full_name or not email or not phone or len(password) < 8:
            flash("Complete all fields. Passwords must contain at least 8 characters.", "error")
        elif password != confirm:
            flash("The passwords do not match.", "error")
        else:
            try:
                execute(
                    "INSERT INTO customers (full_name, email, phone, password_hash) VALUES (%s, %s, %s, %s)",
                    (full_name, email, phone, generate_password_hash(password)),
                )
                flash("Registration successful. You can now log in.", "success")
                return redirect(url_for("login"))
            except psycopg.IntegrityError:
                flash("That email address or phone number is already registered.", "error")
            except (psycopg.Error, RuntimeError) as error:
                render_database_error(error)
    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    try:
        if session["role"] == "admin":
            stats = fetch_one(
                """SELECT
                    (SELECT COUNT(*) FROM customers) AS customers,
                    (SELECT COUNT(*) FROM vehicles) AS vehicles,
                    (SELECT COUNT(*) FROM bookings) AS bookings,
                    (SELECT COUNT(*) FROM mechanics) AS mechanics"""
            )
            recent = fetch_all(
                """SELECT b.booking_id, c.full_name, v.vehicle_number, s.service_name,
                          b.service_date, b.status
                   FROM bookings b
                   JOIN customers c ON c.customer_id = b.customer_id
                   JOIN vehicles v ON v.vehicle_id = b.vehicle_id
                   JOIN services s ON s.service_id = b.service_id
                   ORDER BY b.booking_date DESC LIMIT 8"""
            )
        else:
            stats = fetch_one(
                """SELECT
                    (SELECT COUNT(*) FROM vehicles WHERE customer_id = %s) AS vehicles,
                    (SELECT COUNT(*) FROM bookings WHERE customer_id = %s) AS bookings,
                    (SELECT COUNT(*) FROM bookings
                     WHERE customer_id = %s AND status = 'completed') AS completed""",
                (session["user_id"], session["user_id"], session["user_id"]),
            )
            recent = fetch_all(
                """SELECT b.booking_id, v.vehicle_number, s.service_name,
                          b.service_date, b.status
                   FROM bookings b
                   JOIN vehicles v ON v.vehicle_id = b.vehicle_id
                   JOIN services s ON s.service_id = b.service_id
                   WHERE b.customer_id = %s
                   ORDER BY b.booking_date DESC LIMIT 8""",
                (session["user_id"],),
            )
        return render_template("dashboard.html", stats=stats, recent=recent)
    except (psycopg.Error, RuntimeError) as error:
        render_database_error(error)
        return render_template("dashboard.html", stats={}, recent=[])


@app.route("/customers")
@login_required
@admin_required
def customers():
    try:
        rows = fetch_all(
            """SELECT c.customer_id, c.full_name, c.email, c.phone, c.created_at,
                      COUNT(DISTINCT v.vehicle_id) AS vehicle_count,
                      COUNT(DISTINCT b.booking_id) AS booking_count
               FROM customers c
               LEFT JOIN vehicles v ON v.customer_id = c.customer_id
               LEFT JOIN bookings b ON b.customer_id = c.customer_id
               GROUP BY c.customer_id
               ORDER BY c.full_name"""
        )
        return render_template("customers.html", customers=rows)
    except (psycopg.Error, RuntimeError) as error:
        render_database_error(error)
        return render_template("customers.html", customers=[])


@app.route("/vehicles", methods=["GET", "POST"])
@login_required
def vehicles():
    if request.method == "POST":
        try:
            vehicle_number = request.form.get("vehicle_number", "").strip().upper()
            vehicle_type = request.form.get("vehicle_type", "").strip()
            brand = request.form.get("brand", "").strip()
            model = request.form.get("model", "").strip()
            year = request.form.get("manufacturing_year", type=int)

            if not vehicle_number or not vehicle_type or not brand or not model:
                raise ValueError("Vehicle number, type, brand and model are required.")
            if year is None or year < 1886 or year > 2100:
                raise ValueError("Enter a manufacturing year between 1886 and 2100.")

            execute(
                """INSERT INTO vehicles
                   (customer_id, vehicle_number, vehicle_type, brand, model, manufacturing_year)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (
                    session["user_id"],
                    vehicle_number,
                    vehicle_type,
                    brand,
                    model,
                    year,
                ),
            )
            flash("Vehicle added successfully.", "success")
            return redirect(url_for("vehicles"))
        except psycopg.IntegrityError:
            flash("That vehicle number is already registered.", "error")
        except ValueError as error:
            flash(str(error), "error")
        except (psycopg.Error, RuntimeError) as error:
            render_database_error(error)

    try:
        if session["role"] == "admin":
            rows = fetch_all(
                """SELECT v.*, c.full_name AS customer_name
                   FROM vehicles v
                   JOIN customers c ON c.customer_id = v.customer_id
                   ORDER BY v.vehicle_number"""
            )
        else:
            rows = fetch_all(
                "SELECT * FROM vehicles WHERE customer_id = %s ORDER BY vehicle_number",
                (session["user_id"],),
            )
        return render_template("vehicles.html", vehicles=rows)
    except (psycopg.Error, RuntimeError) as error:
        render_database_error(error)
        return render_template("vehicles.html", vehicles=[])


@app.route("/book-service", methods=["GET", "POST"])
@login_required
@customer_required
def book_service():
    if request.method == "POST":
        connection = None
        try:
            vehicle_id = request.form.get("vehicle_id", type=int)
            service_id = request.form.get("service_id", type=int)

            mechanic_value = request.form.get("mechanic_id", "").strip()
            mechanic_id = int(mechanic_value) if mechanic_value else None

            service_date = request.form.get("service_date", "")
            problem = request.form.get("problem_description", "").strip()

            part_value = request.form.get("part_id", "").strip()
            part_id = int(part_value) if part_value else None

            try:
                part_quantity = int(request.form.get("part_quantity", "1"))
                selected_date = date.fromisoformat(service_date)
            except ValueError as error:
                raise ValueError(
                    "Enter a valid service date and whole-number part quantity."
                ) from error

            if not vehicle_id or not service_id or not service_date or part_quantity < 1:
                raise ValueError(
                    "Select a vehicle, service and date, and use a positive part quantity."
                )

            if selected_date < date.today():
                raise ValueError("The preferred service date cannot be in the past.")

            connection = get_connection()
            cursor = connection.cursor()

            cursor.execute(
                """INSERT INTO bookings
                   (customer_id, vehicle_id, service_id, mechanic_id,
                    service_date, problem_description)
                   SELECT %s, v.vehicle_id, %s, %s, %s, %s
                   FROM vehicles v
                   WHERE v.vehicle_id = %s AND v.customer_id = %s
                   RETURNING booking_id""",
                (
                    session["user_id"],
                    service_id,
                    mechanic_id,
                    service_date,
                    problem,
                    vehicle_id,
                    session["user_id"],
                ),
            )

            if cursor.rowcount != 1:
                raise ValueError("The selected vehicle does not belong to your account.")

            booking_id = cursor.fetchone()["booking_id"]

            if part_id is not None:
                cursor.execute(
                    """INSERT INTO booking_parts
                       (booking_id, part_id, quantity)
                       VALUES (%s, %s, %s)""",
                    (booking_id, part_id, part_quantity),
                )

            connection.commit()
            flash("Service booking created successfully.", "success")
            return redirect(url_for("bookings"))

        except ValueError as error:
            if connection:
                connection.rollback()
            flash(str(error), "error")

        except (psycopg.Error, RuntimeError) as error:
            if connection:
                connection.rollback()
            render_database_error(error)

        finally:
            if connection:
                connection.close()

    try:
        vehicles_list = fetch_all(
            """SELECT vehicle_id, vehicle_number, brand, model
               FROM vehicles
               WHERE customer_id = %s
               ORDER BY vehicle_number""",
            (session["user_id"],),
        )

        service_list = fetch_all(
            "SELECT service_id, service_name, service_cost FROM services ORDER BY service_name"
        )

        mechanics_list = fetch_all(
            """SELECT mechanic_id, mechanic_name, specialization
               FROM mechanics
               WHERE availability = 'available'
               ORDER BY mechanic_name"""
        )

        parts = fetch_all(
            """SELECT part_id, part_name, quantity, price
               FROM spare_parts
               WHERE quantity > 0
               ORDER BY part_name"""
        )

        return render_template(
            "bookings.html",
            bookings=[],
            form_mode=True,
            vehicles=vehicles_list,
            services=service_list,
            mechanics=mechanics_list,
            parts=parts,
        )

    except (psycopg.Error, RuntimeError) as error:
        render_database_error(error)
        return render_template(
            "bookings.html",
            bookings=[],
            form_mode=True,
            vehicles=[],
            services=[],
            mechanics=[],
            parts=[],
        )


@app.route("/bookings", methods=["GET", "POST"])
@login_required
def bookings():
    if request.method == "POST":
        if session["role"] != "admin":
            flash("Only administrators can update booking status.", "error")
            return redirect(url_for("bookings"))

        status = request.form.get("status", "")
        booking_id = request.form.get("booking_id", type=int)

        if status not in {
            "pending",
            "confirmed",
            "in_progress",
            "completed",
            "cancelled",
        }:
            flash("Choose a valid booking status.", "error")
        elif not booking_id:
            flash("Invalid booking ID.", "error")
        else:
            try:
                # 1. Update booking status
                execute(
                    "UPDATE bookings SET status = %s WHERE booking_id = %s",
                    (status, booking_id),
                )

                # 2. Automatically create service history when
                # the booking becomes completed or cancelled.
                if status in {"completed", "cancelled"}:
                    execute(
                        """INSERT INTO service_history
                               (booking_id, service_date, cost, status)
                           SELECT
                               b.booking_id,
                               b.service_date,
                               s.service_cost,
                               b.status
                           FROM bookings b
                           JOIN services s ON s.service_id = b.service_id
                           WHERE b.booking_id = %s
                             AND NOT EXISTS (
                                 SELECT 1
                                 FROM service_history h
                                 WHERE h.booking_id = b.booking_id
                             )""",
                        (booking_id,),
                    )

                flash("Booking status updated successfully.", "success")
                return redirect(url_for("bookings"))

            except (psycopg.Error, RuntimeError) as error:
                render_database_error(error)

    try:
        where = "" if session["role"] == "admin" else "WHERE b.customer_id = %s"
        params = () if session["role"] == "admin" else (session["user_id"],)

        rows = fetch_all(
            f"""SELECT b.*, c.full_name AS customer_name,
                       v.vehicle_number, s.service_name,
                       m.mechanic_name
                FROM bookings b
                JOIN customers c ON c.customer_id = b.customer_id
                JOIN vehicles v ON v.vehicle_id = b.vehicle_id
                JOIN services s ON s.service_id = b.service_id
                LEFT JOIN mechanics m ON m.mechanic_id = b.mechanic_id
                {where}
                ORDER BY b.service_date DESC""",
            params,
        )

        return render_template(
            "bookings.html",
            bookings=rows,
            form_mode=False,
        )

    except (psycopg.Error, RuntimeError) as error:
        render_database_error(error)
        return render_template(
            "bookings.html",
            bookings=[],
            form_mode=False,
        )


@app.route("/mechanics", methods=["GET", "POST"])
@login_required
@admin_required
def mechanics():
    if request.method == "POST":
        action = request.form.get("action", "add")

        try:
            if action == "availability":
                availability = request.form.get("availability", "")

                if availability not in {
                    "available",
                    "busy",
                    "unavailable",
                }:
                    raise ValueError("Choose a valid availability status.")

                execute(
                    "UPDATE mechanics SET availability = %s WHERE mechanic_id = %s",
                    (
                        availability,
                        request.form.get("mechanic_id", type=int),
                    ),
                )

                flash("Mechanic availability updated.", "success")

            else:
                mechanic_name = request.form.get("mechanic_name", "").strip()
                phone = request.form.get("phone", "").strip()
                specialization = request.form.get("specialization", "").strip()
                availability = request.form.get(
                    "availability",
                    "available",
                )

                if not mechanic_name or not phone or not specialization:
                    raise ValueError(
                        "Name, phone and specialization are required."
                    )

                if availability not in {
                    "available",
                    "busy",
                    "unavailable",
                }:
                    raise ValueError("Choose a valid availability status.")

                execute(
                    """INSERT INTO mechanics
                       (mechanic_name, phone, specialization, availability)
                       VALUES (%s, %s, %s, %s)""",
                    (
                        mechanic_name,
                        phone,
                        specialization,
                        availability,
                    ),
                )

                flash("Mechanic added successfully.", "success")

            return redirect(url_for("mechanics"))

        except ValueError as error:
            flash(str(error), "error")

        except (psycopg.Error, RuntimeError) as error:
            render_database_error(error)

    try:
        return render_template(
            "mechanics.html",
            mechanics=fetch_all(
                "SELECT * FROM mechanics ORDER BY mechanic_name"
            ),
        )

    except (psycopg.Error, RuntimeError) as error:
        render_database_error(error)
        return render_template(
            "mechanics.html",
            mechanics=[],
        )


@app.route("/services", methods=["GET", "POST"])
@login_required
def services():
    if request.method == "POST":
        if session["role"] != "admin":
            flash("Only administrators can add services.", "error")
        else:
            try:
                cost = request.form.get("service_cost", type=float)
                service_name = request.form.get("service_name", "").strip()
                description = request.form.get("description", "").strip()

                if not service_name or not description:
                    raise ValueError(
                        "Service name and description are required."
                    )

                if cost is None or cost < 0:
                    raise ValueError(
                        "Service cost must be zero or greater."
                    )

                execute(
                    """INSERT INTO services
                       (service_name, description, service_cost)
                       VALUES (%s, %s, %s)""",
                    (
                        service_name,
                        description,
                        cost,
                    ),
                )

                flash("Service added successfully.", "success")
                return redirect(url_for("services"))

            except ValueError as error:
                flash(str(error), "error")

            except psycopg.IntegrityError:
                flash(
                    "A service with that name already exists.",
                    "error",
                )

            except (psycopg.Error, RuntimeError) as error:
                render_database_error(error)

    try:
        rows = fetch_all(
            "SELECT * FROM services ORDER BY service_name"
        )
        return render_template(
            "services.html",
            services=rows,
        )

    except (psycopg.Error, RuntimeError) as error:
        render_database_error(error)
        return render_template(
            "services.html",
            services=[],
        )


@app.route("/spare-parts", methods=["GET", "POST"])
@login_required
@admin_required
def spare_parts():
    if request.method == "POST":
        try:
            quantity = request.form.get("quantity", type=int)
            price = request.form.get("price", type=float)
            part_name = request.form.get("part_name", "").strip()

            if not part_name:
                raise ValueError("Part name is required.")

            if quantity is None or quantity < 0:
                raise ValueError("Quantity must be zero or greater.")

            if price is None or price < 0:
                raise ValueError("Price must be zero or greater.")

            # Your current spare_parts table has:
            # part_id, part_name, quantity, price
            # and does NOT have a supplier column.
            execute(
                """INSERT INTO spare_parts
                   (part_name, quantity, price)
                   VALUES (%s, %s, %s)""",
                (
                    part_name,
                    quantity,
                    price,
                ),
            )

            flash("Spare part added successfully.", "success")
            return redirect(url_for("spare_parts"))

        except ValueError as error:
            flash(str(error), "error")

        except (psycopg.Error, RuntimeError) as error:
            render_database_error(error)

    try:
        return render_template(
            "spare_parts.html",
            parts=fetch_all(
                "SELECT * FROM spare_parts ORDER BY part_name"
            ),
        )

    except (psycopg.Error, RuntimeError) as error:
        render_database_error(error)
        return render_template(
            "spare_parts.html",
            parts=[],
        )


@app.route("/payments", methods=["GET", "POST"])
@login_required
def payments():
    if request.method == "POST":
        try:
            booking_id = request.form.get("booking_id", type=int)
            amount = request.form.get("amount", type=float)

            if not booking_id or amount is None or amount <= 0:
                raise ValueError(
                    "Select a booking and enter a payment amount greater than zero."
                )

            payment_method = request.form.get(
                "payment_method",
                "",
            )

            if payment_method not in {
                "cash",
                "card",
                "upi",
                "bank_transfer",
            }:
                raise ValueError("Choose a valid payment method.")

            connection = get_connection()

            try:
                cursor = connection.cursor()

                cursor.execute(
                    """INSERT INTO payments
                       (booking_id, customer_id, amount,
                        payment_method, payment_status)
                       SELECT
                           b.booking_id,
                           b.customer_id,
                           %s,
                           %s,
                           'paid'
                       FROM bookings b
                       WHERE b.booking_id = %s
                         AND (%s = 'admin'
                              OR b.customer_id = %s)""",
                    (
                        amount,
                        payment_method,
                        booking_id,
                        session["role"],
                        session["user_id"],
                    ),
                )

                if cursor.rowcount != 1:
                    raise ValueError(
                        "The selected booking could not be found for your account."
                    )

                connection.commit()

            except Exception:
                connection.rollback()
                raise

            finally:
                connection.close()

            flash("Payment recorded successfully.", "success")
            return redirect(url_for("payments"))

        except ValueError as error:
            flash(str(error), "error")

        except (psycopg.Error, RuntimeError) as error:
            render_database_error(error)

    try:
        if session["role"] == "admin":
            rows = fetch_all(
                """SELECT p.*, c.full_name,
                          b.booking_id, v.vehicle_number
                   FROM payments p
                   JOIN customers c ON c.customer_id = p.customer_id
                   JOIN bookings b ON b.booking_id = p.booking_id
                   JOIN vehicles v ON v.vehicle_id = b.vehicle_id
                   ORDER BY p.payment_date DESC"""
            )

            eligible = fetch_all(
                """SELECT b.booking_id, c.full_name,
                          v.vehicle_number, s.service_cost
                   FROM bookings b
                   JOIN customers c ON c.customer_id = b.customer_id
                   JOIN vehicles v ON v.vehicle_id = b.vehicle_id
                   JOIN services s ON s.service_id = b.service_id
                   ORDER BY b.booking_id DESC"""
            )

        else:
            rows = fetch_all(
                """SELECT p.*, b.booking_id, v.vehicle_number
                   FROM payments p
                   JOIN bookings b ON b.booking_id = p.booking_id
                   JOIN vehicles v ON v.vehicle_id = b.vehicle_id
                   WHERE p.customer_id = %s
                   ORDER BY p.payment_date DESC""",
                (session["user_id"],),
            )

            eligible = fetch_all(
                """SELECT b.booking_id, v.vehicle_number,
                          s.service_cost
                   FROM bookings b
                   JOIN vehicles v ON v.vehicle_id = b.vehicle_id
                   JOIN services s ON s.service_id = b.service_id
                   WHERE b.customer_id = %s
                   ORDER BY b.booking_id DESC""",
                (session["user_id"],),
            )

        return render_template(
            "payments.html",
            payments=rows,
            bookings=eligible,
        )

    except (psycopg.Error, RuntimeError) as error:
        render_database_error(error)
        return render_template(
            "payments.html",
            payments=[],
            bookings=[],
        )


@app.route("/service-history")
@login_required
def service_history():
    try:
        where = (
            ""
            if session["role"] == "admin"
            else "WHERE c.customer_id = %s"
        )

        params = (
            ()
            if session["role"] == "admin"
            else (session["user_id"],)
        )

        rows = fetch_all(
            f"""SELECT v.vehicle_number,
                       s.service_name AS service_performed,
                       h.service_date,
                       m.mechanic_name,
                       h.cost,
                       h.status,
                       c.full_name AS customer_name
                FROM service_history h
                JOIN bookings b ON b.booking_id = h.booking_id
                JOIN customers c ON c.customer_id = b.customer_id
                JOIN vehicles v ON v.vehicle_id = b.vehicle_id
                JOIN services s ON s.service_id = b.service_id
                LEFT JOIN mechanics m ON m.mechanic_id = b.mechanic_id
                {where}
                ORDER BY h.service_date DESC""",
            params,
        )

        return render_template(
            "history.html",
            history=rows,
        )

    except (psycopg.Error, RuntimeError) as error:
        render_database_error(error)
        return render_template(
            "history.html",
            history=[],
        )


@app.route("/reports")
@login_required
@admin_required
def reports():
    try:
        summary = fetch_all(
            """SELECT s.service_name,
                      COUNT(DISTINCT b.booking_id) AS booking_count,
                      COALESCE(SUM(p.amount), 0) AS revenue
               FROM services s
               LEFT JOIN bookings b ON b.service_id = s.service_id
               LEFT JOIN payments p
                 ON p.booking_id = b.booking_id
                AND p.payment_status = 'paid'
               GROUP BY s.service_id, s.service_name
               ORDER BY revenue DESC, s.service_name"""
        )

        totals = fetch_one(
            """SELECT COUNT(*) AS booking_count,
                      COALESCE(
                          SUM(
                              CASE
                                  WHEN status = 'completed' THEN 1
                                  ELSE 0
                              END
                          ),
                          0
                      ) AS completed_count,
                      COALESCE(
                          (
                              SELECT SUM(amount)
                              FROM payments
                              WHERE payment_status = 'paid'
                          ),
                          0
                      ) AS revenue
               FROM bookings"""
        )

        return render_template(
            "reports.html",
            summary=summary,
            totals=totals,
        )

    except (psycopg.Error, RuntimeError) as error:
        render_database_error(error)
        return render_template(
            "reports.html",
            summary=[],
            totals={},
        )


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "0") == "1")
