from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .models import Department, Event, Match, Score, OrganizerAssignment, Season, MatchSet
from .models import departments_for_season
from .forms import EventForm, MatchForm, MatchEditForm, ScoreForm, OrganizerForm, OrganizerEditForm, DepartmentForm, SeasonForm, MatchSetScoreForm
from .decorators import role_required, active_season_required


def _get_selected_season(request):
    """
    Returns (selected_season, all_seasons).
    Priority: ?season_id= param → active season → most recent season → None.
    """
    all_seasons = Season.objects.order_by('-year', '-pk')
    season_id = request.GET.get('season_id') or request.session.get('season_id')
    selected = None
    if season_id:
        selected = Season.objects.filter(pk=season_id).first()
    if not selected:
        selected = Season.get_active()
    if not selected and all_seasons.exists():
        selected = all_seasons.first()
    # Store in session so it persists across pages
    if selected:
        request.session['season_id'] = selected.pk
    return selected, list(all_seasons)


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

@active_season_required
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
        .filter(event__season__is_active=True)
        .exclude(score__result_a='pending')
        .filter(score__isnull=False)
        .order_by('-score__updated_at')[:5]
    )

    # Upcoming matches — next 5 that haven't been played yet (no score or pending)
    upcoming_matches = (
        Match.objects.select_related('event', 'team_a', 'team_b')
        .filter(event__season__is_active=True)
        .filter(date_time__gte=now)
        .filter(Q(score__isnull=True) | Q(score__result_a='pending'))
        .order_by('date_time')[:5]
    )

    context = {
        'total_events': Event.objects.filter(season__is_active=True).count(),
        'total_matches': Match.objects.filter(event__season__is_active=True).count(),
        'completed_matches': Score.objects.filter(
            match__event__season__is_active=True
        ).exclude(result_a='pending').count(),
        'top_department': top_department,
        'recent_matches': recent_matches,
        'upcoming_matches': upcoming_matches,
    }
    return render(request, 'core/dashboard.html', context)


# --- 6.2 Departments ---

def _get_group_counts(season=None, exclude_pk=None):
    """
    Return a dict with counts of departments per group for the given season.
    Used to show balance warnings on the department form and list pages.
    exclude_pk: optionally exclude a department (used on the edit form so
                the current dept's existing group isn't double-counted).
    """
    qs = departments_for_season(season)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    count_a = qs.filter(group='A').count()
    count_b = qs.filter(group='B').count()
    unassigned = qs.filter(group__isnull=True).count()
    return {
        'A': count_a,
        'B': count_b,
        'unassigned': unassigned,
        'imbalanced': abs(count_a - count_b) > 1,
    }


def department_list(request):
    selected_season, all_seasons = _get_selected_season(request)
    departments = departments_for_season(selected_season).order_by('display_order')
    group_counts = _get_group_counts(season=selected_season)
    return render(request, 'core/departments.html', {
        'departments': departments,
        'group_counts': group_counts,
        'selected_season': selected_season,
        'all_seasons': all_seasons,
    })


@login_required
@role_required('admin')
def department_create(request):
    active_season = Season.get_active()
    form = DepartmentForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        dept = form.save()

        # Auto-sync: generate missing matches for this new department
        # across all existing events in the active season.
        if active_season:
            from .tournament_service import sync_department_into_season
            result = sync_department_into_season(dept, active_season)
            if result['created'] > 0:
                messages.success(
                    request,
                    f'Department "{dept.name}" added successfully. '
                    f'{result["created"]} new match{"es" if result["created"] != 1 else ""} '
                    f'generated across existing events.'
                )
            else:
                messages.success(request, f'Department "{dept.name}" added successfully.')
            for reason in result['skipped']:
                messages.warning(request, f'⚠️ Skipped: {reason}')
        else:
            messages.success(request, f'Department "{dept.name}" added successfully.')

        return redirect('department_list')
    return render(request, 'core/department_form.html', {
        'form': form,
        'action': 'Add',
        'group_counts': _get_group_counts(season=active_season),
        'active_season': active_season,
    })


