from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from .models import Event, Match, Score, Department, Season, MatchSet


class SeasonForm(forms.ModelForm):
    # Optional: copy events from a previous season
    copy_from_season = forms.ModelChoiceField(
        queryset=Season.objects.none(),  # populated in __init__
        required=False,
        label='Copy Events From Season',
        empty_label='— Do not copy events —',
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text='Select a previous season to copy its events into this new season.',
    )

    class Meta:
        model = Season
        fields = ['name', 'year', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 2026 Intramurals'}),
            'year': forms.NumberInput(attrs={'class': 'form-control', 'min': '2000'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show existing seasons in the copy-from dropdown
        self.fields['copy_from_season'].queryset = Season.objects.order_by('-year', '-pk')

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise ValidationError('Season name cannot be blank.')
        return name


class OrganizerForm(forms.Form):
    """Form for admin to create an organizer account."""
    first_name = forms.CharField(
        max_length=150, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First name (optional)'}),
    )
    last_name = forms.CharField(
        max_length=150, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last name (optional)'}),
    )
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'}),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'}),
    )
    confirm_password = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm password'}),
    )

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if not username:
            raise ValidationError('Username cannot be blank.')
        if User.objects.filter(username=username).exists():
            raise ValidationError('This username is already taken.')
        return username

    def clean(self):
        cleaned_data = super().clean()
        pw = cleaned_data.get('password')
        cpw = cleaned_data.get('confirm_password')
        if pw and cpw and pw != cpw:
            raise ValidationError('Passwords do not match.')
        return cleaned_data


class OrganizerEditForm(forms.Form):
    """Form for admin to edit an organizer account. Password is optional."""
    first_name = forms.CharField(
        max_length=150, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    last_name = forms.CharField(
        max_length=150, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    password = forms.CharField(
        required=False,
        label='New Password',
        help_text='Leave blank to keep the current password.',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Leave blank to keep current'}),
    )
    confirm_password = forms.CharField(
        required=False,
        label='Confirm New Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm new password'}),
    )
    assigned_events = forms.ModelMultipleChoiceField(
        queryset=Event.objects.all().order_by('name'),
        required=False,
        label='Assigned Events',
        widget=forms.CheckboxSelectMultiple(),
        help_text='Select the events this organizer is allowed to manage.',
    )

    def __init__(self, *args, instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance  # the User being edited
        if instance:
            self.fields['username'].initial = instance.username
            self.fields['first_name'].initial = instance.first_name
            self.fields['last_name'].initial = instance.last_name
            self.fields['assigned_events'].initial = Event.objects.filter(organizer=instance)

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if not username:
            raise ValidationError('Username cannot be blank.')
        qs = User.objects.filter(username=username)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError('This username is already taken.')
        return username

    def clean(self):
        cleaned_data = super().clean()
        pw = cleaned_data.get('password')
        cpw = cleaned_data.get('confirm_password')
        if pw and cpw and pw != cpw:
            raise ValidationError('Passwords do not match.')
        return cleaned_data


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'abbreviation', 'display_order', 'logo', 'group']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. College of Arts and Sciences'}),
            'abbreviation': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. CAS'}),
            'display_order': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'logo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'group': forms.Select(attrs={'class': 'form-control'}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise ValidationError('Department name cannot be blank.')
        return name

    def clean_abbreviation(self):
        abbr = self.cleaned_data.get('abbreviation', '').strip().upper()
        if not abbr:
            raise ValidationError('Abbreviation cannot be blank.')
        return abbr


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ['name', 'format', 'division_type', 'has_categories']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'format': forms.Select(attrs={'class': 'form-control'}),
            'division_type': forms.Select(attrs={'class': 'form-control'}),
            'has_categories': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name', '')
        if not name.strip():
            raise ValidationError('Event name cannot be blank.')
        return name


