from django.db import migrations

WINDOW_MESSAGE = "A review can only be left for a paid booking within 90 days of its end date."

SQLITE_INSERT = """
CREATE TRIGGER review_window_check_insert
BEFORE INSERT ON reviews_review
BEGIN
    SELECT RAISE(ABORT, '%s')
    WHERE NOT EXISTS (
        SELECT 1 FROM bookings_booking
        WHERE id = NEW.booking_id
          AND status = 'paid'
          AND date('now') >= end_date
          AND date('now') <= date(end_date, '+90 days')
    );
END;
""" % WINDOW_MESSAGE

SQLITE_UPDATE = """
CREATE TRIGGER review_window_check_update
BEFORE UPDATE ON reviews_review
BEGIN
    SELECT RAISE(ABORT, '%s')
    WHERE NOT EXISTS (
        SELECT 1 FROM bookings_booking
        WHERE id = NEW.booking_id
          AND status = 'paid'
          AND date('now') >= end_date
          AND date('now') <= date(end_date, '+90 days')
    );
END;
""" % WINDOW_MESSAGE

MYSQL_INSERT = """
CREATE TRIGGER review_window_check_insert
BEFORE INSERT ON reviews_review
FOR EACH ROW
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM bookings_booking
        WHERE id = NEW.booking_id
          AND status = 'paid'
          AND CURDATE() >= end_date
          AND CURDATE() <= DATE_ADD(end_date, INTERVAL 90 DAY)
    ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '%s';
    END IF;
END
""" % WINDOW_MESSAGE

MYSQL_UPDATE = """
CREATE TRIGGER review_window_check_update
BEFORE UPDATE ON reviews_review
FOR EACH ROW
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM bookings_booking
        WHERE id = NEW.booking_id
          AND status = 'paid'
          AND CURDATE() >= end_date
          AND CURDATE() <= DATE_ADD(end_date, INTERVAL 90 DAY)
    ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '%s';
    END IF;
END
""" % WINDOW_MESSAGE


def recreate_triggers(apps, schema_editor):
    """Add the missing lower bound (end_date must have passed) to the review window trigger
    created in 0002_review_window_trigger.py - it previously only enforced the 90-day upper
    bound, letting a review through before the booking's stay had even ended."""
    schema_editor.execute("DROP TRIGGER IF EXISTS review_window_check_insert")
    schema_editor.execute("DROP TRIGGER IF EXISTS review_window_check_update")
    if schema_editor.connection.vendor == "sqlite":
        schema_editor.execute(SQLITE_INSERT)
        schema_editor.execute(SQLITE_UPDATE)
    elif schema_editor.connection.vendor == "mysql":
        schema_editor.execute(MYSQL_INSERT)
        schema_editor.execute(MYSQL_UPDATE)


def restore_previous_triggers(apps, schema_editor):
    """Reverse migration: recreate the 0002 trigger definitions (upper bound only)."""
    schema_editor.execute("DROP TRIGGER IF EXISTS review_window_check_insert")
    schema_editor.execute("DROP TRIGGER IF EXISTS review_window_check_update")
    if schema_editor.connection.vendor == "sqlite":
        schema_editor.execute(
            """
            CREATE TRIGGER review_window_check_insert
            BEFORE INSERT ON reviews_review
            BEGIN
                SELECT RAISE(ABORT, '%s')
                WHERE NOT EXISTS (
                    SELECT 1 FROM bookings_booking
                    WHERE id = NEW.booking_id
                      AND status = 'paid'
                      AND date('now') <= date(end_date, '+90 days')
                );
            END;
            """
            % WINDOW_MESSAGE
        )
        schema_editor.execute(
            """
            CREATE TRIGGER review_window_check_update
            BEFORE UPDATE ON reviews_review
            BEGIN
                SELECT RAISE(ABORT, '%s')
                WHERE NOT EXISTS (
                    SELECT 1 FROM bookings_booking
                    WHERE id = NEW.booking_id
                      AND status = 'paid'
                      AND date('now') <= date(end_date, '+90 days')
                );
            END;
            """
            % WINDOW_MESSAGE
        )
    elif schema_editor.connection.vendor == "mysql":
        schema_editor.execute(
            """
            CREATE TRIGGER review_window_check_insert
            BEFORE INSERT ON reviews_review
            FOR EACH ROW
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM bookings_booking
                    WHERE id = NEW.booking_id
                      AND status = 'paid'
                      AND CURDATE() <= DATE_ADD(end_date, INTERVAL 90 DAY)
                ) THEN
                    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '%s';
                END IF;
            END
            """
            % WINDOW_MESSAGE
        )
        schema_editor.execute(
            """
            CREATE TRIGGER review_window_check_update
            BEFORE UPDATE ON reviews_review
            FOR EACH ROW
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM bookings_booking
                    WHERE id = NEW.booking_id
                      AND status = 'paid'
                      AND CURDATE() <= DATE_ADD(end_date, INTERVAL 90 DAY)
                ) THEN
                    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '%s';
                END IF;
            END
            """
            % WINDOW_MESSAGE
        )


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ("reviews", "0002_review_window_trigger"),
    ]

    operations = [
        migrations.RunPython(recreate_triggers, reverse_code=restore_previous_triggers),
    ]
