# Notes

## The bug

Check 3 in `is_booking_possible` was only comparing the exact `check_in_date`. So if Guest A checks in May 21 for 5 nights, Guest B could happily book May 22 on the same unit — no conflict detected.

Fix: compare the full date ranges. Two bookings overlap when one starts before the other ends. I pulled this into a standalone `is_unit_available()` function since I knew the extend feature would need the same logic.

I do the overlap check in Python (loop over same-unit bookings) rather than in SQL because SQLite can't do `date + integer` arithmetic. With Postgres you'd use a single query or even a daterange exclusion constraint, but for SQLite this works fine.

## Extend stay

`PATCH /api/v1/bookings/{id}/extend` with `{"number_of_nights": 8}` (desired total).

I went with the total-based approach over a delta (`additional_nights`) for one reason: idempotency. If a client retries the same request (network glitch, double-tap), sending the desired total always produces the same outcome. A delta-based approach would keep adding nights on each retry unless you build a deduplication layer with idempotency keys.

PATCH because we're partially modifying an existing resource (just the stay duration). The endpoint rejects attempts to shorten a stay (that's a different operation) and treats "same value as current" as a no-op.

The response includes a computed `check_out_date` field — it's not stored, just derived from `check_in_date + number_of_nights`. Small touch but useful for whoever consumes this API; they shouldn't have to do date math themselves.

## Things I left alone

- Project structure, deps, Docker setup — no reason to touch these.
- Existing test style and conventions.
- The `freeze_time` markers on the original tests don't actually freeze the test data (it's built at import time), but since the tests pass correctly on relative dates I left them as-is.

## If I had more time

- DB-level locking or constraints for concurrent booking attempts.
- A listing endpoint for bookings.
- Consistent error response schema (error code + message) instead of bare detail strings.