@login_required
@role_required('admin')
def department_update(request, pk):
    dept = get_object_or_404(Department, pk=pk)
    active_season = Season.get_active()
    old_group = dept.group  # capture before form.save() overwrites it
    form = DepartmentForm(request.POST or None, request.FILES or None, instance=dept)
    if request.method == 'POST' and form.is_valid():
        form.save()

        # If the group assignment changed (e.g. None → 'A'), sync missing matches
        new_group = dept.group
        group_changed = old_group != new_group and new_group is not None
        if group_changed and active_season:
            from .tournament_service import sync_department_into_season
            result = sync_department_into_season(dept, active_season)
            if result['created'] > 0:
                messages.success(
                    request,
                    f'Department "{dept.name}" updated. '
                    f'{result["created"]} new match{"es" if result["created"] != 1 else ""} '
                    f'generated after group assignment change.'
                )
            else:
                messages.success(request, f'Department "{dept.name}" updated successfully.')
            for reason in result['skipped']:
                messages.warning(request, f'⚠️ Skipped: {reason}')
        else:
            messages.success(request, f'Department "{dept.name}" updated successfully.')

        return redirect('department_list')
    return render(request, 'core/department_form.html', {
        'form': form,
        'action': 'Edit',
        'dept': dept,
        'group_counts': _get_group_counts(season=active_season, exclude_pk=dept.pk),
        'active_season': active_season,
    })


@login_required
@role_required('admin')
def department_delete(request, pk):
    dept = get_object_or_404(Department, pk=pk)
    active_season = Season.get_active()

    if request.method == 'POST':
        if active_season:
            # Step 1 — delete all matches for this dept in the current season.
            # This clears the PROTECT constraint so the row can be deleted.
            # Past-season matches are untouched (event__season != active_season).
            current_season_matches = Match.objects.filter(
                event__season=active_season
            ).filter(
                Q(team_a=dept) | Q(team_b=dept)
            )
            match_count = current_season_matches.count()
            current_season_matches.delete()  # cascades Score, MatchSet automatically

            # Step 2 — remove any EventResult medals for this dept in the current season.
            from .models import EventResult
            EventResult.objects.filter(
                department=dept,
                event__season=active_season,
            ).delete()

        # Step 3 — attempt permanent deletion.
        # If the dept still has matches in OTHER seasons, PROTECT will raise
        # ProtectedError and we catch it gracefully.
        from django.db.models import ProtectedError
        name = dept.name
        try:
            dept.delete()
            if active_season and match_count:
                messages.success(
                    request,
                    f'Department "{name}" permanently deleted. '
                    f'{match_count} current-season match{"es" if match_count != 1 else ""} '
                    f'were removed automatically.'
                )
            else:
                messages.success(request, f'Department "{name}" permanently deleted.')
        except ProtectedError:
            # Department is referenced by matches in past seasons — cannot delete the row.
            # Current-season data was already cleaned up above; inform the admin.
            messages.error(
                request,
                f'"{name}" has matches in past seasons and cannot be fully deleted. '
                f'Current-season matches were removed. '
                f'To fully remove this department, delete all past-season events first.'
            )

    return redirect('department_list')


@login_required
@role_required('admin')
def department_sync(request, pk):
    """
    Manually sync a department into all existing events of the active season.
    Generates any missing matches involving this department.
    Safe to call multiple times — get_or_create prevents duplicates.
    """
    from .tournament_service import sync_department_into_season
    dept = get_object_or_404(Department, pk=pk)
    active_season = Season.get_active()

    if not active_season:
        messages.error(request, 'No active season found. Activate a season first.')
        return redirect('department_list')

    result = sync_department_into_season(dept, active_season)

    if result['created'] > 0:
        messages.success(
            request,
            f'Sync complete for "{dept.name}": '
            f'{result["created"]} new match{"es" if result["created"] != 1 else ""} generated.'
        )
    else:
        messages.info(request, f'"{dept.name}" is already fully synced — no missing matches found.')

    for reason in result['skipped']:
        messages.warning(request, f'⚠️ Skipped: {reason}')

    return redirect('department_list')


# --- 6.3 Event views ---

