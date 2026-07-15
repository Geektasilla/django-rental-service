from django.db import migrations

LIMIT_MESSAGE = "A property cannot have more than 10 images."

SQLITE_INSERT = """
CREATE TRIGGER property_image_limit_check
BEFORE INSERT ON listings_propertyimage
BEGIN
    SELECT RAISE(ABORT, '%s')
    WHERE (SELECT COUNT(*) FROM listings_propertyimage WHERE property_id = NEW.property_id) >= 10;
END;
""" % LIMIT_MESSAGE

MYSQL_INSERT = """
CREATE TRIGGER property_image_limit_check
BEFORE INSERT ON listings_propertyimage
FOR EACH ROW
BEGIN
    IF (SELECT COUNT(*) FROM listings_propertyimage WHERE property_id = NEW.property_id) >= 10 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '%s';
    END IF;
END
""" % LIMIT_MESSAGE


def create_trigger(apps, schema_editor):
    """Backstop for PropertyImage.clean()'s settings.MAX_PROPERTY_IMAGES limit. The 10 here is
    hardcoded, not read from settings - triggers can't reach Python settings; keep the two in
    sync manually if MAX_PROPERTY_IMAGES ever changes."""
    if schema_editor.connection.vendor == "sqlite":
        schema_editor.execute(SQLITE_INSERT)
    elif schema_editor.connection.vendor == "mysql":
        schema_editor.execute(MYSQL_INSERT)


def drop_trigger(apps, schema_editor):
    schema_editor.execute("DROP TRIGGER IF EXISTS property_image_limit_check")


class Migration(migrations.Migration):

    dependencies = [
        ("listings", "0006_property_agent_cert_trigger"),
    ]

    operations = [
        migrations.RunPython(create_trigger, reverse_code=drop_trigger),
    ]
