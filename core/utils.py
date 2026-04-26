from django.db.models import Q
from .models import Department, Score


def compute_points(wins, draws, losses):
    """Win=3pts, Draw=1pt, Loss=0pts"""
    return wins * 3 + draws * 1


def get_leaderboard():
    """
    Returns a list of dicts sorted by points desc, then wins desc.
    Each dict: {'department': dept, 'wins': int, 'losses': int, 'draws': int, 'points': int}
    Only counts scores where result is NOT 'pending'.
    """
    departments = Department.objects.all()
    standings = []
    for dept in departments:
        wins = Score.objects.filter(
            Q(match__team_a=dept, result_a='win') |
            Q(match__team_b=dept, result_b='win')
        ).count()
        losses = Score.objects.filter(
            Q(match__team_a=dept, result_a='loss') |
            Q(match__team_b=dept, result_b='loss')
        ).count()
        draws = Score.objects.filter(
            Q(match__team_a=dept, result_a='draw') |
            Q(match__team_b=dept, result_b='draw')
        ).count()
        points = compute_points(wins, draws, losses)
        standings.append({
            'department': dept,
            'wins': wins,
            'losses': losses,
            'draws': draws,
            'points': points,
        })
    standings.sort(key=lambda x: (-x['points'], -x['wins']))
    return standings
