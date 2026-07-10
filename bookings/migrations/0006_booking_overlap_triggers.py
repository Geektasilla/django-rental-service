from django.db import migrations

OVERLAP_MESSAGE = "This property is already booked for the selected dates."

SQLITE_INSERT = """
CREATE TRIGGER booking_overlap_check_insert
BEFORE INSERT ON bookings_booking
WHEN NEW.status IN ('booked', 'paid')
BEGIN
    SELECT RAISE(ABORT, '%s')
    WHERE EXISTS (
        SELECT 1 FROM bookings_booking
        WHERE property_id = NEW.property_id
          AND status IN ('booked', 'paid')
          AND start_date < NEW.end_date
          AND end_date > NEW.start_date
    );
END;
""" % OVERLAP_MESSAGE

SQLITE_UPDATE = """
CREATE TRIGGER booking_overlap_check_update
BEFORE UPDATE ON bookings_booking
WHEN NEW.status IN ('booked', 'paid')
BEGIN
    SELECT RAISE(ABORT, '%s')
    WHERE EXISTS (
        SELECT 1 FROM bookings_booking
        WHERE property_id = NEW.property_id
          AND status IN ('booked', 'paid')
          AND id != NEW.id
          AND start_date < NEW.end_date
          AND end_date > NEW.start_date
    );
END;
""" % OVERLAP_MESSAGE

MYSQL_INSERT = """
CREATE TRIGGER booking_overlap_check_insert
BEFORE INSERT ON bookings_booking
FOR EACH ROW
BEGIN
    IF NEW.status IN ('booked', 'paid') THEN
        IF EXISTS (
            SELECT 1 FROM bookings_booking
            WHERE property_id = NEW.property_id
              AND status IN ('booked', 'paid')
              AND start_date < NEW.end_date
              AND end_date > NEW.start_date
        ) THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '%s';
        END IF;
    END IF;
END
""" % OVERLAP_MESSAGE

MYSQL_UPDATE = """
CREATE TRIGGER booking_overlap_check_update
BEFORE UPDATE ON bookings_booking
FOR EACH ROW
BEGIN
    IF NEW.status IN ('booked', 'paid') THEN
        IF EXISTS (
            SELECT 1 FROM bookings_booking
            WHERE property_id = NEW.property_id
              AND status IN ('booked', 'paid')
              AND id != NEW.id
              AND start_date < NEW.end_date
              AND end_date > NEW.start_date
        ) THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '%s';
        END IF;
    END IF;
END
""" % OVERLAP_MESSAGE


def create_triggers(apps, schema_editor):
    """Last-line-of-defense DB trigger for the overlap rule already enforced in Booking.clean() -
    bulk_create()/bulk_update()/.update() skip clean(), so this is the only thing that still
    catches them. Dialect-specific: SQLite's RAISE(ABORT, ...) vs MySQL's SIGNAL SQLSTATE."""
    if schema_editor.connection.vendor == "sqlite":
        schema_editor.execute(SQLITE_INSERT)
        schema_editor.execute(SQLITE_UPDATE)
    elif schema_editor.connection.vendor == "mysql":
        schema_editor.execute(MYSQL_INSERT)
        schema_editor.execute(MYSQL_UPDATE)


def drop_triggers(apps, schema_editor):
    schema_editor.execute("DROP TRIGGER IF EXISTS booking_overlap_check_insert")
    schema_editor.execute("DROP TRIGGER IF EXISTS booking_overlap_check_update")


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0005_booking_booking_status_valid"),
    ]

    operations = [
        migrations.RunPython(create_triggers, reverse_code=drop_triggers),
    ]
