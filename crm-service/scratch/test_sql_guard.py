import sys
import os

# Adjust path so we can import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.sql_guard import SQLGuard, SQLGuardError

def test_sql_guard():
    guard = SQLGuard()
    print("Running SQLGuard Tests...")

    # 1. Allowed selects
    print("- Testing valid select queries...")
    safe_sql = guard.validate_and_prepare("SELECT * FROM customers WHERE city = 'Delhi'")
    assert "LIMIT 1000" in safe_sql, "Should append MAX_LIMIT"
    
    # 2. Reject DML
    print("- Testing rejection of DML (INSERT/UPDATE/DELETE/DROP)...")
    for dml in [
        "INSERT INTO customers (name) VALUES ('Hacker')",
        "UPDATE customers SET name = 'Hacker'",
        "DELETE FROM customers",
        "DROP TABLE customers",
    ]:
        try:
            guard.validate_and_prepare(dml)
            raise AssertionError(f"Failed to reject: {dml}")
        except SQLGuardError:
            pass  # Expected

    # 3. Reject disallowed tables
    print("- Testing rejection of disallowed tables...")
    try:
        guard.validate_and_prepare("SELECT * FROM brand_profile")
        raise AssertionError("Failed to reject query referencing brand_profile table")
    except SQLGuardError as e:
        assert "disallowed" in str(e).lower()

    # 4. Limit appending and overrides
    print("- Testing limit additions & overrides...")
    # Add limit if missing
    sql_no_limit = "SELECT name FROM customers"
    res_no_limit = guard.validate_and_prepare(sql_no_limit)
    assert "LIMIT 1000" in res_no_limit

    # Keep small limit
    sql_small_limit = "SELECT name FROM customers LIMIT 10"
    res_small_limit = guard.validate_and_prepare(sql_small_limit)
    assert "LIMIT 10" in res_small_limit
    assert "LIMIT 1000" not in res_small_limit

    # Override large limit
    sql_large_limit = "SELECT name FROM customers LIMIT 5000"
    res_large_limit = guard.validate_and_prepare(sql_large_limit)
    assert "LIMIT 1000" in res_large_limit
    assert "5000" not in res_large_limit

    # 5. Piggyback & comment blocks
    print("- Testing block of multiple statements / comment bypasses...")
    for query in [
        "SELECT * FROM customers; DROP TABLE orders",
        "SELECT * FROM customers -- comment here",
        "SELECT * FROM customers /* comment */",
    ]:
        try:
            guard.validate_and_prepare(query)
            raise AssertionError(f"Failed to reject query with semicolon/comment: {query}")
        except SQLGuardError:
            pass

    print("ALL TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_sql_guard()
