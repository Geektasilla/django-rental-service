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
          AND CURDATE() <= DATE_ADD(end_date, INTERVAL 90 DAY)
    ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '%s';
    END IF;
END
""" % WINDOW_MESSAGE


def create_triggers(apps, schema_editor):
    """Backstop for Review.clean()'s PAID + REVIEW_WINDOW_DAYS rule. The 90 here is hardcoded,
    not read from reviews.models.review.REVIEW_WINDOW_DAYS - triggers can't reach Python constants;
    keep the two in sync manually if that constant ever changes."""
    if schema_editor.connection.vendor == "sqlite":
        schema_editor.execute(SQLITE_INSERT)
        schema_editor.execute(SQLITE_UPDATE)
    elif schema_editor.connection.vendor == "mysql":
        schema_editor.execute(MYSQL_INSERT)
        schema_editor.execute(MYSQL_UPDATE)


def drop_triggers(apps, schema_editor):
    schema_editor.execute("DROP TRIGGER IF EXISTS review_window_check_insert")
    schema_editor.execute("DROP TRIGGER IF EXISTS review_window_check_update")


class Migration(migrations.Migration):

    dependencies = [
        ("reviews", "0001_initial"),
        ("bookings", "0006_booking_overlap_triggers"),
    ]

    operations = [
        migrations.RunPython(create_triggers, reverse_code=drop_triggers),
    ]
