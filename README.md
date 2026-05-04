# 🏆 Intramurals Management System

A web-based intramural sports management system built with Django. It handles event creation, match scheduling, score recording, tournament bracket progression, department standings, and an overall medal leaderboard — all with role-based access control and a responsive UI.

---

## Features

- **Dashboard** — Live stats: total events, matches, completed matches, top department by medals, recent results, and upcoming matches
- **Department Logos** — Upload logos via admin panel; displayed beside team names throughout the system
- **Event Management** — Create and edit events with format (Hybrid / Group Knockout), division type (Men / Women / Both), and optional categories (Singles / Doubles / Mixed)
- **Auto Match Generation** — Matches are automatically generated on event creation based on format and division settings
- **Match Scheduling** — Edit match date, time, venue, and teams; system-controlled fields (stage, group, division) are locked
- **Score Recording** — Enter scores; win/loss/draw results computed automatically
- **Tournament Progression** — Semifinals and finals auto-generate when the previous stage is complete
- **Event Standings** — Per-event standings with Group A/B tables, Knockout bracket, and Champion display
- **Overall Leaderboard** — Medal table (Gold / Silver / Bronze) ranked by total medal points
- **Role-Based Access** — Admin, Organizer, and Student roles with enforced permissions
- **Dark Mode** — Toggle between light and dark themes
- **Responsive Layout** — Works on desktop, tablet, and mobile
- **Delete Confirmation** — Custom modal dialog before any destructive action

---

## Technologies

| Layer | Technology |
|---|---|
| Backend | Python 3.14, Django 4.2 |
| Database | MySQL / MariaDB |
| Frontend | HTML, CSS, JavaScript (vanilla) |
| Image handling | Pillow |

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

Open `intramurals/settings.py` and update the `DATABASES` section with your MySQL credentials:

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

## Setting Up Departments

1. Go to [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/) and log in with your superuser account
2. Under **Core → Departments**, add your departments (name, abbreviation, display order)
3. Optionally upload a logo image for each department

---

## Usage

| URL | Description |
|---|---|
| `/dashboard/` | Overview and recent activity |
| `/departments/` | List of all departments |
| `/events/` | Create and manage events |
| `/schedule/` | View and search match schedule |
| `/results/` | Enter and view match scores |
| `/leaderboard/` | Per-event standings and knockout bracket |
| `/overall-leaderboard/` | Overall medal standings |
| `/admin/` | Django admin panel |

---

## Project Structure

```
intramurals/
├── manage.py
├── requirements.txt
├── intramurals/               # Project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
└── core/                      # Main application
    ├── models.py              # Department, Event, EventCategory, Match, Score, EventResult
    ├── views.py               # All view functions
    ├── urls.py                # URL routing
    ├── forms.py               # EventForm, MatchForm, MatchEditForm, ScoreForm
    ├── decorators.py          # role_required decorator
    ├── utils.py               # compute_points()
    ├── signals.py             # Auto match generation and stage progression
    ├── tournament_service.py  # Match generation and standings logic
    ├── result_service.py      # Medal (EventResult) logic and overall leaderboard
    ├── admin.py               # Django admin configuration
    ├── templatetags/
    │   └── score_filters.py   # score_display template filter
    ├── migrations/            # Database migrations
    ├── static/core/css/
    │   └── style.css          # All styles (light + dark mode)
    └── templates/core/        # HTML templates
```

---

## Default Roles

After creating a superuser, you can assign roles via the admin panel under **Core → User Profiles**:

| Role | Permissions |
|---|---|
| Admin | Full access — create/edit/delete events, matches, scores |
| Organizer | Can schedule matches and enter scores |
| Student | Read-only access |

---

## License

This project was developed as an academic submission for Negros Oriental State University — Bayawan Sta. Catalina Campus.
