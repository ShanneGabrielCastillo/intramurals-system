from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0014_add_event_organizer'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='OrganizerAssignment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category_type', models.CharField(
                    blank=True, null=True, max_length=20,
                    choices=[('singles', 'Singles'), ('doubles', 'Doubles'), ('mixed', 'Mixed')],
                    help_text='Leave blank to assign all categories of this event.',
                )),
                ('division', models.CharField(
                    blank=True, null=True, max_length=10,
                    choices=[('men', 'Men'), ('women', 'Women'), ('mixed', 'Mixed')],
                    help_text='Leave blank to assign all divisions of this event.',
                )),
                ('event', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='organizer_assignments',
                    to='core.event',
                )),
                ('organizer', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='assignments',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['event__name', 'category_type', 'division'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='organizerassignment',
            unique_together={('organizer', 'event', 'category_type', 'division')},
        ),
    ]
