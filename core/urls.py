from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('', views.dashboard_view, name='home'),
    path('departments/', views.department_list, name='department_list'),
    path('events/', views.event_list, name='event_list'),
    path('events/create/', views.event_create, name='event_create'),
    path('events/<int:pk>/edit/', views.event_update, name='event_update'),
    path('events/<int:pk>/delete/', views.event_delete, name='event_delete'),
    path('schedule/', views.match_list, name='match_list'),
    path('schedule/create/', views.match_create, name='match_create'),
    path('schedule/<int:pk>/edit/', views.match_update, name='match_update'),
    path('schedule/<int:pk>/delete/', views.match_delete, name='match_delete'),
    path('results/', views.results_list, name='results_list'),
    path('results/<int:pk>/score/', views.score_update, name='score_update'),
    path('leaderboard/', views.leaderboard_view, name='leaderboard'),
    path('events/<int:event_pk>/bracket/', views.tournament_bracket, name='tournament_bracket'),
    path('overall-leaderboard/', views.overall_leaderboard_view, name='overall_leaderboard'),
]
