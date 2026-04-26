from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .models import Department, Event, Match, Score
from .forms import EventForm, MatchForm, ScoreForm
from .decorators import role_required
from .utils import get_leaderboard


def login_view(request):
    if request.user.is_authenticated:
        return redirect('/dashboard/')

    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        remember_me = request.POST.get('remember_me')

        if not username or not password:
            error = 'Please enter both username and password.'
        else:
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                # Remember Me: keep session for 2 weeks; otherwise expire on browser close
                if remember_me:
                    request.session.set_expiry(1209600)  # 14 days in seconds
                else:
                    request.session.set_expiry(0)  # expires when browser closes
                return redirect('/dashboard/')
            else:
                error = 'Invalid credentials. Please try again.'

    return render(request, 'core/login.html', {'error': error})


def logout_view(request):
    logout(request)
    return redirect('/login/')


# --- 6.1 Dashboard ---

@login_required
def dashboard_view(request):
    leaderboard = get_leaderboard()
    context = {
        'total_events': Event.objects.count(),
        'total_matches': Match.objects.count(),
        'completed_matches': Score.objects.exclude(result_a='pending').count(),
        'top_department': leaderboard[0] if leaderboard else None,
    }
    return render(request, 'core/dashboard.html', context)


# --- 6.2 Departments ---

@login_required
def department_list(request):
    departments = Department.objects.order_by('display_order')
    return render(request, 'core/departments.html', {'departments': departments})


# --- 6.3 Event views ---

@login_required
def event_list(request):
    events = Event.objects.all()
    return render(request, 'core/events.html', {'events': events})


@login_required
@role_required('admin')
def event_create(request):
    form = EventForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        event = form.save()
        messages.success(request, f'Event "{event.name}" created successfully.')
        return redirect('event_list')
    return render(request, 'core/event_form.html', {'form': form, 'action': 'Create'})


@login_required
@role_required('admin')
def event_update(request, pk):
    event = get_object_or_404(Event, pk=pk)
    form = EventForm(request.POST or None, instance=event)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Event "{event.name}" updated successfully.')
        return redirect('event_list')
    return render(request, 'core/event_form.html', {'form': form, 'action': 'Edit', 'event': event})


@login_required
@role_required('admin')
def event_delete(request, pk):
    event = get_object_or_404(Event, pk=pk)
    if request.method == 'POST':
        name = event.name
        event.delete()
        messages.success(request, f'Event "{name}" deleted.')
    return redirect('event_list')


# --- 6.4 Match views ---

STAGE_ORDER = ['group', 'round_robin', 'semifinal', 'final', 'third_place']
STAGE_LABELS = {
    'group': 'Group Stage',
    'round_robin': 'Round Robin',
    'semifinal': 'Semifinals',
    'final': 'Finals',
    'third_place': '3rd Place Match',
}

@login_required
def match_list(request):
    q = request.GET.get('q', '').strip()
    matches = Match.objects.select_related('event', 'team_a', 'team_b').order_by(
        'event__name', 'division', 'stage', 'date_time'
    )
    if q:
        matches = matches.filter(
            Q(event__name__icontains=q) |
            Q(team_a__name__icontains=q) |
            Q(team_b__name__icontains=q) |
            Q(venue__icontains=q)
        )

    # Group: event → division → stage → [matches]
    # Structure: [{'event': Event, 'divisions': {'men': {'label':..., 'stages': {...}}, 'women': {...}}}]
    events_seen = {}  # event.pk → index in event_groups
    event_groups = []

    for match in matches:
        evt = match.event
        if evt.pk not in events_seen:
            events_seen[evt.pk] = len(event_groups)
            event_groups.append({'event': evt, 'divisions': {}})
        eg = event_groups[events_seen[evt.pk]]

        div = match.division  # 'men' or 'women'
        if div not in eg['divisions']:
            eg['divisions'][div] = {
                'label': "Men's Division" if div == 'men' else "Women's Division",
                'stages': {},
            }

        stage = match.stage
        if stage not in eg['divisions'][div]['stages']:
            eg['divisions'][div]['stages'][stage] = {
                'label': STAGE_LABELS.get(stage, stage),
                'matches': [],
            }
        eg['divisions'][div]['stages'][stage]['matches'].append(match)

    has_bracket = Match.objects.filter(stage='semifinal').exists()
    auto_formats = {'hybrid', 'group_knockout'}
    has_auto_events = Event.objects.filter(format__in=auto_formats).exists()

    return render(request, 'core/schedule.html', {
        'event_groups': event_groups,
        'query': q,
        'has_bracket': has_bracket,
        'has_auto_events': has_auto_events,
    })


