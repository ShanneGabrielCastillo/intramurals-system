from django.db import migrations


class Migration(migrations.Migration):
    """
    Enforce that only ONE organizer can be assigned to each
    event + category_type + division combination.
    """

    dependencies = [
        ('core', '0015_organizerassignment'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='organizerassignment',
            unique_together={
                ('organizer', 'event', 'category_type', 'division'),
                ('event', 'category_type', 'division'),
            },
        ),
    ]
