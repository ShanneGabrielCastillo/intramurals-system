from django.contrib import admin
from django.utils.html import format_html
from .models import UserProfile, Department, Event, Match, Score, EventResult


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('display_order', 'abbreviation', 'name', 'group', 'created_season', 'logo_preview')
    list_display_links = ('abbreviation', 'name')
    list_filter = ('group', 'created_season')
    ordering = ('display_order',)
    readonly_fields = ('logo_preview',)

    def logo_preview(self, obj):
        if obj.logo:
            return format_html(
                '<img src="{}" style="width:50px; height:50px; object-fit:contain; '
                'border-radius:50%; background:#f0f0f0; padding:3px;" />',
                obj.logo.url
            )
        return '—'
    logo_preview.short_description = 'Logo Preview'


admin.site.register(UserProfile)
admin.site.register(Event)
admin.site.register(Match)
admin.site.register(Score)
admin.site.register(EventResult)
