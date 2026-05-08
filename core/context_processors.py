from .models import Season


def season_context(request):
    """
    Makes season data available in every template automatically.
    Reads the selected season from the session.
    Also sets viewing_past_season=True when the selected season is not active.
    """
    all_seasons = list(Season.objects.order_by('-year', '-pk'))
    season_id = request.session.get('season_id')
    selected = None
    if season_id:
        selected = next((s for s in all_seasons if s.pk == season_id), None)
    if not selected:
        selected = next((s for s in all_seasons if s.is_active), None)
    if not selected and all_seasons:
        selected = all_seasons[0]

    viewing_past = bool(selected and not selected.is_active)

    return {
        'all_seasons': all_seasons,
        'selected_season': selected,
        'viewing_past_season': viewing_past,
    }
