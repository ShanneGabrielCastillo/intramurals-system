from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .models import Department, Event, Match, Score
from .forms import EventForm, MatchForm, MatchEditForm, ScoreForm
from .decorators import role_required


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
    from django.utils import timezone
    from .result_service import get_overall_leaderboard

    overall = get_overall_leaderboard()
    # Top department = rank 1 from overall leaderboard (medal-based)
    # Only count as "top" if they have at least one medal
    top_department = next((e for e in overall if e['total_points'] > 0), None)
    now = timezone.now()

    # Recent completed matches — last 5 sorted by when the score was last updated
    recent_matches = (
        Match.objects.select_related('event', 'team_a', 'team_b', 'score', 'category')
        .exclude(score__result_a='pending')
        .filter(score__isnull=False)
        .order_by('-score__updated_at')[:5]
    )

    # Upcoming matches — next 5 that haven't been played yet (no score or pending)
    upcoming_matches = (
        Match.objects.select_related('event', 'team_a', 'team_b')
        .filter(date_time__gte=now)
        .filter(Q(score__isnull=True) | Q(score__result_a='pending'))
        .order_by('date_time')[:5]
    )

    context = {
        'total_events': Event.objects.count(),
        'total_matches': Match.objects.count(),
        'completed_matches': Score.objects.exclude(result_a='pending').count(),
        'top_department': top_department,
        'recent_matches': recent_matches,
        'upcoming_matches': upcoming_matches,
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
    from django.db import transaction
    from .signals import regenerate_matches_for_event

    event = get_object_or_404(Event, pk=pk)
    form = EventForm(request.POST or None, instance=event)

    if request.method == 'POST' and form.is_valid():
        # Read old values FRESH FROM THE DATABASE — not from the in-memory
        # instance, because ModelForm._post_clean() mutates the instance
        # in-place during is_valid(), overwriting the old values before we
        # can compare them.
        db_event = Event.objects.get(pk=pk)
        old_format = db_event.format
        old_division_type = db_event.division_type
        old_has_categories = db_event.has_categories

        new_format = form.cleaned_data['format']
        new_division_type = form.cleaned_data['division_type']
        new_has_categories = form.cleaned_data['has_categories']

        structure_changed = (
            new_format != old_format or
            new_division_type != old_division_type or
            new_has_categories != old_has_categories
        )

        if structure_changed:
            # Check if any existing matches already have scored results
            has_scored = Score.objects.filter(
                match__event=event
            ).exclude(result_a='pending').exists()

            if has_scored and not request.POST.get('confirm_regenerate'):
                # Re-render the form with a confirmation warning
                messages.warning(
                    request,
                    'This event has scored matches. Changing the format, division, or categories '
                    'will delete ALL existing matches and results. '
                    'Click "Save & Regenerate" to confirm.'
                )
                return render(request, 'core/event_form.html', {
                    'form': form,
                    'action': 'Edit',
                    'event': event,
                    'needs_confirm': True,
                })

            # Save the event first, then regenerate matches inside a transaction
            with transaction.atomic():
                form.save()
                regenerate_matches_for_event(event)

            messages.success(
                request,
                f'Event "{event.name}" updated. Matches regenerated successfully.'
            )
        else:
            # No structural change — plain save, no match regeneration needed
            form.save()
            messages.success(request, f'Event "{event.name}" updated successfully.')

        return redirect('event_list')

    return render(request, 'core/event_form.html', {
        'form': form,
        'action': 'Edit',
        'event': event,
        'needs_confirm': False,
    })


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

STAGE_LABELS = {
    'group': 'Group Stage',
    'round_robin': 'Round Robin',
    'semifinal': 'Semifinals',
    'final': 'Finals',
    'third_place': '3rd Place Match',
}

DIVISION_LABELS = {
    'men': "♂ Men's Division",
    'women': "♀ Women's Division",
    'mixed': "🔀 Mixed Division",
}

STAGE_COLORS = {
    'round_robin': '#1a56db',
    'group': '#1a56db',
    'semifinal': '#d97706',
    'final': '#059669',
    'third_place': '#7c3aed',
}

CATEGORY_ICONS = {
    'singles': '👤',
    'doubles': '👥',
    'mixed': '🔀',
}


def _build_event_groups(matches):
    """
    Build the event_groups structure used by both schedule and results views.

    For events WITH categories:
      event → categories (ordered: singles, doubles, mixed) → divisions → stages → matches

    For events WITHOUT categories:
      event → divisions → stages → matches  (categories list is empty)

    Returns a list of dicts:
    [
      {
        'event': Event,
        'has_categories': bool,
        'categories': [          # only populated when has_categories=True
          {
            'key': 'singles',
            'label': 'Singles',
            'icon': '👤',
            'divisions': {
              'men': {'label': "♂ Men's Division", 'stages': {'round_robin': {'label':..., 'color':..., 'matches':[...]}}},
              ...
            }
          },
          ...
        ],
        'divisions': {           # only populated when has_categories=False
          'men': {'label':..., 'stages': {...}},
          ...
        },
      },
      ...
    ]
    """
    events_seen = {}
    event_groups = []

    # Category ordering for consistent display
    cat_order = {'singles': 0, 'doubles': 1, 'mixed': 2}

    for match in matches:
        evt = match.event

        if evt.pk not in events_seen:
            events_seen[evt.pk] = len(event_groups)
            event_groups.append({
                'event': evt,
                'has_categories': evt.has_categories,
                'categories': {},   # cat_type → cat_data dict
                'divisions': {},    # used when no categories
            })
        eg = event_groups[events_seen[evt.pk]]

        div = match.division
        stage = match.stage
        stage_entry = {
            'label': STAGE_LABELS.get(stage, stage),
            'color': STAGE_COLORS.get(stage, '#1a56db'),
            'matches': [],
        }

        if evt.has_categories and match.category:
            cat = match.category
            cat_type = cat.category_type

            if cat_type not in eg['categories']:
                eg['categories'][cat_type] = {
                    'key': cat_type,
                    'label': cat.get_category_type_display(),
                    'icon': CATEGORY_ICONS.get(cat_type, '🏅'),
                    'divisions': {},
                }
            cat_data = eg['categories'][cat_type]

            if div not in cat_data['divisions']:
                cat_data['divisions'][div] = {
                    'label': DIVISION_LABELS.get(div, div.title()),
                    'stages': {},
                }
            div_data = cat_data['divisions'][div]

            if stage not in div_data['stages']:
                div_data['stages'][stage] = stage_entry
            div_data['stages'][stage]['matches'].append(match)

        else:
            # No category — flat event → division → stage
            if div not in eg['divisions']:
                eg['divisions'][div] = {
                    'label': DIVISION_LABELS.get(div, div.title()),
                    'stages': {},
                }
            div_data = eg['divisions'][div]

            if stage not in div_data['stages']:
                div_data['stages'][stage] = stage_entry
            div_data['stages'][stage]['matches'].append(match)

    # Sort categories by defined order for consistent display
    for eg in event_groups:
        eg['categories'] = dict(
            sorted(eg['categories'].items(), key=lambda x: cat_order.get(x[0], 99))
        )

    return event_groups


@login_required
def match_list(request):
    q = request.GET.get('q', '').strip()
    matches = Match.objects.select_related(
        'event', 'team_a', 'team_b', 'category'
    ).order_by('event__name', 'category__category_type', 'division', 'stage', 'date_time')

    if q:
        matches = matches.filter(
            Q(event__name__icontains=q) |
            Q(team_a__name__icontains=q) |
            Q(team_b__name__icontains=q) |
            Q(venue__icontains=q)
        )

    event_groups = _build_event_groups(matches)

    auto_formats = {'hybrid', 'group_knockout'}
    has_auto_events = Event.objects.filter(format__in=auto_formats).exists()

    return render(request, 'core/schedule.html', {
        'event_groups': event_groups,
        'query': q,
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
    # Use MatchEditForm — only team_a, team_b, date_time, venue are editable.
    # event, stage, group, division are excluded from the form entirely,
    # so they cannot be changed even via a crafted POST request.
    form = MatchEditForm(request.POST or None, instance=match)
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
    q = request.GET.get('q', '').strip()
    matches = Match.objects.select_related(
        'score', 'team_a', 'team_b', 'event', 'category'
    ).order_by('event__name', 'category__category_type', 'division', 'stage', 'date_time')

    if q:
        matches = matches.filter(
            Q(event__name__icontains=q) |
            Q(team_a__name__icontains=q) |
            Q(team_b__name__icontains=q) |
            Q(venue__icontains=q)
        )

    event_groups = _build_event_groups(matches)
    return render(request, 'core/results.html', {'event_groups': event_groups, 'query': q})


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
    from .models import EventCategory

    events = Event.objects.all().order_by('name')
    selected_event = None
    event_data = None
    selected_category = None
    categories = []
    available_divisions = ['men', 'women']

    event_id = request.GET.get('event_id')
    active_tab = request.GET.get('tab', 'standings')
    division = request.GET.get('division', 'men')
    category_id = request.GET.get('category_id')

    if event_id:
        selected_event = get_object_or_404(Event, pk=event_id)
        fmt = selected_event.format
        dt = selected_event.division_type

        # --- Category handling ---
        if selected_event.has_categories:
            categories = list(selected_event.categories.all())
            # Select category from URL param or default to first
            if category_id:
                selected_category = next(
                    (c for c in categories if str(c.pk) == category_id), None
                )
            if not selected_category and categories:
                selected_category = categories[0]

            # Mixed category forces division=mixed, hides division selector
            if selected_category and selected_category.category_type == 'mixed':
                available_divisions = ['mixed']
                division = 'mixed'
            else:
                # Singles / Doubles respect event's division_type
                if dt == 'men':
                    available_divisions = ['men']
                elif dt == 'women':
                    available_divisions = ['women']
                else:
                    available_divisions = ['men', 'women']
                if division not in available_divisions:
                    division = available_divisions[0]
        else:
            # No categories — use division_type directly
            if dt == 'men':
                available_divisions = ['men']
            elif dt == 'women':
                available_divisions = ['women']
            else:
                available_divisions = ['men', 'women']
            if division not in available_divisions:
                division = available_divisions[0]

        # --- Build category filter for match queries ---
        cat_filter = {}
        if selected_event.has_categories and selected_category:
            cat_filter = {'category': selected_category}

        # --- Build event_data based on format ---
        def _get_champion(finals_qs):
            """Return the champion Department from the final match, or None."""
            for match in finals_qs:
                if match.stage == 'final':
                    try:
                        score = match.score
                        if score.result_a == 'win':
                            return match.team_a
                        elif score.result_a == 'loss':
                            return match.team_b
                    except Score.DoesNotExist:
                        pass
            return None

        if fmt == 'group_knockout':
            group_a = [{'rank': i, **e} for i, e in enumerate(
                get_event_standings(selected_event, 'group', group_filter='A',
                                    division=division, category=selected_category), start=1)]
            group_b = [{'rank': i, **e} for i, e in enumerate(
                get_event_standings(selected_event, 'group', group_filter='B',
                                    division=division, category=selected_category), start=1)]
            semis = Match.objects.filter(
                event=selected_event, stage='semifinal', division=division, **cat_filter
            ).select_related('score', 'team_a', 'team_b')
            finals = list(Match.objects.filter(
                event=selected_event, stage__in=['final', 'third_place'], division=division, **cat_filter
            ).select_related('score', 'team_a', 'team_b'))
            event_data = {
                'format': fmt,
                'group_a': group_a,
                'group_b': group_b,
                'semis': semis,
                'finals': finals,
                'champion': _get_champion(finals),
            }

        elif fmt == 'hybrid':
            rr_standings = [{'rank': i, **e} for i, e in enumerate(
                get_event_standings(selected_event, 'round_robin',
                                    division=division, category=selected_category), start=1)]
            semis = Match.objects.filter(
                event=selected_event, stage='semifinal', division=division, **cat_filter
            ).select_related('score', 'team_a', 'team_b')
            finals = list(Match.objects.filter(
                event=selected_event, stage__in=['final', 'third_place'], division=division, **cat_filter
            ).select_related('score', 'team_a', 'team_b'))
            event_data = {
                'format': fmt,
                'rr_standings': rr_standings,
                'semis': semis,
                'finals': finals,
                'champion': _get_champion(finals),
            }

        else:  # group_knockout (fallback — treat unknown formats like group_knockout)
            group_a = [{'rank': i, **e} for i, e in enumerate(
                get_event_standings(selected_event, 'group', group_filter='A',
                                    division=division, category=selected_category), start=1)]
            group_b = [{'rank': i, **e} for i, e in enumerate(
                get_event_standings(selected_event, 'group', group_filter='B',
                                    division=division, category=selected_category), start=1)]
            semis = Match.objects.filter(
                event=selected_event, stage='semifinal', division=division, **cat_filter
            ).select_related('score', 'team_a', 'team_b')
            finals = list(Match.objects.filter(
                event=selected_event, stage__in=['final', 'third_place'], division=division, **cat_filter
            ).select_related('score', 'team_a', 'team_b'))
            event_data = {
                'format': fmt,
                'group_a': group_a,
                'group_b': group_b,
                'semis': semis,
                'finals': finals,
                'champion': _get_champion(finals),
            }

    return render(request, 'core/leaderboard.html', {
        'events': events,
        'selected_event': selected_event,
        'event_data': event_data,
        'active_tab': active_tab,
        'event_id': event_id,
        'division': division,
        'available_divisions': available_divisions,
        'categories': categories,
        'selected_category': selected_category,
        'category_id': category_id or (str(selected_category.pk) if selected_category else ''),
    })


# --- Overall Leaderboard ---

@login_required
def overall_leaderboard_view(request):
    from .result_service import get_overall_leaderboard
    raw = get_overall_leaderboard()
    standings = [{'rank': i, **entry} for i, entry in enumerate(raw, start=1)]
    return render(request, 'core/overall_leaderboard.html', {'standings': standings})
