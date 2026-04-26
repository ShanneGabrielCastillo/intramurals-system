"""
Result Service — Overall Leaderboard / General Champion System

Derives and persists EventResult records (Gold/Silver/Bronze) from
scored final and third-place matches. Also provides get_overall_leaderboard()
for the overall leaderboard view.

Called from signals.py after check_and_advance_stage — purely additive.
Never modifies Match, Score, Event, or Department records.
"""
import logging

from .models import Department, EventResult

logger = logging.getLogger(__name__)

# Medal point values: Gold=5, Silver=3, Bronze=1
MEDAL_POINTS = {1: 5, 2: 3, 3: 1}


def save_event_results(score_instance) -> None:
    """
    Derive and persist EventResult records from a scored final or third-place match.

    - final match:       winner → Gold (pos 1), loser → Silver (pos 2)
    - third_place match: winner → Bronze (pos 3)
    - draw tiebreaker:   team_a gets the higher position
    - other stages:      return immediately, no action

    Uses update_or_create so repeated calls are idempotent.
    Catches and logs all exceptions — never interrupts the signal handler.
    """
    try:
        match = score_instance.match
        division = match.division  # read division from match for EventResult lookup

        # Skip if score not yet computed
        if score_instance.result_a == 'pending':
            return

        if match.stage == 'final':
            if score_instance.result_a == 'win':
                gold_dept, silver_dept = match.team_a, match.team_b
            elif score_instance.result_a == 'loss':
                gold_dept, silver_dept = match.team_b, match.team_a
            else:
                # draw — team_a gets Gold by tiebreaker convention
                gold_dept, silver_dept = match.team_a, match.team_b

            EventResult.objects.update_or_create(
                event=match.event,
                department=gold_dept,
                division=division,
                defaults={'position': 1},
            )
            EventResult.objects.update_or_create(
                event=match.event,
                department=silver_dept,
                division=division,
                defaults={'position': 2},
            )

        elif match.stage == 'third_place':
            if score_instance.result_a == 'win':
                bronze_dept = match.team_a
            elif score_instance.result_a == 'loss':
                bronze_dept = match.team_b
            else:
                # draw — team_a gets Bronze by tiebreaker convention
                bronze_dept = match.team_a

            EventResult.objects.update_or_create(
                event=match.event,
                department=bronze_dept,
                division=division,
                defaults={'position': 3},
            )

        # All other stages: no action

    except Exception:
        logger.exception(
            "save_event_results: unexpected error for score_instance pk=%s",
            getattr(score_instance, 'pk', 'unknown'),
        )


def get_overall_leaderboard() -> list:
    """
    Aggregate EventResult records into a ranked medal table for all 6 departments.

    Always returns all 6 departments (zero counts for those with no medals).
    Sorted by: total_points desc → gold desc → silver desc.

    Returns list of dicts:
        [{'department': Department, 'gold': int, 'silver': int,
          'bronze': int, 'total_points': int}, ...]
    """
    departments = Department.objects.all()
    standings = []

    for dept in departments:
        gold = EventResult.objects.filter(department=dept, position=1).count()
        silver = EventResult.objects.filter(department=dept, position=2).count()
        bronze = EventResult.objects.filter(department=dept, position=3).count()
        total_points = (
            gold * MEDAL_POINTS[1] +
            silver * MEDAL_POINTS[2] +
            bronze * MEDAL_POINTS[3]
        )
        standings.append({
            'department': dept,
            'gold': gold,
            'silver': silver,
            'bronze': bronze,
            'total_points': total_points,
        })

    standings.sort(key=lambda x: (-x['total_points'], -x['gold'], -x['silver']))
    return standings
