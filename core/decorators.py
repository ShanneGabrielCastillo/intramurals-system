from functools import wraps
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.contrib import messages


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not hasattr(request.user, 'profile') or request.user.profile.role not in roles:
                return HttpResponseForbidden("You do not have permission to access this page.")
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def active_season_required(view_func):
    """
    Blocks access to write/edit views when the user is viewing a past (non-active) season.
    Redirects to the events list with an informational message.
    Applied to: dashboard, schedule, match create/edit/delete, score entry, event create/edit/delete.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        season_id = request.session.get('season_id')
        if season_id:
            from .models import Season
            season = Season.objects.filter(pk=season_id).first()
            if season and not season.is_active:
                messages.info(
                    request,
                    f'"{season.name}" is a past season. Switch to the active season to make changes.'
                )
                return redirect('event_list')
        return view_func(request, *args, **kwargs)
    return wrapper
