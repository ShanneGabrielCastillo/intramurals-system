from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Department, Event, Match, Score, UserProfile


class Command(BaseCommand):
    help = "Seed the database with sample data (idempotent)."

    def handle(self, *args, **options):
        self._seed_departments()
        events = self._seed_events()
        matches = self._seed_matches(events)
        self._seed_scores(matches)
        self._seed_users()
        self.stdout.write(self.style.SUCCESS("Database seeding complete."))

    # ------------------------------------------------------------------
    def _seed_departments(self):
        departments = [
            ("College of Arts and Sciences", "CAS", 1),
            ("College of Teacher Education", "CTED", 2),
            ("College of Industrial Technology", "CIT", 3),
            ("College of Business Administration", "CBA", 4),
            ("College of Agriculture and Forestry", "CAF", 5),
            ("College of Criminal Justice Education", "CCJE", 6),
        ]
        for name, abbr, order in departments:
            dept, created = Department.objects.get_or_create(
                abbreviation=abbr,
                defaults={"name": name, "display_order": order},
            )
            status = "Created" if created else "Already exists"
            self.stdout.write(self.style.SUCCESS(f"  {status}: Department {abbr}"))

    # ------------------------------------------------------------------
    def _seed_events(self):
        event_names = ["Basketball", "Volleyball", "Badminton"]
        events = {}
        for name in event_names:
            event, created = Event.objects.get_or_create(name=name)
            status = "Created" if created else "Already exists"
            self.stdout.write(self.style.SUCCESS(f"  {status}: Event '{name}'"))
            events[name] = event
        return events

    # ------------------------------------------------------------------
    def _seed_matches(self, events):
        now = timezone.now()
        cas = Department.objects.get(abbreviation="CAS")
        cted = Department.objects.get(abbreviation="CTED")
        cit = Department.objects.get(abbreviation="CIT")
        cba = Department.objects.get(abbreviation="CBA")
        caf = Department.objects.get(abbreviation="CAF")
        ccje = Department.objects.get(abbreviation="CCJE")

        match_specs = [
            (events["Basketball"], cas, cted, now + timedelta(days=3), "Main Gym"),
            (events["Basketball"], cit, cba, now + timedelta(days=5), "Main Gym"),
            (events["Volleyball"], cted, caf, now + timedelta(days=7), "Covered Court"),
            (events["Badminton"], ccje, cas, now + timedelta(days=10), "Badminton Hall"),
        ]

        matches = []
        for event, team_a, team_b, dt, venue in match_specs:
            match, created = Match.objects.get_or_create(
                event=event,
                team_a=team_a,
                team_b=team_b,
                defaults={"date_time": dt, "venue": venue},
            )
            status = "Created" if created else "Already exists"
            self.stdout.write(
                self.style.SUCCESS(
                    f"  {status}: Match {team_a.abbreviation} vs {team_b.abbreviation} ({event.name})"
                )
            )
            matches.append(match)
        return matches

    # ------------------------------------------------------------------
    def _seed_scores(self, matches):
        score_specs = [
            (matches[0], 78, 65),   # CAS wins
            (matches[1], 55, 72),   # CBA wins
            (matches[2], 0, 0),     # pending
            (matches[3], 0, 0),     # pending
        ]
        for i, (match, score_a, score_b) in enumerate(score_specs):
            score, created = Score.objects.get_or_create(
                match=match,
                defaults={"score_a": score_a, "score_b": score_b},
            )
            if not created:
                # Update scores if they differ
                score.score_a = score_a
                score.score_b = score_b

            # Compute result for the first two completed matches
            if i < 2:
                score.compute_result()

            score.save()
            status = "Created" if created else "Updated"
            self.stdout.write(
                self.style.SUCCESS(
                    f"  {status}: Score for match {match.team_a.abbreviation} vs {match.team_b.abbreviation}"
                )
            )

    # ------------------------------------------------------------------
    def _seed_users(self):
        user_specs = [
            ("admin", "admin123", "admin", True, True),
            ("organizer", "organizer123", "organizer", False, False),
            ("student", "student123", "student", False, False),
        ]
        for username, password, role, is_staff, is_superuser in user_specs:
            user, created = User.objects.get_or_create(username=username)
            user.set_password(password)
            user.is_staff = is_staff
            user.is_superuser = is_superuser
            user.save()

            # The post_save signal creates a profile with role='student' on first create.
            # Use get_or_create so we don't duplicate, then set the correct role.
            profile, _ = UserProfile.objects.get_or_create(
                user=user, defaults={"role": role}
            )
            if profile.role != role:
                profile.role = role
                profile.save()

            status = "Created" if created else "Updated"
            self.stdout.write(
                self.style.SUCCESS(f"  {status}: User '{username}' (role={role})")
            )