def event_list(request):
    from .models import OrganizerAssignment

    selected_season, all_seasons = _get_selected_season(request)

    qs = Event.objects.all().prefetch_related('organizer_assignments__organizer', 'categories')
    if selected_season:
        qs = qs.filter(season=selected_season)
    events = list(qs)

    # Build organizer labels per event as a plain dict {event.pk: [(name, label), ...]}
    organizer_labels = {}
    for event in events:
        seen_orgs = {}
        for a in event.organizer_assignments.all():
            org = a.organizer
            if org.pk not in seen_orgs:
                org_labels = _get_organizer_event_labels(org)
                label = next(
                    (lbl for lbl in org_labels
                     if lbl == event.name or lbl.startswith(event.name + ' (')),
                    event.name
                )
                seen_orgs[org.pk] = (org.get_full_name() or org.username, label)
        organizer_labels[event.pk] = list(seen_orgs.values())

    return render(request, 'core/events.html', {
        'events': events,
        'organizer_labels': organizer_labels,
        'selected_season': selected_season,
        'all_seasons': all_seasons,
    })


@login_required
@role_required('admin')
@active_season_required
def event_create(request):
    form = EventForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        event = form.save(commit=False)
        # Auto-assign to the active season
        event.season = Season.get_active()
        event.save()
        messages.success(request, f'Event "{event.name}" created successfully.')
        return redirect('event_list')
    return render(request, 'core/event_form.html', {'form': form, 'action': 'Create'})


@login_required
@role_required('admin')
@active_season_required
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
@active_season_required
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


def _get_organizer_event_labels(user):
    """
    Generate smart, summarized assignment labels for an organizer.

    Groups assignments by event, then applies these rules:
    - Full event (all cats + all divs, or no-category event with all divs) → "EventName"
    - All divisions, specific category → "EventName (Singles)"
    - Specific division, all categories → "EventName (Men)"
    - Specific category + specific division → "EventName (Singles - Men)"
    - No-category event, one division → "EventName (Men)"

    Returns a list of label strings, one per event.
    """
    from collections import defaultdict
    from .models import OrganizerAssignment, Event

    assignments = OrganizerAssignment.objects.filter(organizer=user).select_related('event')
    if not assignments.exists():
        return []

    # Group by event
    by_event = defaultdict(list)
    for a in assignments:
        by_event[a.event].append(a)

    labels = []
    for event, event_assignments in sorted(by_event.items(), key=lambda x: x[0].name):
        if event.has_categories:
            # Determine all possible categories for this event
            all_cats = set(event.categories.values_list('category_type', flat=True))
            # Determine all possible divisions (mixed cat only has mixed div)
            # For non-mixed cats: men + women; for mixed cat: mixed
            all_possible = set()
            for cat in all_cats:
                if cat == 'mixed':
                    all_possible.add(('mixed', 'mixed'))
                else:
                    if event.division_type in ('men', 'both'):
                        all_possible.add((cat, 'men'))
                    if event.division_type in ('women', 'both'):
                        all_possible.add((cat, 'women'))

            assigned = {(a.category_type, a.division) for a in event_assignments}
            assigned_cats = {a.category_type for a in event_assignments}
            assigned_divs = {a.division for a in event_assignments if a.division != 'mixed'}

            # Possible non-mixed divisions
            possible_divs = set()
            if event.division_type in ('men', 'both'):
                possible_divs.add('men')
            if event.division_type in ('women', 'both'):
                possible_divs.add('women')

            # Possible non-mixed categories
            possible_non_mixed_cats = {c for c in all_cats if c != 'mixed'}

            full_coverage = assigned >= all_possible

            if full_coverage:
                labels.append(event.name)
            else:
                all_divs_covered = possible_divs and possible_divs <= assigned_divs
                all_cats_covered = possible_non_mixed_cats and possible_non_mixed_cats <= assigned_cats

                if all_divs_covered and not all_cats_covered:
                    # All divisions, specific categories
                    cat_labels = sorted({
                        dict(OrganizerAssignment.CATEGORY_CHOICES).get(c, c)
                        for c in assigned_cats if c != 'mixed'
                    })
                    labels.append(f"{event.name} (All Division) ({', '.join(cat_labels)})")
                elif all_cats_covered and not all_divs_covered:
                    # All categories, specific divisions
                    div_labels = sorted({
                        dict(OrganizerAssignment.DIVISION_CHOICES).get(d, d)
                        for d in assigned_divs
                    })
                    labels.append(f"{event.name} ({', '.join(div_labels)}) (All Category)")
                else:
                    # Specific category + specific division — list each
                    for a in sorted(event_assignments, key=lambda x: (x.category_type or '', x.division or '')):
                        parts = []
                        if a.category_type:
                            parts.append(a.get_category_type_display())
                        if a.division:
                            parts.append(a.get_division_display())
                        if parts:
                            labels.append(f"{event.name} ({' '.join(parts)})")
                        else:
                            labels.append(event.name)
        else:
            # No-category event — only divisions matter
            assigned_divs = {a.division for a in event_assignments if a.division}
            possible_divs = set()
            if event.division_type in ('men', 'both'):
                possible_divs.add('men')
            if event.division_type in ('women', 'both'):
                possible_divs.add('women')

            if not possible_divs or assigned_divs >= possible_divs:
                labels.append(event.name)
            else:
                div_labels = sorted({
                    dict(OrganizerAssignment.DIVISION_CHOICES).get(d, d)
                    for d in assigned_divs
                })
                labels.append(f"{event.name} ({', '.join(div_labels)})")

    return labels


