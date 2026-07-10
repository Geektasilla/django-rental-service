from django.db import migrations

DECERTIFY_MESSAGE = "Cannot revoke certification while this agent has properties listed as agent."

SQLITE_UPDATE = """
CREATE TRIGGER agent_decertify_guard
BEFORE UPDATE ON users_agentprofile
WHEN NEW.is_certified = 0 AND OLD.is_certified = 1
BEGIN
    SELECT RAISE(ABORT, '%s')
    WHERE EXISTS (
        SELECT 1 FROM listings_property
        WHERE owner_id = NEW.user_id AND listed_as = 'agent'
    );
END;
""" % DECERTIFY_MESSAGE

MYSQL_UPDATE = """
CREATE TRIGGER agent_decertify_guard
BEFORE UPDATE ON users_agentprofile
FOR EACH ROW
BEGIN
    IF NEW.is_certified = 0 AND OLD.is_certified = 1 THEN
        IF EXISTS (
            SELECT 1 FROM listings_property
            WHERE owner_id = NEW.user_id AND listed_as = 'agent'
        ) THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '%s';
        END IF;
    END IF;
END
""" % DECERTIFY_MESSAGE


def create_trigger(apps, schema_editor):
    """The other half of the agent-certification invariant: without this, decertifying an agent
    (AgentProfile.is_certified -> False) while they still have Property rows with listed_as='agent'
    would silently leave those rows violating the rule that listings/migrations/
    0006_property_agent_cert_trigger.py enforces on the Property side."""
    if schema_editor.connection.vendor == "sqlite":
        schema_editor.execute(SQLITE_UPDATE)
    elif schema_editor.connection.vendor == "mysql":
        schema_editor.execute(MYSQL_UPDATE)


def drop_trigger(apps, schema_editor):
    schema_editor.execute("DROP TRIGGER IF EXISTS agent_decertify_guard")


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0003_remove_user_avatar"),
        ("listings", "0006_property_agent_cert_trigger"),
    ]

    operations = [
        migrations.RunPython(create_trigger, reverse_code=drop_trigger),
    ]
