# Intramurals Management System

## Overview

A Django web application for managing intramural sports competitions. It supports scheduling matches, recording scores, computing a live leaderboard, and enforcing role-based access for admins, organizers, and students.

---

## Requirements

- Python 3.10+
- pip

---

## Installation & Setup (Step-by-Step)

### Step 1: Clone or download the project

```bash
git clone <repository-url>
cd intramurals
```

### Step 2: Create a virtual environment

```bash
python -m venv venv
```

Activate it:

```bash
# Windows:
venv\Scripts\activate

# Mac/Linux:
source venv/bin/activate
```

### Step 3: Install dependencies

```bash
pip install -r requirements.txt
```

Required packages:

| Package | Version |
|---------|---------|
| Django | 4.2.7 |
| pytest | 7.4.3 |
| pytest-django | 4.7.0 |
| hypothesis | 6.92.1 |

### Step 4: Run database migrations

```bash
python manage.py migrate
```

### Step 5: Seed sample data

```bash
python manage.py seed_data
```

This command is idempotent — safe to run multiple times without creating duplicates.

### Step 6: Start the development server

```bash
python manage.py runserver
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.

---

## Test Accounts

| Role | Username | Password |
|------|----------|----------|
| Admin | admin | admin123 |
| Organizer | organizer | organizer123 |
| Student | student | student123 |

---

## Features

- **Authentication** — Login/logout with session management; unauthenticated users are redirected to the login page.
- **Role-based access control** — Three roles (admin, organizer, student) with different permissions enforced via a decorator.
- **Department management** — View all six competing departments with abbreviations.
- **Event management** — Admins can create, edit, and delete sports events.
- **Match scheduling** — Admins and organizers can schedule matches; supports search by event, team, or venue.
- **Score recording** — Admins and organizers can enter scores; win/loss/draw results are computed automatically.
- **Live leaderboard** — Ranks departments by points (win=3, draw=1) then by wins; updates instantly as scores are saved.
- **Dashboard** — Summary cards showing total events, matches, completed matches, and the current top-ranked department.
- **Dark mode** — Toggle between light and dark themes; preference is stored in `sessionStorage`.
- **Responsive layout** — Works on screens as narrow as 320 px; tables scroll horizontally on small screens.

---

## Project Structure

```
intramurals/
├── manage.py
├── requirements.txt
├── db.sqlite3
├── intramurals/               # Django project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
└── core/                      # Main application
    ├── models.py              # UserProfile, Department, Event, Match, Score
    ├── views.py               # All view functions
    ├── urls.py                # URL routing
    ├── forms.py               # EventForm, MatchForm, ScoreForm
    ├── decorators.py          # role_required decorator
    ├── utils.py               # get_leaderboard(), compute_points()
    ├── admin.py               # Django admin registrations
    ├── management/
    │   └── commands/
    │       └── seed_data.py   # Sample data seeder
    ├── migrations/
    │   └── 0001_initial.py
    ├── static/core/css/
    │   └── style.css          # Light/dark theme styles
    └── templates/core/
        ├── base.html
        ├── login.html
        ├── dashboard.html
        ├── departments.html
        ├── events.html
        ├── event_form.html
        ├── schedule.html
        ├── match_form.html
        ├── results.html
        ├── score_form.html
        └── leaderboard.html
```

---

## Running Tests (Optional)

```bash
pytest
```

Tests cover score computation, form validation, role-based access, authentication flow, leaderboard ordering, and more using both unit tests and property-based tests (Hypothesis).

---

## Suggestions for Improvement

1. **Bracket/tournament generator** — Automatically generate single-elimination or round-robin brackets from a list of participating departments.
2. **Real-time score updates** — Use Django Channels (WebSockets) to push live score changes to all connected browsers without a page refresh.
3. **Email notifications** — Send match reminders and result announcements to participants via Django's email backend.
4. **REST API** — Expose endpoints with Django REST Framework so a mobile app or third-party client can consume the data.
5. **Media uploads** — Allow organizers to attach photos or documents (e.g., match reports) to events and matches.
6. **Audit log** — Record who created or modified each match and score entry, with timestamps, for accountability.
