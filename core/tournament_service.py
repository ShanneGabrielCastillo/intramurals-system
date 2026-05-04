import logging
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from .models import Department, Event, Match, Score
from .utils import compute_points

logger = logging.getLogger(__name__)

GROUP_A_ABBREVS = {'CAS', 'CTED', 'CIT'}
GROUP_B_ABBREVS = {'CBA', 'CAF', 'CCJE'}


# ---------------------------------------------------------------------------
# Pure helpers (no DB access)
# ---------------------------------------------------------------------------

def _compute_round_robin_pairs(teams):
    """Return list of (team_a, team_b) tuples for every unique pair."""
    pairs = []
    for i in range(len(teams)):
        for j in range(i + 1, len(teams)):
            pairs.append((teams[i], teams[j]))
    return pairs


def _sort_standings(standings):
    """Sort standings list by points desc, wins desc."""
    return sorted(standings, key=lambda x: (-x['points'], -x['wins']))


def _compute_hybrid_semifinal_pairs(standings):
    """Return [(rank0, rank3), (rank1, rank2)] from sorted standings (min 4)."""
    return [(standings[0], standings[3]), (standings[1], standings[2])]


def _compute_group_knockout_semifinal_pairs(group_a_standings, group_b_standings):
    """Return [(a0, b1), (b0, a1)] cross-group pairings."""
    return [
        (group_a_standings[0], group_b_standings[1]),
        (group_b_standings[0], group_a_standings[1]),
    ]


def _compute_final_pairs(semi1_result, semi2_result):
    return {
        'final': (semi1_result['winner'], semi2_result['winner']),
        'third_place': (semi1_result['loser'], semi2_result['loser']),
    }


# ---------------------------------------------------------------------------
# Standings
# ---------------------------------------------------------------------------

def get_event_standings(event, stage_filter, group_filter=None, division='men', category=None):
    """
    Compute standings for a specific event, stage, optional group, division,
    and optional EventCategory. Only counts Score records where result_a != 'pending'.
    Returns sorted list of dicts: [{'department', 'wins', 'losses', 'draws', 'points'}, ...]
    """
    qs = Match.objects.filter(event=event, stage=stage_filter, division=division, category=category)
    if group_filter is not None:
        qs = qs.filter(group=group_filter)

    dept_ids = set()
    for match in qs:
        dept_ids.add(match.team_a_id)
        dept_ids.add(match.team_b_id)

    departments = Department.objects.filter(id__in=dept_ids)
    standings = []
    for dept in departments:
        scope_q = Q(
            match__event=event,
            match__stage=stage_filter,
            match__division=division,
            match__category=category,
        )
        if group_filter is not None:
            scope_q &= Q(match__group=group_filter)

        wins = Score.objects.filter(
            scope_q &
            (Q(match__team_a=dept, result_a='win') | Q(match__team_b=dept, result_b='win'))
        ).count()
        losses = Score.objects.filter(
            scope_q &
            (Q(match__team_a=dept, result_a='loss') | Q(match__team_b=dept, result_b='loss'))
        ).count()
        draws = Score.objects.filter(
            scope_q &
            (Q(match__team_a=dept, result_a='draw') | Q(match__team_b=dept, result_b='draw'))
        ).count()
        points = compute_points(wins, draws, losses)
        standings.append({
            'department': dept,
            'wins': wins,
            'losses': losses,
            'draws': draws,
            'points': points,
        })

    return _sort_standings(standings)


# ---------------------------------------------------------------------------
# Stage completion check
# ---------------------------------------------------------------------------

def is_stage_complete(event, stage, division='men', category=None):
    """
    Returns True if ALL matches for event+stage+division+category have a
    non-pending Score. Returns False if no matches exist or any are pending.
    """
    matches = Match.objects.filter(
        event=event, stage=stage, division=division, category=category
    )
    if not matches.exists():
        return False
    for match in matches:
        try:
            if match.score.result_a == 'pending':
                return False
        except Score.DoesNotExist:
            return False
    return True


# ---------------------------------------------------------------------------
# Match generation — all accept optional category parameter
# ---------------------------------------------------------------------------

def generate_round_robin_matches(event, division='men', category=None):
    """
    Generate all C(n,2) round-robin matches for all 6 departments.
    Scoped to division and optional category. Uses get_or_create (no duplicates).
    """
    teams = list(Department.objects.all())
    pairs = _compute_round_robin_pairs(teams)
    default_dt = timezone.now() + timedelta(days=7)
    matches = []
    for team_a, team_b in pairs:
        match, _ = Match.objects.get_or_create(
            event=event,
            team_a=team_a,
            team_b=team_b,
            stage='round_robin',
            division=division,
            category=category,
            defaults={'date_time': default_dt, 'venue': 'TBD', 'group': None},
        )
        matches.append(match)
    return matches


def generate_group_matches(event, division='men', category=None):
    """
    Generate intra-group round-robin matches for a group_knockout event.
    Group A: CAS, CTED, CIT  |  Group B: CBA, CAF, CCJE
    Scoped to division and optional category. Uses get_or_create (no duplicates).
    """
    default_dt = timezone.now() + timedelta(days=7)
    matches = []
    for abbrevs, group_label in [(GROUP_A_ABBREVS, 'A'), (GROUP_B_ABBREVS, 'B')]:
        teams = list(Department.objects.filter(abbreviation__in=abbrevs))
        pairs = _compute_round_robin_pairs(teams)
        for team_a, team_b in pairs:
            match, _ = Match.objects.get_or_create(
                event=event,
                team_a=team_a,
                team_b=team_b,
                stage='group',
                division=division,
                category=category,
                defaults={'date_time': default_dt, 'venue': 'TBD', 'group': group_label},
            )
            matches.append(match)
    return matches