def _get_organizer_match_filter(user):
    """
    Build a Q filter that restricts matches to only those the organizer is assigned to.
    Checks OrganizerAssignment records for this user.
    Returns a Q object or None (meaning no restriction — admin/viewer).
    """
    assignments = OrganizerAssignment.objects.filter(organizer=user)
    if not assignments.exists():
        # No assignments at all — organizer sees nothing
        return Q(pk__in=[])

    q = Q()
    for a in assignments:
        cond = Q(event=a.event)
        if a.category_type:
            cond &= Q(category__category_type=a.category_type)
        if a.division:
            cond &= Q(division=a.division)
        q |= cond
    return q


def _is_organizer_allowed(user, match):
    """Return True if the organizer has an assignment covering this match."""
    assignments = OrganizerAssignment.objects.filter(organizer=user, event=match.event)
    if not assignments.exists():
        return False
    for a in assignments:
        cat_ok = (not a.category_type) or (
            match.category and match.category.category_type == a.category_type
        )
        div_ok = (not a.division) or (match.division == a.division)
        if cat_ok and div_ok:
            return True
    return False


@active_season_required
def match_list(request):
    q = request.GET.get('q', '').strip()
    is_organizer = (
        request.user.is_authenticated and
        hasattr(request.user, 'profile') and
        request.user.profile.role == 'organizer'
    )

    selected_season, all_seasons = _get_selected_season(request)

    matches = Match.objects.select_related(
        'event', 'team_a', 'team_b', 'category'
    ).order_by('event__name', 'category__category_type', 'division', 'stage', 'date_time')

    if selected_season:
        matches = matches.filter(event__season=selected_season)

    if is_organizer:
        matches = matches.filter(_get_organizer_match_filter(request.user))
    elif q:
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
        'query': q if not is_organizer else '',
        'has_auto_events': has_auto_events,
        'is_organizer': is_organizer,
        'selected_season': selected_season,
        'all_seasons': all_seasons,
    })


@login_required
@role_required('admin', 'organizer')
@active_season_required
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
@active_season_required
def match_update(request, pk):
    match = get_object_or_404(Match, pk=pk)

    # Organizers can only edit matches they are assigned to
    if request.user.profile.role == 'organizer' and not _is_organizer_allowed(request.user, match):
        messages.error(request, 'You do not have permission to edit this match.')
        return redirect('match_list')

    form = MatchEditForm(request.POST or None, instance=match)
    if request.method == 'POST' and form.is_valid():
        old_best_of = match.best_of
        new_best_of = form.cleaned_data.get('best_of')

        # Save the match (best_of is now part of the form)
        match.team_a = form.cleaned_data['team_a']
        match.team_b = form.cleaned_data['team_b']
        match.date_time = form.cleaned_data['date_time']
        match.venue = form.cleaned_data['venue']
        match.best_of = new_best_of
        match.save()

        # Sync MatchSet records when best_of changes
        if new_best_of:
            existing_sets = set(match.sets.values_list('set_number', flat=True))
            for n in range(1, new_best_of + 1):
                if n not in existing_sets:
                    MatchSet.objects.create(match=match, set_number=n)
            # Remove sets beyond the new best_of
            match.sets.filter(set_number__gt=new_best_of).delete()
        else:
            # Switched to normal scoring — remove all sets
            match.sets.all().delete()

        messages.success(request, f'{match.team_a.abbreviation} vs {match.team_b.abbreviation} updated successfully.')
        return redirect('match_list')
    return render(request, 'core/match_form.html', {'form': form, 'action': 'Edit', 'match': match})