@login_required
@role_required('admin', 'organizer')
def match_create(request):
    form = MatchForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        match = form.save()
        Score.objects.get_or_create(match=match)
        messages.success(request, 'Match scheduled successfully.')
        return redirect('match_list')
    return render(request, 'core/match_form.html', {'form': form, 'action': 'Schedule'})


@login_required
@role_required('admin', 'organizer')
def match_update(request, pk):
    match = get_object_or_404(Match, pk=pk)
    form = MatchForm(request.POST or None, instance=match)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'{match.team_a.abbreviation} vs {match.team_b.abbreviation} updated successfully.')
        return redirect('match_list')
    return render(request, 'core/match_form.html', {'form': form, 'action': 'Edit', 'match': match})


@login_required
@role_required('admin')
def match_delete(request, pk):
    match = get_object_or_404(Match, pk=pk)
    if request.method == 'POST':
        label = f'{match.team_a.abbreviation} vs {match.team_b.abbreviation}'
        match.delete()
        messages.success(request, f'Match "{label}" deleted.')
    return redirect('match_list')


# --- 6.5 Score views ---

@login_required
def results_list(request):
    matches = Match.objects.select_related(
        'score', 'team_a', 'team_b', 'event'
    ).order_by('event__name', 'division', 'stage', 'date_time')

    # Group: event → division → stage → [matches]
    events_seen = {}
    event_groups = []

    stage_labels = {
        'round_robin': 'Round Robin',
        'group': 'Group Stage',
        'semifinal': 'Semifinals',
        'final': 'Finals',
        'third_place': '3rd Place Match',
    }
    stage_colors = {
        'round_robin': '#1a56db',
        'group': '#1a56db',
        'semifinal': '#d97706',
        'final': '#059669',
        'third_place': '#7c3aed',
    }

    for match in matches:
        evt = match.event
        if evt.pk not in events_seen:
            events_seen[evt.pk] = len(event_groups)
            event_groups.append({'event': evt, 'divisions': {}})
        eg = event_groups[events_seen[evt.pk]]

        div = match.division
        if div not in eg['divisions']:
            eg['divisions'][div] = {
                'label': "Men's Division" if div == 'men' else "Women's Division",
                'stages': {},
            }

        stage = match.stage
        if stage not in eg['divisions'][div]['stages']:
            eg['divisions'][div]['stages'][stage] = {
                'label': stage_labels.get(stage, stage),
                'color': stage_colors.get(stage, '#1a56db'),
                'matches': [],
            }
        eg['divisions'][div]['stages'][stage]['matches'].append(match)

    return render(request, 'core/results.html', {'event_groups': event_groups})


@login_required
@role_required('admin', 'organizer')
def score_update(request, pk):
    match = get_object_or_404(Match, pk=pk)
    score, _ = Score.objects.get_or_create(match=match)
    form = ScoreForm(request.POST or None, instance=score)
    if request.method == 'POST' and form.is_valid():
        score = form.save(commit=False)
        score.compute_result()
        score.save()

        # Build result notification message
        event_name = match.event.name
        division_label = "Men's Division" if match.division == 'men' else "Women's Division"
        if score.result_a == 'win':
            winner = match.team_a.name
            msg = f'🏆 {winner} won {event_name} ({division_label}) — {score.score_a}–{score.score_b}'
            messages.success(request, msg)
        elif score.result_a == 'loss':
            winner = match.team_b.name
            msg = f'🏆 {winner} won {event_name} ({division_label}) — {score.score_b}–{score.score_a}'
            messages.success(request, msg)
        else:
            msg = f'🤝 Draw: {match.team_a.abbreviation} vs {match.team_b.abbreviation} in {event_name} ({division_label}) — {score.score_a}–{score.score_b}'
            messages.info(request, msg)

        return redirect('results_list')
    return render(request, 'core/score_form.html', {'form': form, 'match': match})


