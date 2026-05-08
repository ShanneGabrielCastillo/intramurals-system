# 🏆 Intramurals Management System

A web-based intramural sports management system built with Django. It handles season management, department tracking, event creation, automatic match generation, score recording, tournament bracket progression, real-time notifications, department standings, and an overall medal leaderboard — all with role-based access control and a fully responsive mobile UI.

---

## Features

### Core System
- **Dashboard** — Live stats: total events, matches, completed matches, top department by medals, recent results, and upcoming matches with mobile-optimized card layout
- **Season Management** — Create and manage multiple seasons; set one as active; copy events from a previous season with auto-generated matches; past seasons are read-only
- **Department Management** — Add departments with name, abbreviation, display order, logo, and tournament group (A/B); season-aware visibility ensures departments only appear in seasons where they exist
- **Department Logo Upload** — Upload PNG/JPG logos via the admin panel; displayed as circular thumbnails throughout the system (powered by Pillow)

### Events & Matches
- **Event Management** — Create events with format (Hybrid / Group Knockout), division type (Men / Women / Both), and optional categories (Singles / Doubles / Mixed)
- **Auto Match Generation** — Matches are automatically generated on event creation based on format, division, and category settings using Django `post_save` signals
- **Auto Department Sync** — When a new department is added mid-season, missing matches are automatically generated across all existing events without recreating them; includes a manual Sync button per department
- **Match Scheduling** — Edit match date, time, venue, and teams; system-controlled fields (stage, group, division) are locked to protect tournament integrity
- **Set-Based Scoring** — Supports Best of 3/5/7 set scoring for sports like Volleyball; sets won are computed automatically
- **Score Recording** — Enter scores; win/loss/draw results computed automatically via `Score.compute_result()`

### Tournament Progression
- **Automatic Stage Advancement** — Semifinals and finals auto-generate when the previous stage is fully complete; no manual intervention required
- **Stage Locking** — Once a knockout stage is generated, earlier stage scores are locked to prevent retroactive bracket manipulation; enforced at both UI and backend level
- **Hybrid Format** — Round Robin → Top 4 advance → Semifinals (Rank1 vs Rank4, Rank2 vs Rank3) → Finals + 3rd Place
- **Group Knockout Format** — Group Stage (A and B) → Top 2 from each group → Cross-group Semifinals (A1 vs B2, B1 vs A2) → Finals + 3rd Place
- **Dynamic Group Assignment** — Department groups (A/B) are stored on the Department model; no hardcoded abbreviations

### Standings & Leaderboard
- **Event Standings** — Per-event standings with Group A/B tables, Knockout bracket, Champion display; scoped per division and category
- **Overall Leaderboard** — Medal table (Gold=5pts / Silver=3pts / Bronze=1pt) ranked by total points → Gold count → Silver count; season-filtered
- **Real-Time Notifications** — AJAX polling every 5 seconds; toast notifications appear for all users (including viewers) when a new match result is recorded

### Access Control
- **Role-Based Access** — Admin (full control), Organizer (assigned events only), Viewer (read-only, no login required)
- **Granular Organizer Assignment** — Organizers are assigned per event + category + division combination; enforced at the backend
- **Session-Based Authentication** — Django session system; multiple devices can be logged in simultaneously with independent sessions

### UI & Responsiveness
- **Mobile Hamburger Menu** — Slide-out drawer with smooth animation, season selector, all nav links, and admin section; built from scratch without Bootstrap
- **Fully Responsive** — Custom CSS with media query breakpoints at 900px, 768px, 600px, 480px, and 360px; no external CSS framework used
- **Dark Mode** — Toggle between light and dark themes; preference stored in `sessionStorage`
- **Modern Form Design** — Redesigned forms with rounded inputs, inline error messages, two-column grid layouts, and touch-friendly controls
- **Delete Confirmation Modal** — Custom modal dialog before any destructive action

---

## Technologies

| Layer | Technology |
|---|---|
| Backend | Python 3.14, Django 4.2 |
| Database | MySQL / MariaDB |
| Frontend | HTML5, CSS3, JavaScript (vanilla — no Bootstrap) |
| Image handling | Pillow |
| Database connector | mysqlclient |

---

## Prerequisites

- Python 3.10 or higher
- MySQL or MariaDB server running locally
- pip

---

## Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd intramurals
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create the MySQL database

Open your MySQL client (XAMPP, MySQL Workbench, or terminal) and run:

