-- 1. DQL / JOIN: bookings with customer, vehicle, service and assigned mechanic.
SELECT b.booking_id, c.full_name, v.vehicle_number, s.service_name,
       m.mechanic_name, b.service_date, b.status
FROM bookings b
JOIN customers c ON c.customer_id = b.customer_id
JOIN vehicles v ON v.vehicle_id = b.vehicle_id
JOIN services s ON s.service_id = b.service_id
LEFT JOIN mechanics m ON m.mechanic_id = b.mechanic_id
ORDER BY b.service_date DESC;

-- 2. JOIN: payments with customer and vehicle.
SELECT p.payment_id, c.full_name, v.vehicle_number, p.amount,
       p.payment_method, p.payment_status, p.payment_date
FROM payments p
JOIN bookings b ON b.booking_id = p.booking_id
JOIN customers c ON c.customer_id = p.customer_id
JOIN vehicles v ON v.vehicle_id = b.vehicle_id;

-- 3. GROUP BY + aggregate + HAVING: revenue per service with at least one booking.
SELECT s.service_name, COUNT(DISTINCT b.booking_id) AS booking_count,
       COALESCE(SUM(CASE WHEN p.payment_status = 'paid' THEN p.amount ELSE 0 END), 0) AS revenue
FROM services s
LEFT JOIN bookings b ON b.service_id = s.service_id
LEFT JOIN payments p ON p.booking_id = b.booking_id
GROUP BY s.service_id, s.service_name
HAVING COUNT(DISTINCT b.booking_id) > 0;

-- 4. Subquery: customers with more bookings than the overall customer average.
SELECT c.customer_id, c.full_name
FROM customers c
WHERE (SELECT COUNT(*) FROM bookings b WHERE b.customer_id = c.customer_id) >
      (SELECT AVG(customer_booking_count)
       FROM (SELECT COUNT(*) AS customer_booking_count
             FROM bookings GROUP BY customer_id) AS counts_by_customer);

-- 5. DQL: available mechanics.
SELECT mechanic_id, mechanic_name, specialization
FROM mechanics WHERE availability = 'available';

-- 6. View: service history report.
SELECT * FROM v_service_history ORDER BY service_date DESC;

-- 7. Stored procedure: booking counts for one customer.
CALL sp_customer_booking_summary(1, NULL, NULL);

-- 8. Stored function: service price plus assigned spare-part prices.
SELECT fn_booking_total(1) AS booking_total;

-- 9. DML: insert a payment for an existing booking; commit as one transaction.
BEGIN;
INSERT INTO payments (booking_id, customer_id, amount, payment_method, payment_status)
SELECT booking_id, customer_id, fn_booking_total(booking_id), 'cash', 'paid'
FROM bookings WHERE booking_id = 1;
COMMIT;

-- 10. DML: assign an available mechanic to a booking.
UPDATE bookings
SET mechanic_id = (SELECT mechanic_id FROM mechanics
                   WHERE availability = 'available' ORDER BY mechanic_id LIMIT 1)
WHERE booking_id = 1;