def generate_semifinal_matches(event, division='men', category=None):
    """
    Read standings and create 2 semifinal matches scoped to division + category.
    Dispatches based on event.format ('hybrid' or 'group_knockout').
    """
    default_dt = timezone.now() + timedelta(days=7)
    pairs = []

    if event.format == 'hybrid':
        standings = get_event_standings(event, 'round_robin', division=division, category=category)
        if len(standings) < 4:
            logger.warning(
                "generate_semifinal_matches: hybrid event %s div=%s cat=%s has < 4 teams",
                event.pk, division, category,
            )
            return []
        pairs = _compute_hybrid_semifinal_pairs(standings)
        pairs = [(p[0]['department'], p[1]['department']) for p in pairs]

    elif event.format == 'group_knockout':
        standings_a = get_event_standings(event, 'group', group_filter='A', division=division, category=category)
        standings_b = get_event_standings(event, 'group', group_filter='B', division=division, category=category)
        if len(standings_a) < 2 or len(standings_b) < 2:
            logger.warning(
                "generate_semifinal_matches: group_knockout event %s div=%s cat=%s has < 2 teams/group",
                event.pk, division, category,
            )
            return []
        pairs = _compute_group_knockout_semifinal_pairs(standings_a, standings_b)
        pairs = [(p[0]['department'], p[1]['department']) for p in pairs]

    matches = []
    for team_a, team_b in pairs:
        match, _ = Match.objects.get_or_create(
            event=event,
            team_a=team_a,
            team_b=team_b,
            stage='semifinal',
            division=division,
            category=category,
            defaults={'date_time': default_dt, 'venue': 'TBD', 'group': None},
        )
        matches.append(match)
    return matches


def generate_final_matches(event, division='men', category=None):
    """
    Read semifinal results and create final + third-place matches.
    Scoped to division + category.
    """
    semis = list(Match.objects.filter(
        event=event, stage='semifinal', division=division, category=category
    ))
    if len(semis) < 2:
        logger.warning(
            "generate_final_matches: event %s div=%s cat=%s has < 2 semifinal matches",
            event.pk, division, category,
        )
        return []

    semi_results = []
    for semi in semis:
        try:
            score = semi.score
        except Score.DoesNotExist:
            logger.warning("generate_final_matches: semifinal %s has no score", semi.pk)
            return []
        if score.result_a == 'pending':
            logger.warning("generate_final_matches: semifinal %s score is pending", semi.pk)
            return []
        if score.result_a == 'win':
            winner, loser = semi.team_a, semi.team_b
        elif score.result_a == 'loss':
            winner, loser = semi.team_b, semi.team_a
        else:
            winner, loser = semi.team_a, semi.team_b
        semi_results.append({'winner': winner, 'loser': loser})

    pairs = _compute_final_pairs(semi_results[0], semi_results[1])
    default_dt = timezone.now() + timedelta(days=14)
    matches = []

    final_a, final_b = pairs['final']
    final_match, _ = Match.objects.get_or_create(
        event=event, team_a=final_a, team_b=final_b,
        stage='final', division=division, category=category,
        defaults={'date_time': default_dt, 'venue': 'TBD', 'group': None},
    )
    matches.append(final_match)

    third_a, third_b = pairs['third_place']
    third_match, _ = Match.objects.get_or_create(
        event=event, team_a=third_a, team_b=third_b,
        stage='third_place', division=division, category=category,
        defaults={'date_time': default_dt, 'venue': 'TBD', 'group': None},
    )
    matches.append(third_match)
    return matches


# ---------------------------------------------------------------------------
# Stage advancement
# ---------------------------------------------------------------------------

def check_and_advance_stage(event, division='men', category=None):
    """
    Called after every Score save. Advances to the next stage when the
    current stage is fully complete. Scoped to division + category.
    Supports hybrid and group_knockout formats only.
    """
    try:
        if event.format == 'hybrid':
            if (is_stage_complete(event, 'round_robin', division, category) and
                    not Match.objects.filter(event=event, stage='semifinal',
                                             division=division, category=category).exists()):
                generate_semifinal_matches(event, division, category)

            if (is_stage_complete(event, 'semifinal', division, category) and
                    not Match.objects.filter(event=event, stage='final',
                                             division=division, category=category).exists()):
                generate_final_matches(event, division, category)

        elif event.format == 'group_knockout':
            if (is_stage_complete(event, 'group', division, category) and
                    not Match.objects.filter(event=event, stage='semifinal',
                                             division=division, category=category).exists()):
                generate_semifinal_matches(event, division, category)

            if (is_stage_complete(event, 'semifinal', division, category) and
                    not Match.objects.filter(event=event, stage='final',
                                             division=division, category=category).exists()):
                generate_final_matches(event, division, category)

    except Exception:
        logger.exception(
            "check_and_advance_stage: error for event %s div=%s cat=%s",
            event.pk, division, category,
        )