class MatchForm(forms.ModelForm):
    class Meta:
        model = Match
        fields = ['event', 'team_a', 'team_b', 'date_time', 'venue', 'stage', 'group', 'division']
        widgets = {
            'event': forms.Select(attrs={'class': 'form-control'}),
            'team_a': forms.Select(attrs={'class': 'form-control'}),
            'team_b': forms.Select(attrs={'class': 'form-control'}),
            'date_time': forms.DateTimeInput(
                attrs={'class': 'form-control', 'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M',
            ),
            'venue': forms.TextInput(attrs={'class': 'form-control'}),
            'stage': forms.Select(attrs={'class': 'form-control'}),
            'group': forms.Select(attrs={'class': 'form-control'}),
            'division': forms.Select(attrs={'class': 'form-control'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        team_a = cleaned_data.get('team_a')
        team_b = cleaned_data.get('team_b')
        if team_a and team_b and team_a == team_b:
            raise ValidationError('A team cannot play against itself.')
        return cleaned_data


class MatchEditForm(forms.ModelForm):
    """
    Used when EDITING an existing match.
    Only allows changing: Team A, Team B, Date & Time, Venue, and Best Of (sets).
    Event, stage, group, and division are system-controlled and must not change.
    """
    BEST_OF_CHOICES = [
        ('', '— Normal scoring (no sets) —'),
        (3, 'Best of 3'),
        (5, 'Best of 5'),
        (7, 'Best of 7'),
    ]
    best_of = forms.ChoiceField(
        choices=BEST_OF_CHOICES,
        required=False,
        label='Set-Based Scoring',
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text='Select if this match uses sets (e.g. Volleyball). Leave blank for normal scoring.',
    )

    class Meta:
        model = Match
        fields = ['team_a', 'team_b', 'date_time', 'venue', 'best_of']
        widgets = {
            'team_a': forms.Select(attrs={'class': 'form-control'}),
            'team_b': forms.Select(attrs={'class': 'form-control'}),
            'date_time': forms.DateTimeInput(
                attrs={'class': 'form-control', 'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M',
            ),
            'venue': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pre-select current best_of value
        if self.instance and self.instance.best_of:
            self.fields['best_of'].initial = self.instance.best_of
        else:
            self.fields['best_of'].initial = ''

    def clean(self):
        cleaned_data = super().clean()
        team_a = cleaned_data.get('team_a')
        team_b = cleaned_data.get('team_b')
        if team_a and team_b and team_a == team_b:
            raise ValidationError('A team cannot play against itself.')
        # Convert best_of to int or None
        best_of_raw = cleaned_data.get('best_of')
        cleaned_data['best_of'] = int(best_of_raw) if best_of_raw else None
        return cleaned_data


class MatchSetScoreForm(forms.Form):
    """Dynamically built form for entering scores for each set."""

    def __init__(self, *args, match_sets=None, **kwargs):
        super().__init__(*args, **kwargs)
        if match_sets:
            for ms in match_sets:
                self.fields[f'score_a_{ms.set_number}'] = forms.IntegerField(
                    min_value=0,
                    label=f'Set {ms.set_number} — Team A',
                    initial=ms.score_a,
                    widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'style': 'max-width:90px;'}),
                )
                self.fields[f'score_b_{ms.set_number}'] = forms.IntegerField(
                    min_value=0,
                    label=f'Set {ms.set_number} — Team B',
                    initial=ms.score_b,
                    widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'style': 'max-width:90px;'}),
                )


class ScoreForm(forms.ModelForm):
    class Meta:
        model = Score
        fields = ['score_a', 'score_b']
        widgets = {
            'score_a': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'step': '0.5',   # allows 0, 0.5, 1, 1.5, 2, 2.5 etc.
                'placeholder': '0',
            }),
            'score_b': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'step': '0.5',
                'placeholder': '0',
            }),
        }

    def clean_score_a(self):
        value = self.cleaned_data.get('score_a')
        if value is not None and value < 0:
            raise ValidationError('Score cannot be negative.')
        return value

    def clean_score_b(self):
        value = self.cleaned_data.get('score_b')
        if value is not None and value < 0:
            raise ValidationError('Score cannot be negative.')
        return value