@login_required
@role_required('admin', 'organizer')
@active_season_required
def set_score_update(request, pk):
    """Enter/edit scores for each set of a set-based match."""
    from .tournament_service import get_stage_lock_reason
    match = get_object_or_404(Match, pk=pk)

    if not match.best_of:
        messages.error(request, 'This match does not use set-based scoring.')
        return redirect('results_list')

    if request.user.profile.role == 'organizer' and not _is_organizer_allowed(request.user, match):
        messages.error(request, 'You do not have permission to enter scores for this match.')
        return redirect('results_list')

    # Stage lock — block edits when the next knockout stage is already generated
    lock_reason = get_stage_lock_reason(match)
    if lock_reason:
        messages.error(request, lock_reason)
        return redirect('results_list')

    match_sets = list(match.sets.order_by('set_number'))

    if request.method == 'POST':
        form = MatchSetScoreForm(request.POST, match_sets=match_sets)
        if form.is_valid():
            for ms in match_sets:
                ms.score_a = form.cleaned_data[f'score_a_{ms.set_number}']
                ms.score_b = form.cleaned_data[f'score_b_{ms.set_number}']
                ms.save()

            # Compute sets won and update the main Score record
            sets_won_a = sum(1 for ms in match_sets if ms.score_a > ms.score_b)
            sets_won_b = sum(1 for ms in match_sets if ms.score_b > ms.score_a)

            score, _ = Score.objects.get_or_create(match=match)
            score.score_a = sets_won_a
            score.score_b = sets_won_b
            score.compute_result()
            score.save()

            messages.success(
                request,
                f'Set scores saved. Result: {match.team_a.abbreviation} {sets_won_a}–{sets_won_b} {match.team_b.abbreviation}'
            )
            return redirect('results_list')
    else:
        form = MatchSetScoreForm(match_sets=match_sets)

    return render(request, 'core/set_score_form.html', {
        'form': form,
        'match': match,
        'match_sets': match_sets,
    })


@login_required
@role_required('admin')
@active_season_required
def match_delete(request, pk):
    match = get_object_or_404(Match, pk=pk)
    if request.method == 'POST':
        label = f'{match.team_a.abbreviation} vs {match.team_b.abbreviation}'
        match.delete()
        messages.success(request, f'Match "{label}" deleted.')
    return redirect('match_list')


# --- 6.5 Score views ---

def results_list(request):
    from .tournament_service import get_stage_lock_reason
    q = request.GET.get('q', '').strip()
    is_organizer = (
        request.user.is_authenticated and
        hasattr(request.user, 'profile') and
        request.user.profile.role == 'organizer'
    )

    selected_season, all_seasons = _get_selected_season(request)

    matches = Match.objects.select_related(
        'score', 'team_a', 'team_b', 'event', 'category'
    ).order_by('event__name', 'category__category_type', 'division', 'stage', 'date_time')

    if selected_season:
        matches = matches.filter(event__season=selected_season)

    if is_organizer:
        matches = matches.filter(_get_organizer_match_filter(request.user))
    elif q:
        matches = matches.filter(
            Q(event__name__icontains=q) |
            Q(team_a__name__icontains=q) |
            Q(team_b__name__icontains=q) |
            Q(venue__icontains=q)
        )

    # Build the set of locked match PKs so the template can disable edit buttons
    locked_match_pks = set()
    for m in matches:
        if get_stage_lock_reason(m):
            locked_match_pks.add(m.pk)

    event_groups = _build_event_groups(matches)
    return render(request, 'core/results.html', {
        'event_groups': event_groups,
        'query': q if not is_organizer else '',
        'is_organizer': is_organizer,
        'selected_season': selected_season,
        'all_seasons': all_seasons,
        'locked_match_pks': locked_match_pks,
    })


