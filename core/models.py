from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('organizer', 'Organizer'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='organizer')

    def __str__(self):
        return f"{self.user.username} ({self.role})"


class Season(models.Model):
    """
    Represents one intramural year/season.
    Only ONE season should be active at a time.
    All events belong to a season, keeping historical data isolated.
    """
    name = models.CharField(max_length=100, help_text='e.g. "2026 Intramurals"')
    year = models.PositiveIntegerField()
    is_active = models.BooleanField(
        default=False,
        help_text='Only one season should be active at a time. '
                  'Setting this active will deactivate all others.',
    )

    class Meta:
        ordering = ['-year', '-pk']

    def save(self, *args, **kwargs):
        # Enforce single active season: deactivate all others when this is set active
        if self.is_active:
            Season.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({'Active' if self.is_active else str(self.year)})"

    @classmethod
    def get_active(cls):
        return cls.objects.filter(is_active=True).first()


class Department(models.Model):
    GROUP_CHOICES = [
        ('A', 'Group A'),
        ('B', 'Group B'),
    ]

    name = models.CharField(max_length=100)
    abbreviation = models.CharField(max_length=10)
    display_order = models.PositiveIntegerField()
    logo = models.ImageField(
        upload_to='department_logos/',
        null=True,
        blank=True,
        help_text='Upload department logo (PNG or JPG recommended)',
    )
    group = models.CharField(
        max_length=1,
        choices=GROUP_CHOICES,
        null=True,
        blank=True,
        default=None,
        help_text='Assign to Group A or Group B for Group Knockout events. '
                  'Leave blank if this department does not participate in Group Knockout.',
    )
    created_season = models.ForeignKey(
        'Season',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='departments',
        help_text='The first season this department officially exists in. '
                  'Auto-set to the active season when the department is created. '
                  'The department will not appear in seasons before this one.',
    )

    class Meta:
        ordering = ['display_order']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Auto-assign created_season to the active season on first creation
        if self._state.adding and self.created_season_id is None:
            active = Season.get_active()
            if active:
                self.created_season = active
        super().save(*args, **kwargs)


def departments_for_season(season):
    """
    Return a queryset of departments that existed during the given season.

    Visibility rule:
      - created_season year <= season year  (or created_season is NULL)

    A department created in 2027 is invisible in 2026.
    Deleted departments are gone from the DB entirely — past match FKs
    are protected by Match.team_a/team_b using on_delete=PROTECT, so
    deletion is only allowed after current-season matches are removed first.

    If season is None, returns all departments.
    """
    if season is None:
        return Department.objects.all()
    return Department.objects.filter(
        models.Q(created_season__year__lte=season.year) |
        models.Q(created_season__isnull=True)
    )


class Event(models.Model):
    FORMAT_CHOICES = [
        ('hybrid', 'Hybrid'),
        ('group_knockout', 'Group Knockout'),
    ]
    DIVISION_TYPE_CHOICES = [
        ('men', 'Men Only'),
        ('women', 'Women Only'),
        ('both', 'Both Divisions'),
    ]
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    format = models.CharField(
        max_length=20,
        choices=FORMAT_CHOICES,
        default='hybrid',
    )
    division_type = models.CharField(
        max_length=10,
        choices=DIVISION_TYPE_CHOICES,
        default='both',
        help_text='Which division(s) this event is played in.',
    )
    has_categories = models.BooleanField(
        default=False,
        help_text='Enable for sports with multiple categories (e.g. Badminton: Singles, Doubles, Mixed). '
                  'When enabled, standings are shown per category + division.',
    )
    organizer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_events',
        help_text='Organizer assigned to manage this event.',
    )
    season = models.ForeignKey(
        'Season',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='events',
        help_text='Season this event belongs to.',
    )

    def __str__(self):
        return self.name


class EventCategory(models.Model):
    """
    Optional sub-categories for an event (e.g. Badminton Singles, Doubles, Mixed).
    Category = Singles / Doubles / Mixed  (the TYPE of play)
    Division = Men / Women / Mixed        (who plays — set on the Match)
    Mixed category forces division='mixed' on its matches.
    """
    CATEGORY_CHOICES = [
        ('singles', 'Singles'),
        ('doubles', 'Doubles'),
        ('mixed', 'Mixed'),
    ]
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=50)
    category_type = models.CharField(max_length=20, choices=CATEGORY_CHOICES)

    class Meta:
        ordering = ['category_type']
        unique_together = [('event', 'category_type')]

    def __str__(self):
        return f"{self.event.name} — {self.get_category_type_display()}"


