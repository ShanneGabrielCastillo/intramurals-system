from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0016_organizerassignment_unique_per_slot'),
    ]

    operations = [
        migrations.CreateModel(
            name='Season',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='e.g. "2026 Intramurals"', max_length=100)),
                ('year', models.PositiveIntegerField()),
                ('is_active', models.BooleanField(
                    default=False,
                    help_text='Only one season should be active at a time.',
                )),
            ],
            options={
                'ordering': ['-year', '-id'],
            },
        ),
        migrations.AddField(
            model_name='event',
            name='season',
            field=models.ForeignKey(
                blank=True,
                help_text='Season this event belongs to.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='events',
                to='core.season',
            ),
        ),
    ]