@login_required
@role_required('admin', 'organizer')
@active_season_required
def score_update(request, pk):
    from .tournament_service import get_stage_lock_reason
    match = get_object_or_404(Match, pk=pk)

    # Organizers can only enter scores for their assigned matches
    if request.user.profile.role == 'organizer' and not _is_organizer_allowed(request.user, match):
        messages.error(request, 'You do not have permission to enter scores for this match.')
        return redirect('results_list')

    # Stage lock — block edits when the next knockout stage is already generated
    lock_reason = get_stage_lock_reason(match)
    if lock_reason:
        messages.error(request, lock_reason)
        return redirect('results_list')
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

def leaderboard_view(request):
    from .tournament_service import get_event_standings
    from .models import EventCategory

    selected_season, all_seasons = _get_selected_season(request)

    events = Event.objects.order_by('name')
    if selected_season:
        events = events.filter(season=selected_season)
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

            # Mixed category has no division — treat as a single undivided group
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
        'selected_season': selected_season,
        'all_seasons': all_seasons,
    })


# --- Overall Leaderboard ---

def overall_leaderboard_view(request):
    from .result_service import get_overall_leaderboard

    selected_season, all_seasons = _get_selected_season(request)

    raw = get_overall_leaderboard(season=selected_season)
    standings = [{'rank': i, **entry} for i, entry in enumerate(raw, start=1)]
    return render(request, 'core/overall_leaderboard.html', {
        'standings': standings,
        'selected_season': selected_season,
        'all_seasons': all_seasons,
    })


# --- Organizer Management (admin only) ---

@login_required
@role_required('admin')
def organizer_list(request):
    """List all organizer accounts with smart assignment labels filtered by active season."""
    from django.contrib.auth.models import User
    organizers = User.objects.filter(profile__role='organizer').select_related('profile').order_by('username')
    active_season = Season.get_active()

    # Pre-compute labels for each organizer, filtered to the active season only.
    # Historical assignments from past seasons are preserved in the DB but not shown here.
    organizer_data = []
    for org in organizers:
        if active_season:
            # Only include assignments whose event belongs to the active season
            season_assignments = org.assignments.filter(event__season=active_season)
            if season_assignments.exists():
                labels = _get_organizer_event_labels(org)
                # Filter labels to only those matching active-season events
                active_event_names = set(
                    season_assignments.values_list('event__name', flat=True)
                )
                labels = [
                    lbl for lbl in labels
                    if any(lbl == name or lbl.startswith(name + ' (') for name in active_event_names)
                ]
            else:
                labels = []
        else:
            labels = []
        organizer_data.append({'user': org, 'labels': labels})

    return render(request, 'core/organizers.html', {
        'organizer_data': organizer_data,
        'active_season': active_season,
    })


@login_required
@role_required('admin')
def organizer_create(request):
    """Admin creates a new organizer account."""
    from django.contrib.auth.models import User

    form = OrganizerForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = User.objects.create_user(
            username=form.cleaned_data['username'],
            password=form.cleaned_data['password'],
            first_name=form.cleaned_data.get('first_name', ''),
            last_name=form.cleaned_data.get('last_name', ''),
        )
        # post_save signal creates UserProfile with role='organizer' automatically
        # explicitly set to be safe
        user.profile.role = 'organizer'
        user.profile.save()
        messages.success(request, f'Organizer account "{user.username}" created successfully.')
        return redirect('organizer_list')
    return render(request, 'core/organizer_form.html', {'form': form})


@login_required
@role_required('admin')
def organizer_delete(request, pk):
    """Admin deletes an organizer account."""
    from django.contrib.auth.models import User
    user = get_object_or_404(User, pk=pk, profile__role='organizer')
    if request.method == 'POST':
        username = user.username
        user.delete()
        messages.success(request, f'Organizer account "{username}" deleted.')
    return redirect('organizer_list')


