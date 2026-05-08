"""
Tournament stage progression and medal result signal.

on_event_saved  — fires after Event creation:
  • If has_categories=True: creates Singles/Doubles/Mixed EventCategory objects,
    then generates matches per category × division.
  • If has_categories=False: generates matches per division (existing behaviour).

on_score_saved  — fires after every Score save:
  • Advances knockout stages for the correct division + category combination.
  • Saves Gold/Silver/Bronze EventResult records.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Event, EventCategory, Score
from . import tournament_service, result_service

# Ordered list of categories auto-created when has_categories=True
_AUTO_CATEGORIES = [
    ('singles', 'Singles'),
    ('doubles', 'Doubles'),
    ('mixed',   'Mixed'),
]


def _get_divisions(event):
    """Return list of division strings based on event.division_type."""
    dt = event.division_type
    if dt == 'men':
        return ['men']
    elif dt == 'women':
        return ['women']
    return ['men', 'women']


@receiver(post_save, sender=Event)
def on_event_saved(sender, instance, created, **kwargs):
    """
    Auto-generate matches when a new event is created.
    Only runs on creation (not edits) to avoid duplicate matches.
    """
    if not created:
        return

    if instance.has_categories:
        # 1. Create the three categories
        categories = []
        for cat_type, cat_name in _AUTO_CATEGORIES:
            cat, _ = EventCategory.objects.get_or_create(
                event=instance,
                category_type=cat_type,
                defaults={'name': cat_name},
            )
            categories.append(cat)

        # 2. Generate matches per category × division
        for cat in categories:
            if cat.category_type == 'mixed':
                # Mixed category uses division='mixed' in storage
                # (display layer omits the redundant "Mixed Division" label)
                _generate_initial_matches(instance, division='mixed', category=cat)
            else:
                # Singles / Doubles respect division_type
                for div in _get_divisions(instance):
                    _generate_initial_matches(instance, division=div, category=cat)
    else:
        # No categories — standard generation per division
        for div in _get_divisions(instance):
            _generate_initial_matches(instance, division=div, category=None)


def _generate_initial_matches(event, division, category):
    """Dispatch to the correct generator based on event format."""
    if event.format == 'hybrid':
        tournament_service.generate_round_robin_matches(event, division=division, category=category)
    elif event.format == 'group_knockout':
        tournament_service.generate_group_matches(event, division=division, category=category)
    # round_robin format: no auto-generation (matches added manually)


def regenerate_matches_for_event(event):
    """
    Delete all existing matches for the event and regenerate them
    based on the event's current format, division_type, and has_categories.

    Called when an event's format/division/category settings change.
    Caller is responsible for wrapping this in a transaction.
    """
    # Delete all matches (cascades to Score, EventResult via FK)
    event.matches.all().delete()

    if event.has_categories:
        # Ensure categories exist (get_or_create is idempotent)
        categories = []
        for cat_type, cat_name in _AUTO_CATEGORIES:
            cat, _ = EventCategory.objects.get_or_create(
                event=event,
                category_type=cat_type,
                defaults={'name': cat_name},
            )
            categories.append(cat)

        for cat in categories:
            if cat.category_type == 'mixed':
                _generate_initial_matches(event, division='mixed', category=cat)
            else:
                for div in _get_divisions(event):
                    _generate_initial_matches(event, division=div, category=cat)
    else:
        for div in _get_divisions(event):
            _generate_initial_matches(event, division=div, category=None)


@receiver(post_save, sender=Score)
def on_score_saved(sender, instance, **kwargs):
    """
    After a score is saved, advance the knockout stage for the correct
    division + category combination, then update medal standings.
    """
    match = instance.match
    event = match.event
    division = match.division
    category = match.category  # None for non-category events

    tournament_service.check_and_advance_stage(event, division=division, category=category)
    result_service.save_event_results(instance)
