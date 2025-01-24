from django.urls import path, include
from . import views

app_name = 'django_app'

urlpatterns = [
    path('home', views.filter_results, name='home'),
    path('all_movies/', views.all_movies, name='all_movies'),
    path('', views.register, name='register'),
    path('login/', views.login_, name='login'),
    path('logout/', views.logout_f, name='logout'),
    path('profile/', views.profile, name='profile'),
    path('profile_update/', views.profile_update, name='profile_update'),
    path('about/', views.about, name='about'),
]