# --- 6.6 Event Standings (formerly Leaderboard) ---

@login_required
def leaderboard_view(request):
    from .tournament_service import get_event_standings

    events = Event.objects.all().order_by('name')
    selected_event = None
    event_data = None

    event_id = request.GET.get('event_id')
    active_tab = request.GET.get('tab', 'standings')
    division = request.GET.get('division', 'men')
    if division not in ('men', 'women'):
        division = 'men'

    if event_id:
        selected_event = get_object_or_404(Event, pk=event_id)
        fmt = selected_event.format

        if fmt == 'group_knockout':
            group_a = [{'rank': i, **e} for i, e in enumerate(
                get_event_standings(selected_event, 'group', group_filter='A', division=division), start=1)]
            group_b = [{'rank': i, **e} for i, e in enumerate(
                get_event_standings(selected_event, 'group', group_filter='B', division=division), start=1)]
            semis = Match.objects.filter(event=selected_event, stage='semifinal', division=division).select_related('score', 'team_a', 'team_b')
            finals = Match.objects.filter(event=selected_event, stage__in=['final', 'third_place'], division=division).select_related('score', 'team_a', 'team_b')
            all_matches = Match.objects.filter(event=selected_event, division=division).select_related('score', 'team_a', 'team_b').order_by('stage', 'date_time')
            event_data = {
                'format': fmt,
                'group_a': group_a,
                'group_b': group_b,
                'semis': semis,
                'finals': finals,
                'matches': all_matches,
            }

        elif fmt == 'hybrid':
            rr_standings = [{'rank': i, **e} for i, e in enumerate(
                get_event_standings(selected_event, 'round_robin', division=division), start=1)]
            semis = Match.objects.filter(event=selected_event, stage='semifinal', division=division).select_related('score', 'team_a', 'team_b')
            finals = Match.objects.filter(event=selected_event, stage__in=['final', 'third_place'], division=division).select_related('score', 'team_a', 'team_b')
            all_matches = Match.objects.filter(event=selected_event, division=division).select_related('score', 'team_a', 'team_b').order_by('stage', 'date_time')
            event_data = {
                'format': fmt,
                'rr_standings': rr_standings,
                'semis': semis,
                'finals': finals,
                'matches': all_matches,
            }

        else:  # round_robin
            rr_standings = [{'rank': i, **e} for i, e in enumerate(
                get_event_standings(selected_event, 'round_robin', division=division), start=1)]
            all_matches = Match.objects.filter(event=selected_event, division=division).select_related('score', 'team_a', 'team_b').order_by('date_time')
            event_data = {
                'format': fmt,
                'rr_standings': rr_standings,
                'matches': all_matches,
            }

    return render(request, 'core/leaderboard.html', {
        'events': events,
        'selected_event': selected_event,
        'event_data': event_data,
        'active_tab': active_tab,
        'event_id': event_id,
        'division': division,
    })


# --- Tournament Bracket ---

@login_required
def tournament_bracket(request, event_pk):
    event = get_object_or_404(Event, pk=event_pk)
    semis = Match.objects.filter(event=event, stage='semifinal').select_related(
        'score', 'team_a', 'team_b')
    finals = Match.objects.filter(event=event, stage__in=['final', 'third_place']).select_related(
        'score', 'team_a', 'team_b')
    return render(request, 'core/bracket.html', {
        'event': event,
        'semis': semis,
        'finals': finals,
    })


# --- Overall Leaderboard ---

@login_required
def overall_leaderboard_view(request):
    from .result_service import get_overall_leaderboard
    raw = get_overall_leaderboard()
    standings = [{'rank': i, **entry} for i, entry in enumerate(raw, start=1)]
    return render(request, 'core/overall_leaderboard.html', {'standings': standings})
