"""
Migration: fix orphaned core_eventcategory foreign key constraint.

The core_eventcategory table exists in the database from a previous version
of the project but has no corresponding Django model. Its FK to core_event
uses RESTRICT (default), which blocks event deletion.

This migration drops the old FK constraint and re-adds it with ON DELETE CASCADE
so that deleting an event automatically removes its orphaned category rows.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_add_event_categories'),
    ]

    operations = [
        migrations.RunSQL(
            # Forward: drop the blocking FK, re-add with CASCADE
            sql=[
                """
                ALTER TABLE core_eventcategory
                DROP FOREIGN KEY core_eventcategory_event_id_474358a2_fk_core_event_id;
                """,
                """
                ALTER TABLE core_eventcategory
                ADD CONSTRAINT core_eventcategory_event_id_fk
                FOREIGN KEY (event_id) REFERENCES core_event(id)
                ON DELETE CASCADE;
                """,
            ],
            # Reverse: restore original RESTRICT behaviour
            reverse_sql=[
                """
                ALTER TABLE core_eventcategory
                DROP FOREIGN KEY core_eventcategory_event_id_fk;
                """,
                """
                ALTER TABLE core_eventcategory
                ADD CONSTRAINT core_eventcategory_event_id_474358a2_fk_core_event_id
                FOREIGN KEY (event_id) REFERENCES core_event(id);
                """,
            ],
        ),
    ]
