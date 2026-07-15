from django.db import migrations

CERT_MESSAGE = "Only a certified agent may list a property on a clients behalf."

SQLITE_INSERT = """
CREATE TRIGGER property_agent_cert_check_insert
BEFORE INSERT ON listings_property
WHEN NEW.listed_as = 'agent'
BEGIN
    SELECT RAISE(ABORT, '%s')
    WHERE NOT EXISTS (
        SELECT 1 FROM users_user u
        JOIN users_agentprofile ap ON ap.user_id = u.id
        WHERE u.id = NEW.owner_id
          AND u.is_agent = 1
          AND ap.is_certified = 1
    );
END;
""" % CERT_MESSAGE

SQLITE_UPDATE = """
CREATE TRIGGER property_agent_cert_check_update
BEFORE UPDATE ON listings_property
WHEN NEW.listed_as = 'agent'
BEGIN
    SELECT RAISE(ABORT, '%s')
    WHERE NOT EXISTS (
        SELECT 1 FROM users_user u
        JOIN users_agentprofile ap ON ap.user_id = u.id
        WHERE u.id = NEW.owner_id
          AND u.is_agent = 1
          AND ap.is_certified = 1
    );
END;
""" % CERT_MESSAGE

MYSQL_INSERT = """
CREATE TRIGGER property_agent_cert_check_insert
BEFORE INSERT ON listings_property
FOR EACH ROW
BEGIN
    IF NEW.listed_as = 'agent' THEN
        IF NOT EXISTS (
            SELECT 1 FROM users_user u
            JOIN users_agentprofile ap ON ap.user_id = u.id
            WHERE u.id = NEW.owner_id
              AND u.is_agent = 1
              AND ap.is_certified = 1
        ) THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '%s';
        END IF;
    END IF;
END
""" % CERT_MESSAGE

MYSQL_UPDATE = """
CREATE TRIGGER property_agent_cert_check_update
BEFORE UPDATE ON listings_property
FOR EACH ROW
BEGIN
    IF NEW.listed_as = 'agent' THEN
        IF NOT EXISTS (
            SELECT 1 FROM users_user u
            JOIN users_agentprofile ap ON ap.user_id = u.id
            WHERE u.id = NEW.owner_id
              AND u.is_agent = 1
              AND ap.is_certified = 1
        ) THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '%s';
        END IF;
    END IF;
END
""" % CERT_MESSAGE


def create_triggers(apps, schema_editor):
    """Backstop for Property.clean()'s agent-certification rule. Only covers writes to
    listings_property - see users/migrations/0004_agent_decertify_guard_trigger.py for the
    mirror-image case (revoking is_certified out from under an already agent-listed property)."""
    if schema_editor.connection.vendor == "sqlite":
        schema_editor.execute(SQLITE_INSERT)
        schema_editor.execute(SQLITE_UPDATE)
    elif schema_editor.connection.vendor == "mysql":
        schema_editor.execute(MYSQL_INSERT)
        schema_editor.execute(MYSQL_UPDATE)


def drop_triggers(apps, schema_editor):
    schema_editor.execute("DROP TRIGGER IF EXISTS property_agent_cert_check_insert")
    schema_editor.execute("DROP TRIGGER IF EXISTS property_agent_cert_check_update")


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ("listings", "0005_property_property_price_required_for_rent_type_and_more"),
        ("users", "0003_remove_user_avatar"),
    ]

    operations = [
        migrations.RunPython(create_triggers, reverse_code=drop_triggers),
    ]