class Match(models.Model):
    STAGE_CHOICES = [
        ('round_robin', 'Round Robin'),
        ('group', 'Group Stage'),
        ('semifinal', 'Semifinal'),
        ('final', 'Final'),
        ('third_place', '3rd Place Match'),
    ]
    GROUP_CHOICES = [
        ('A', 'Group A'),
        ('B', 'Group B'),
    ]
    DIVISION_CHOICES = [
        ('men', 'Men'),
        ('women', 'Women'),
        ('mixed', 'Mixed'),
    ]
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='matches')
    team_a = models.ForeignKey(Department, on_delete=models.PROTECT, related_name='home_matches')
    team_b = models.ForeignKey(Department, on_delete=models.PROTECT, related_name='away_matches')
    date_time = models.DateTimeField()
    venue = models.CharField(max_length=200)
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES, default='round_robin')
    group = models.CharField(
        max_length=1,
        choices=GROUP_CHOICES,
        null=True,
        blank=True,
        default=None,
    )
    division = models.CharField(
        max_length=10,
        choices=DIVISION_CHOICES,
        default='men',
    )
    category = models.ForeignKey(
        'EventCategory',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='matches',
    )
    best_of = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Number of sets (e.g. 3, 5, 7). Leave blank for normal scoring.',
    )

    class Meta:
        ordering = ['date_time']
        unique_together = [('event', 'team_a', 'team_b', 'stage', 'division', 'category')]

    def __str__(self):
        return f"{self.team_a} vs {self.team_b} — {self.event}"


class MatchSet(models.Model):
    """
    Stores the score for one individual set within a match.
    Only used when match.best_of is set.
    The match's overall Score (sets won) is computed from these records.
    """
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='sets')
    set_number = models.PositiveIntegerField()
    score_a = models.PositiveIntegerField(default=0, help_text='Points scored by Team A in this set')
    score_b = models.PositiveIntegerField(default=0, help_text='Points scored by Team B in this set')

    class Meta:
        ordering = ['set_number']
        unique_together = [('match', 'set_number')]

    def __str__(self):
        return f"Set {self.set_number}: {self.match.team_a.abbreviation} {self.score_a}–{self.score_b} {self.match.team_b.abbreviation}"


class Score(models.Model):
    RESULT_CHOICES = [
        ('win', 'Win'),
        ('loss', 'Loss'),
        ('draw', 'Draw'),
        ('pending', 'Pending'),
    ]
    match = models.OneToOneField(Match, on_delete=models.CASCADE, related_name='score')
    # DecimalField used instead of FloatField to avoid binary floating-point rounding errors.
    # max_digits=5, decimal_places=2 supports scores like 0.5, 2.5, 99.99, 100.00
    score_a = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    score_b = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    result_a = models.CharField(max_length=10, choices=RESULT_CHOICES, default='pending')
    result_b = models.CharField(max_length=10, choices=RESULT_CHOICES, default='pending')
    updated_at = models.DateTimeField(auto_now=True)  # set automatically on every save

    def compute_result(self):
        if self.score_a > self.score_b:
            self.result_a, self.result_b = 'win', 'loss'
        elif self.score_b > self.score_a:
            self.result_a, self.result_b = 'loss', 'win'
        else:
            self.result_a = self.result_b = 'draw'

    def __str__(self):
        return f"Score for {self.match}: {self.score_a}-{self.score_b}"


# --- Signals ---

from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance, role='organizer')


class OrganizerAssignment(models.Model):
    """
    Granular assignment of an organizer to a specific event + category + division.
    An organizer can only manage matches that match ALL three criteria.

    category: None means "all categories" (for non-category events)
    division: None means "all divisions"
    """
    DIVISION_CHOICES = [
        ('men', 'Men'),
        ('women', 'Women'),
        ('mixed', 'Mixed'),
    ]
    CATEGORY_CHOICES = [
        ('singles', 'Singles'),
        ('doubles', 'Doubles'),
        ('mixed', 'Mixed'),
    ]
    organizer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='assignments',
    )
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='organizer_assignments',
    )
    category_type = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        null=True,
        blank=True,
        help_text='Leave blank to assign all categories of this event.',
    )
    division = models.CharField(
        max_length=10,
        choices=DIVISION_CHOICES,
        null=True,
        blank=True,
        help_text='Leave blank to assign all divisions of this event.',
    )

    class Meta:
        unique_together = [
            ('organizer', 'event', 'category_type', 'division'),  # one organizer per combination
            ('event', 'category_type', 'division'),               # only ONE organizer per event+cat+div
        ]
        ordering = ['event__name', 'category_type', 'division']

    def label(self):
        """Human-readable label like 'Badminton (Singles - Men)'."""
        parts = []
        if self.category_type:
            parts.append(self.get_category_type_display())
        if self.division:
            parts.append(self.get_division_display())
        if parts:
            return f"{self.event.name} ({' - '.join(parts)})"
        return self.event.name

    def __str__(self):
        return f"{self.organizer.username} → {self.label()}"


# --- EventResult ---

class EventResult(models.Model):
    """
    Stores a department's final finishing position in an event per division.
    position: 1 = Gold, 2 = Silver, 3 = Bronze
    division: 'men' or 'women'
    Auto-populated by result_service.save_event_results() via post_save signal on Score.
    """
    DIVISION_CHOICES = [
        ('men', 'Men'),
        ('women', 'Women'),
    ]
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='results')
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='event_results')
    position = models.PositiveIntegerField()  # 1=Gold, 2=Silver, 3=Bronze
    division = models.CharField(
        max_length=10,
        choices=DIVISION_CHOICES,
        default='men',
    )

    class Meta:
        unique_together = [
            ('event', 'department', 'division'),  # one position per department per event per division
            ('event', 'position', 'division'),    # one department per position per event per division
        ]

    def __str__(self):
        medals = {1: 'Gold', 2: 'Silver', 3: 'Bronze'}
        return f"{self.department} — {medals.get(self.position, str(self.position))} ({self.division}) in {self.event}"
