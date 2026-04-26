from django.contrib import admin
from .models import UserProfile, Department, Event, Match, Score, EventResult

admin.site.register(UserProfile)
admin.site.register(Department)
admin.site.register(Event)
admin.site.register(Match)
admin.site.register(Score)
admin.site.register(EventResult)
