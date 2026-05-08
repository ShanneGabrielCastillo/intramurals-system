from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0013_remove_student_role'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='organizer',
            field=models.ForeignKey(
                blank=True,
                help_text='Organizer assigned to manage this event.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='assigned_events',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
