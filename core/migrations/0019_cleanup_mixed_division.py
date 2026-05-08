"""
Clean up legacy data: matches with category_type='mixed' had division='mixed'.
The new rule is: Mixed category has no division (division=NULL).
Also clean up OrganizerAssignment records for Mixed category.
"""
from django.db import migrations


def cleanup_mixed_division(apps, schema_editor):
    Match = apps.get_model('core', 'Match')
    OrganizerAssignment = apps.get_model('core', 'OrganizerAssignment')

    # Update matches: Mixed category + division='mixed' → division=None
    updated = Match.objects.filter(
        category__category_type='mixed',
        division='mixed',
    ).update(division=None)

    # Update organizer assignments: Mixed category + division='mixed' → division=None
    # (may cause unique constraint issues if a None record already exists — handle gracefully)
    for a in OrganizerAssignment.objects.filter(category_type='mixed', division='mixed'):
        exists = OrganizerAssignment.objects.filter(
            organizer=a.organizer,
            event=a.event,
            category_type='mixed',
            division=None,
        ).exists()
        if not exists:
            a.division = None
            a.save()
        else:
            a.delete()  # duplicate — remove the old one


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0018_match_best_of_matchset'),
    ]

    operations = [
        migrations.RunPython(
            cleanup_mixed_division,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
