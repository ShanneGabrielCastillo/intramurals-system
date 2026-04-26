from django import forms
from django.core.exceptions import ValidationError

from .models import Event, Match, Score, Department


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ['name', 'description', 'format']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control'}),
            'format': forms.Select(attrs={'class': 'form-control'}),
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