@login_required
@role_required('admin')
def organizer_edit(request, pk):
    """Admin edits an organizer account and assigns granular event/category/division access."""
    from django.contrib.auth.models import User

    user = get_object_or_404(User, pk=pk, profile__role='organizer')

    # Only show events from the active season — no cross-season assignments
    active_season = Season.get_active()
    events = Event.objects.filter(
        season=active_season
    ).order_by('name').prefetch_related('categories') if active_season else Event.objects.none()

    if request.method == 'POST':
        from .forms import OrganizerEditForm
        form = OrganizerEditForm(request.POST, instance=user)
        if form.is_valid():
            user.username = form.cleaned_data['username']
            user.first_name = form.cleaned_data.get('first_name', '')
            user.last_name = form.cleaned_data.get('last_name', '')
            new_pw = form.cleaned_data.get('password')
            if new_pw:
                user.set_password(new_pw)
            user.save()

            # Delete all existing assignments for this organizer
            OrganizerAssignment.objects.filter(organizer=user).delete()
            # Also clear the old event-level organizer FK
            Event.objects.filter(organizer=user).update(organizer=None)

            # Parse granular assignments from POST data and check for conflicts
            created_events = set()
            conflict_labels = []
            assignments_to_create = []

            for key in request.POST:
                if not key.startswith('assign_'):
                    continue
                parts = key[len('assign_'):].split('_', 2)
                if len(parts) != 3:
                    continue
                event_pk_str, cat, div = parts
                try:
                    event_obj = Event.objects.get(pk=int(event_pk_str))
                except (Event.DoesNotExist, ValueError):
                    continue
                # Backend guard: only allow events from the active season
                if active_season and event_obj.season_id != active_season.pk:
                    continue
                assignments_to_create.append((event_obj, cat or None, div or None))

            # Check if any slot is already taken by another organizer
            for event_obj, cat, div in assignments_to_create:
                conflict = OrganizerAssignment.objects.filter(
                    event=event_obj,
                    category_type=cat,
                    division=div,
                ).exclude(organizer=user).first()
                if conflict:
                    # Build a readable label for the conflict
                    parts = []
                    if cat:
                        parts.append(dict(OrganizerAssignment.CATEGORY_CHOICES).get(cat, cat))
                    if div:
                        parts.append(dict(OrganizerAssignment.DIVISION_CHOICES).get(div, div))
                    label = f"{event_obj.name}"
                    if parts:
                        label += f" ({' - '.join(parts)})"
                    conflict_labels.append(
                        f"{label} → already assigned to {conflict.organizer.username}"
                    )

            if conflict_labels:
                for msg in conflict_labels:
                    messages.error(request, f"Conflict: {msg}")
                # Re-render with errors
                form2 = OrganizerEditForm(request.POST, instance=user)
                existing = set()
                for a in OrganizerAssignment.objects.filter(organizer=user):
                    existing.add(f"{a.event_id}_{a.category_type or ''}_{a.division or ''}")
                return render(request, 'core/organizer_edit.html', {
                    'form': form2,
                    'organizer': user,
                    'events': events,
                    'existing_assignments': existing,
                    'active_season': active_season,
                })

            # No conflicts — save all assignments
            for event_obj, cat, div in assignments_to_create:
                OrganizerAssignment.objects.get_or_create(
                    organizer=user,
                    event=event_obj,
                    category_type=cat,
                    division=div,
                )
                created_events.add(event_obj)

            # Set the event-level organizer FK for backward compatibility
            for ev in created_events:
                ev.organizer = user
                ev.save()

            messages.success(request, f'Organizer "{user.username}" updated successfully.')
            return redirect('organizer_list')
    else:
        from .forms import OrganizerEditForm
        form = OrganizerEditForm(instance=user)

    # Build existing assignments for template pre-selection
    existing = set()
    for a in OrganizerAssignment.objects.filter(organizer=user):
        existing.add(f"{a.event_id}_{a.category_type or ''}_{a.division or ''}")

    # Build taken slots (assigned to OTHER organizers) — shown as disabled
    taken = set()
    for a in OrganizerAssignment.objects.exclude(organizer=user):
        taken.add(f"{a.event_id}_{a.category_type or ''}_{a.division or ''}_taken")

    return render(request, 'core/organizer_edit.html', {
        'form': form,
        'organizer': user,
        'events': events,
        'existing_assignments': existing,
        'taken_slots': taken,
        'active_season': active_season,
    })


# --- Season Management (admin only) ---

@login_required
@role_required('admin')
def season_list(request):
    seasons = Season.objects.order_by('-year', '-pk')
    return render(request, 'core/seasons.html', {'seasons': seasons})