```sql
CREATE DATABASE intramurals_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 5. Configure the database connection

Open `intramurals/settings.py` and update the `DATABASES` section:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'intramurals_db',
        'USER': 'root',           # your MySQL username
        'PASSWORD': '',           # your MySQL password
        'HOST': 'localhost',
        'PORT': '3306',
        'OPTIONS': {'charset': 'utf8mb4'},
    }
}
```

### 6. Run migrations

```bash
python manage.py migrate
```

### 7. Create a superuser (admin account)

```bash
python manage.py createsuperuser
```

### 8. Start the development server

```bash
python manage.py runserver
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.

---

## Quick Start Guide

### 1. Set up departments
Go to `/departments/` → Add Department. Set name, abbreviation, display order, and assign a tournament group (A or B for Group Knockout events).

### 2. Create a season
Go to `/seasons/` → Create Season. Set it as active. Optionally copy events from a previous season.

### 3. Create events
Go to `/events/` → Add Event. Choose format, divisions, and whether the sport has categories. Matches are generated automatically.

### 4. Assign organizers
Go to `/organizers/` → Edit an organizer → assign them to specific events, categories, and divisions.

### 5. Enter scores
Go to `/results/` → click Enter Score or Enter Sets for each match. Standings update automatically. Next stages generate automatically when a stage is complete.

---

## URL Reference

| URL | Description |
|---|---|
| `/` | Redirects to dashboard |
| `/dashboard/` | Overview and recent activity |
| `/departments/` | List, add, edit, delete, sync departments |
| `/events/` | Create and manage events |
| `/schedule/` | View and search match schedule |
| `/results/` | Enter and view match scores |
| `/leaderboard/` | Per-event standings and knockout bracket |
| `/overall-leaderboard/` | Overall medal standings |
| `/organizers/` | Manage organizer accounts and assignments |
| `/seasons/` | Manage seasons |
| `/api/latest-result/` | JSON endpoint for real-time notification polling |
| `/admin/` | Django admin panel |

---

## Project Structure

```
intramurals/
├── manage.py
├── requirements.txt
├── system_flowchart.html          # Complete system flowchart (open in browser)
├── intramurals/                   # Project configuration
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
└── core/                          # Main application
    ├── models.py                  # All database models (9 models)
    ├── views.py                   # All view functions and business logic
    ├── urls.py                    # 27 URL routes
    ├── forms.py                   # All form definitions and validation
    ├── decorators.py              # role_required, active_season_required
    ├── utils.py                   # compute_points()
    ├── context_processors.py      # Season context injected into every template
    ├── signals.py                 # Auto match generation and stage progression
    ├── tournament_service.py      # Match generation, standings, stage lock, dept sync
    ├── result_service.py          # Medal assignment and overall leaderboard
    ├── admin.py                   # Django admin configuration
    ├── templatetags/
    │   └── score_filters.py       # score_display template filter
    ├── migrations/                # 24 database migrations
    ├── static/core/css/
    │   └── style.css              # All styles — light/dark mode, responsive (2400+ lines)
    └── templates/core/            # All HTML templates
        ├── base.html              # Master layout — navbar, drawer, JS, dark mode
        ├── dashboard.html
        ├── departments.html
        ├── department_form.html
        ├── events.html
        ├── event_form.html
        ├── schedule.html
        ├── results.html
        ├── score_form.html
        ├── set_score_form.html
        ├── leaderboard.html
        ├── overall_leaderboard.html
        ├── organizers.html
        ├── organizer_form.html
        ├── organizer_edit.html
        ├── seasons.html
        ├── season_form.html
        ├── match_form.html
        ├── login.html
        ├── _match_row_results.html
        └── _match_row_schedule.html
```

---

## User Roles

| Role | Permissions |
|---|---|
| **Admin** | Full access — manage seasons, departments, events, organizers, matches, scores |
| **Organizer** | Enter scores and edit schedules for assigned events/categories/divisions only |
| **Viewer** | Read-only access to all public pages — no login required |

Roles are stored in `UserProfile.role`. Access is enforced using the `@role_required` decorator and `OrganizerAssignment` checks at the backend level.

---

## Key Technical Notes

- **No Bootstrap** — all CSS is written from scratch in `style.css`
- **No duplicate matches** — all match creation uses `get_or_create` + `unique_together` database constraint
- **Historical accuracy** — `Department.created_season` ensures departments only appear in seasons where they existed
- **Decimal scores** — `DecimalField` used instead of `FloatField` to avoid floating-point rounding errors on scores like 2.5
- **CSRF protection** — all forms include Django's CSRF token
- **Password hashing** — Django PBKDF2 + SHA-256; passwords never stored as plain text

---

## License

This project was developed as an academic capstone submission for Negros Oriental State University — Bayawan Sta. Catalina Campus.
