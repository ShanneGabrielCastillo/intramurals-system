from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0017_season_event_season'),
    ]

    operations = [
        migrations.AddField(
            model_name='match',
            name='best_of',
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                help_text='Number of sets (e.g. 3, 5, 7). Leave blank for normal scoring.',
            ),
        ),
        migrations.CreateModel(
            name='MatchSet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('set_number', models.PositiveIntegerField()),
                ('score_a', models.PositiveIntegerField(default=0, help_text='Points scored by Team A in this set')),
                ('score_b', models.PositiveIntegerField(default=0, help_text='Points scored by Team B in this set')),
                ('match', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='sets',
                    to='core.match',
                )),
            ],
            options={
                'ordering': ['set_number'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='matchset',
            unique_together={('match', 'set_number')},
        ),
    ]