@login_required
@role_required('admin')
def season_create(request):
    form = SeasonForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        season = form.save()
        copy_from = form.cleaned_data.get('copy_from_season')

        if copy_from:
            # Evaluate ALL source events into a list BEFORE creating any new events.
            # This prevents the queryset from being affected by new records created
            # during the loop (post_save signals create matches which could interfere).
            source_events = list(copy_from.events.prefetch_related('categories').all())
            total_source = len(source_events)
            copied_count = 0
            failed_count = 0

            for src in source_events:
                try:
                    # Create a fresh event — organizer is explicitly None (not copied)
                    Event.objects.create(
                        name=src.name,
                        format=src.format,
                        division_type=src.division_type,
                        has_categories=src.has_categories,
                        season=season,
                        organizer=None,  # explicitly reset — must be reassigned
                    )
                    copied_count += 1
                except Exception as e:
                    failed_count += 1
                    import logging
                    logging.getLogger(__name__).error(
                        f"season_create: failed to copy event '{src.name}' — {e}"
                    )

            if failed_count == 0:
                messages.success(
                    request,
                    f'Season "{season.name}" created. '
                    f'All {copied_count}/{total_source} events copied from '
                    f'"{copy_from.name}" and matches auto-generated. '
                    f'No organizers assigned.'
                )
            else:
                messages.warning(
                    request,
                    f'Season "{season.name}" created. '
                    f'{copied_count}/{total_source} events copied from "{copy_from.name}". '
                    f'{failed_count} event(s) failed — check server logs.'
                )
        else:
            messages.success(request, f'Season "{season.name}" created successfully.')

        return redirect('season_list')
    return render(request, 'core/season_form.html', {'form': form, 'action': 'Create'})


@login_required
@role_required('admin')
def season_update(request, pk):
    season = get_object_or_404(Season, pk=pk)
    form = SeasonForm(request.POST or None, instance=season)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Season "{season.name}" updated.')
        return redirect('season_list')
    return render(request, 'core/season_form.html', {'form': form, 'action': 'Edit', 'season': season})


@login_required
@role_required('admin')
def season_delete(request, pk):
    season = get_object_or_404(Season, pk=pk)
    if request.method == 'POST':
        if season.events.exists():
            messages.error(request, f'Cannot delete "{season.name}" — it has events. Delete or reassign them first.')
            return redirect('season_list')
        name = season.name
        season.delete()
        messages.success(request, f'Season "{name}" deleted.')
    return redirect('season_list')


def season_switch(request, pk):
    """Switch the active season context (stored in session). Available to all users."""
    season = get_object_or_404(Season, pk=pk)
    request.session['season_id'] = season.pk
    # Redirect back to the referring page
    next_url = request.GET.get('next') or request.META.get('HTTP_REFERER') or '/'
    return redirect(next_url)


# --- Real-time notification API (AJAX polling) ---

def latest_result_api(request):
    """
    Returns the most recently scored match result as JSON.
    Polled every 5 seconds by the frontend to show real-time toast notifications.
    Accessible to all users (admin, organizer, viewer).
    """
    from django.http import JsonResponse
    from .templatetags.score_filters import score_display as fmt_score

    last = (
        Score.objects.select_related('match__event', 'match__team_a', 'match__team_b')
        .exclude(result_a='pending')
        .order_by('-updated_at')
        .first()
    )

    if not last:
        return JsonResponse({'has_result': False})

    match = last.match
    if last.result_a == 'win':
        winner = match.team_a.abbreviation
        msg = f'🏆 {match.team_a.abbreviation} {fmt_score(last.score_a)}–{fmt_score(last.score_b)} {match.team_b.abbreviation} — {match.event.name}'
    elif last.result_a == 'loss':
        winner = match.team_b.abbreviation
        msg = f'🏆 {match.team_b.abbreviation} {fmt_score(last.score_b)}–{fmt_score(last.score_a)} {match.team_a.abbreviation} — {match.event.name}'
    else:
        msg = f'🤝 Draw: {match.team_a.abbreviation} {fmt_score(last.score_a)}–{fmt_score(last.score_b)} {match.team_b.abbreviation} — {match.event.name}'

    return JsonResponse({
        'has_result': True,
        'score_id': last.pk,
        'updated_at': last.updated_at.isoformat(),
        'message': msg,
        'type': 'success' if last.result_a != 'draw' else 'info',
    })
