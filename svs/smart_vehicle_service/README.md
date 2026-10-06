# Smart Vehicle Service Management System

A beginner-friendly vehicle service booking application built with Flask, PostgreSQL, HTML, CSS and JavaScript.

## Features

- Customer registration/login and administrator login with password hashing.
- Customers manage their own vehicles, make service bookings, view status, history and payments.
- Administrators manage customers, mechanics, services, spare parts, booking status, payments and reports.
- Booking creation is transactional. Selected parts are reserved in the same transaction; database triggers check and update stock.
- Completing or cancelling a booking writes a service-history record through a trigger.
- PostgreSQL schema includes relational constraints, sample data, a view, stored procedure, function and triggers.

## Project files

- `app.py` — Flask routes and request handling.
- `database.py` — PostgreSQL connection configuration read from environment variables.
- `schema.sql` — tables, constraints, DBMS objects and sample records.
- `queries.sql` — example DQL, DML, JOIN, GROUP BY, HAVING, subquery, view, procedure, function and transaction queries.
- `templates/` — server-rendered HTML pages.
- `static/` — responsive CSS and browser-side form validation.

## Requirements

- Python 3.10 or newer.
- PostgreSQL 12 or newer.
- pgAdmin 4 for creating and managing the database (included with many PostgreSQL installers).
- VS Code with the Python extension is recommended.

## Create the PostgreSQL database in pgAdmin

1. Install PostgreSQL for Windows if you do not already have the PostgreSQL server. pgAdmin is a management tool and does not itself run the database server.
2. Open pgAdmin and connect to your PostgreSQL server. During installation, PostgreSQL usually creates the `postgres` administrator account; use the password you chose.
3. In the left Browser panel, right-click **Databases** → **Create** → **Database...**.
4. Enter `smart_vehicle_service` as the database name. Set the owner to your PostgreSQL user (often `postgres`), then click **Save**.
5. Select the new `smart_vehicle_service` database. Open **Tools** → **Query Tool**.
6. In Query Tool, open `schema.sql` using the folder/open-file button, then execute the script with the lightning-bolt **Execute** button (or press F5). It creates the tables, constraints, demo records, view, procedure, function and triggers inside the selected database.
7. To confirm, expand **Schemas** → **public** → **Tables** and refresh the tree.

The script does not create the database itself: create and select the database in pgAdmin first, then run `schema.sql`. To inspect or try the demonstration queries later, open `queries.sql` in Query Tool. The file contains write queries too; run only against a development database and review the sample IDs before executing.

Demo logins:

- Admin: username `admin`, password `admin123`
- Customer: email `demo@example.com`, password `Customer123!`

Change these demonstration credentials before using the project outside a local demo.

## Install and run in VS Code (Windows PowerShell)

1. Open the `smart_vehicle_service` folder in VS Code.
2. Create and activate a virtual environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Install Python dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

4. Set the PostgreSQL connection and Flask secret for the current terminal. Replace the password with your PostgreSQL user's password:

   ```powershell
   $env:DB_HOST = "127.0.0.1"
   $env:DB_PORT = "5432"
   $env:DB_USER = "postgres"
   $env:DB_PASSWORD = "your_postgresql_password"
   $env:DB_NAME = "smart_vehicle_service"
   $env:SECRET_KEY = "replace-with-a-long-random-secret"
   ```

   These values must match the server/role/database in pgAdmin. The app reads credentials from environment variables and does not save the database password in source code.
5. Start Flask:

   ```powershell
   python app.py
   ```

6. Open `http://127.0.0.1:5000` in a browser.

To generate a suitable Flask secret, run `python -c "import secrets; print(secrets.token_hex(32))"` and use its output as `SECRET_KEY`.

## Validation and DBMS notes

- Required fields, password confirmation, password length, positive payment amounts, nonnegative costs/stock, vehicle years and enumerated states are checked in forms and/or PostgreSQL constraints.
- Candidate keys include customer email/phone, vehicle number, mechanic phone, service name and admin username. Primary keys identify rows; foreign keys enforce parent-child relationships.
- `booking_parts` has a composite primary key `(booking_id, part_id)` and references bookings and spare parts.
- Service history appears when an administrator changes a booking to `completed` or `cancelled`.
- PostgreSQL uses `GENERATED ... AS IDENTITY`, `ON CONFLICT`, PL/pgSQL trigger functions and `CHECK` constraints in place of MySQL-specific syntax.

## DBMS viva questions and answers

1. **What is a DBMS?**  
   Software that stores, organizes, retrieves and controls access to data. PostgreSQL is the DBMS used here.
2. **What is a primary key?**  
   A column or column set that uniquely identifies each row and cannot be NULL, such as `customers.customer_id`.
3. **What is a candidate key?**  
   A minimal attribute set that can uniquely identify a row. Customer email and phone are candidate keys; this schema enforces both as `UNIQUE`.
4. **Why are foreign keys used?**  
   To enforce referential integrity. For example, each booking points to an existing customer, vehicle and service.
5. **What is normalization?**  
   Structuring data to reduce duplication and update anomalies. Customer, vehicle, service, mechanic and booking facts are kept in separate related tables.
6. **What does a JOIN do?**  
   It combines related rows from tables. Booking pages join bookings to customers, vehicles, services and mechanics.
7. **What is GROUP BY used for?**  
   It groups rows so aggregates such as `COUNT` and `SUM` can be calculated per service or customer.
8. **How does HAVING differ from WHERE?**  
   `WHERE` filters rows before grouping; `HAVING` filters grouped aggregate results.
9. **What is a subquery?**  
   A query nested inside another query, such as finding customers whose booking count is above the average.
10. **What is a view?**  
    A stored query exposed like a virtual table. `v_service_history` presents joined service-history details.
11. **What is a stored procedure?**  
    A named SQL program invoked with `CALL`. `sp_customer_booking_summary` returns booking counts for one customer.
12. **What is a stored function?**  
    A stored SQL routine that returns a value. `fn_booking_total` calculates service cost plus selected part costs.
13. **What is a trigger?**  
    A database routine that runs automatically for a table event. Triggers in this project enforce spare-part stock handling and maintain history.
14. **What is a transaction?**  
    A sequence of operations treated as one unit. Booking and part reservation commit together or roll back together.
15. **What does ACID mean?**  
    Atomicity, Consistency, Isolation and Durability—the core properties expected of reliable transactions.
16. **What is DDL, DML and DQL?**  
    DDL defines structures (`CREATE`), DML modifies rows (`INSERT`, `UPDATE`, `DELETE`), and DQL retrieves rows (`SELECT`).
17. **Why hash passwords?**  
    A one-way password hash prevents the database from storing readable passwords. Flask Werkzeug generates and verifies the hashes.
18. **Why is `booking_parts` a separate table?**  
    A booking can use many parts and each part can belong to many bookings; the table resolves this many-to-many relationship.
