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
# Pure helpers (no DB access) — unchanged
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
    """
    Takes two dicts each with 'winner' and 'loser' keys (Department objects).
    Returns {'final': (winner1, winner2), 'third_place': (loser1, loser2)}.
    """
    return {
        'final': (semi1_result['winner'], semi2_result['winner']),
        'third_place': (semi1_result['loser'], semi2_result['loser']),
    }


# ---------------------------------------------------------------------------
# ORM-backed service functions — all gain division='men' parameter
# ---------------------------------------------------------------------------

def get_event_standings(event, stage_filter, group_filter=None, division='men'):
    """
    Compute standings for a specific event, stage, optional group, and division.
    Only counts Score records where result_a != 'pending'.
    Returns sorted list of dicts: [{'department', 'wins', 'losses', 'draws', 'points'}, ...]
    Only includes departments that have at least one match in scope.
    """
    qs = Match.objects.filter(event=event, stage=stage_filter, division=division)
    if group_filter is not None:
        qs = qs.filter(group=group_filter)

    # Collect departments that appear in at least one match in scope
    dept_ids = set()
    for match in qs:
        dept_ids.add(match.team_a_id)
        dept_ids.add(match.team_b_id)

    departments = Department.objects.filter(id__in=dept_ids)
    standings = []
    for dept in departments:
        scope_q = Q(match__event=event, match__stage=stage_filter, match__division=division)
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


def is_stage_complete(event, stage, division='men'):
    """
    Returns False if no matches exist for that event+stage+division.
    Returns True if ALL matches have a Score with result_a != 'pending'.
    """
    matches = Match.objects.filter(event=event, stage=stage, division=division)
    if not matches.exists():
        return False
    for match in matches:
        try:
            if match.score.result_a == 'pending':
                return False
        except Score.DoesNotExist:
            return False
    return True


def generate_round_robin_matches(event, division='men'):
    """
    Generate all C(n,2) round-robin matches for the event (all 6 departments).
    Sets stage='round_robin', group=None, division=division. Uses get_or_create.
    Returns list of Match objects.
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
            defaults={'date_time': default_dt, 'venue': 'TBD', 'group': None},
        )
        matches.append(match)
    return matches


def generate_group_matches(event, division='men'):
    """
    Generate intra-group round-robin matches for a group_knockout event.
    Group A: CAS, CTED, CIT  →  3 matches with stage='group', group='A', division=division
    Group B: CBA, CAF, CCJE  →  3 matches with stage='group', group='B', division=division
    Returns list of 6 Match objects.
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
                defaults={'date_time': default_dt, 'venue': 'TBD', 'group': group_label},
            )
            matches.append(match)
    return matches


def generate_semifinal_matches(event, division='men'):
    """
    Read standings and create 2 semifinal matches scoped to the given division.
    Dispatches based on event.format ('hybrid' or 'group_knockout').
    Logs warning and returns [] if not enough teams.
    Returns list of 2 Match objects.
    """
    default_dt = timezone.now() + timedelta(days=7)
    pairs = []

    if event.format == 'hybrid':
        standings = get_event_standings(event, 'round_robin', division=division)
        if len(standings) < 4:
            logger.warning(
                "generate_semifinal_matches: hybrid event %s division=%s has fewer than 4 teams",
                event.pk, division,
            )
            return []
        pairs = _compute_hybrid_semifinal_pairs(standings)
        pairs = [(p[0]['department'], p[1]['department']) for p in pairs]

    elif event.format == 'group_knockout':
        standings_a = get_event_standings(event, 'group', group_filter='A', division=division)
        standings_b = get_event_standings(event, 'group', group_filter='B', division=division)
        if len(standings_a) < 2 or len(standings_b) < 2:
            logger.warning(
                "generate_semifinal_matches: group_knockout event %s division=%s has fewer than 2 teams per group",
                event.pk, division,
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
            defaults={'date_time': default_dt, 'venue': 'TBD', 'group': None},
        )
        matches.append(match)
    return matches


def generate_final_matches(event, division='men'):
    """
    Read semifinal results (scoped to division) and create final + third-place matches.
    Logs warning and returns [] if semis are incomplete.
    Returns list of 2 Match objects.
    """
    semis = list(Match.objects.filter(event=event, stage='semifinal', division=division))
    if len(semis) < 2:
        logger.warning(
            "generate_final_matches: event %s division=%s does not have 2 semifinal matches",
            event.pk, division,
        )
        return []

    semi_results = []
    for semi in semis:
        try:
            score = semi.score
        except Score.DoesNotExist:
            logger.warning(
                "generate_final_matches: semifinal match %s has no score yet", semi.pk
            )
            return []
        if score.result_a == 'pending':
            logger.warning(
                "generate_final_matches: semifinal match %s score is still pending", semi.pk
            )
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
        event=event,
        team_a=final_a,
        team_b=final_b,
        stage='final',
        division=division,
        defaults={'date_time': default_dt, 'venue': 'TBD', 'group': None},
    )
    matches.append(final_match)

    third_a, third_b = pairs['third_place']
    third_match, _ = Match.objects.get_or_create(
        event=event,
        team_a=third_a,
        team_b=third_b,
        stage='third_place',
        division=division,
        defaults={'date_time': default_dt, 'venue': 'TBD', 'group': None},
    )
    matches.append(third_match)
    return matches


def check_and_advance_stage(event, division='men'):
    """
    Master function called by the post_save signal on Score.
    Handles stage progression for hybrid and group_knockout events, scoped to division.
    Returns immediately for round_robin events.
    All exceptions are caught and logged.
    """
    if event.format == 'round_robin':
        return

    try:
        if event.format == 'hybrid':
            semifinal_exists = Match.objects.filter(
                event=event, stage='semifinal', division=division).exists()
            if is_stage_complete(event, 'round_robin', division=division) and not semifinal_exists:
                generate_semifinal_matches(event, division=division)

            final_exists = Match.objects.filter(
                event=event, stage='final', division=division).exists()
            if is_stage_complete(event, 'semifinal', division=division) and not final_exists:
                generate_final_matches(event, division=division)

        elif event.format == 'group_knockout':
            semifinal_exists = Match.objects.filter(
                event=event, stage='semifinal', division=division).exists()
            if is_stage_complete(event, 'group', division=division) and not semifinal_exists:
                generate_semifinal_matches(event, division=division)

            final_exists = Match.objects.filter(
                event=event, stage='final', division=division).exists()
            if is_stage_complete(event, 'semifinal', division=division) and not final_exists:
                generate_final_matches(event, division=division)

    except Exception:
        logger.exception(
            "check_and_advance_stage: unexpected error for event %s division=%s",
            event.pk, division,
        )
