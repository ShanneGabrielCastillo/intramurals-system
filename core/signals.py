"""
Tournament stage progression and medal result signal.
Fires after every Score save to:
1. Automatically generate the next round of matches when the current stage is complete.
2. Automatically save Gold/Silver/Bronze EventResult records for final and third-place matches.

Also fires after every Event save to:
3. Auto-generate round-robin matches when a hybrid event is created.
4. Auto-generate group matches when a group_knockout event is created.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Event, Score
from . import tournament_service, result_service


@receiver(post_save, sender=Event)
def on_event_saved(sender, instance, created, **kwargs):
    """
    When a new hybrid or group_knockout event is created, automatically
    generate the initial round of matches so organizers only need to
    fill in date/time and venue.

    Uses get_or_create internally so running this multiple times is safe
    — it will never create duplicate matches.
    """
    if not created:
        return  # only trigger on creation, not on edits

    if instance.format == 'hybrid':
        # Generate all 15 round-robin matches (6 teams, every pair once)
        # for both Men's and Women's divisions
        tournament_service.generate_round_robin_matches(instance, division='men')
        tournament_service.generate_round_robin_matches(instance, division='women')

    elif instance.format == 'group_knockout':
        # Generate 6 intra-group matches (3 per group) for both divisions
        tournament_service.generate_group_matches(instance, division='men')
        tournament_service.generate_group_matches(instance, division='women')


@receiver(post_save, sender=Score)
def on_score_saved(sender, instance, **kwargs):
    event = instance.match.event
    tournament_service.check_and_advance_stage(event, division='men')
    tournament_service.check_and_advance_stage(event, division='women')
    result_service.save_event_results(instance)  # derive and persist medal positions
