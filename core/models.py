from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('organizer', 'Organizer'),
        ('student', 'Student'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    def __str__(self):
        return f"{self.user.username} ({self.role})"


class Department(models.Model):
    name = models.CharField(max_length=100)
    abbreviation = models.CharField(max_length=10)
    display_order = models.PositiveIntegerField()

    class Meta:
        ordering = ['display_order']

    def __str__(self):
        return self.name


class Event(models.Model):
    FORMAT_CHOICES = [
        ('round_robin', 'Round Robin'),
        ('hybrid', 'Hybrid'),
        ('group_knockout', 'Group Knockout'),
    ]
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    format = models.CharField(
        max_length=20,
        choices=FORMAT_CHOICES,
        default='round_robin',
    )

    def __str__(self):
        return self.name


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

    class Meta:
        ordering = ['date_time']
        unique_together = [('event', 'team_a', 'team_b', 'stage', 'division')]

    def __str__(self):
        return f"{self.team_a} vs {self.team_b} — {self.event}"


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
        UserProfile.objects.create(user=instance, role='student')


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
