from django.urls import path

from . import views

app_name = 'django_app'

urlpatterns = [
    path('', views.home, name='index'),
    path('home', views.home, name='home'),
    path('browse/', views.catalog, name='catalog'),
    path('browse/<slug:category_slug>/', views.catalog, name='catalog_category'),
    path('all_movies/', views.all_movies, name='all_movies'),
    path('title/<int:pk>/', views.title_detail, name='title_detail'),
    path('title/<int:pk>/status/', views.set_status, name='set_status'),
    path('title/<int:pk>/rate/', views.rate_title, name='rate_title'),
    path('title/<int:pk>/review/', views.review_title, name='review_title'),
    path('lists/new/', views.list_create, name='list_create'),
    path('lists/<int:pk>/', views.list_detail, name='list_detail'),
    path('lists/<int:pk>/edit/', views.list_edit, name='list_edit'),
    path('lists/<int:pk>/delete/', views.list_delete, name='list_delete'),
    path('lists/<int:pk>/toggle/<int:item_pk>/', views.list_toggle_item, name='list_toggle_item'),
    path('register/', views.register, name='register'),
    path('login/', views.login_, name='login'),
    path('logout/', views.logout_f, name='logout'),
    path('profile/', views.profile, name='profile'),
    path('profile_update/', views.profile_update, name='profile_update'),
    path('u/<str:username>/', views.profile, name='user_profile'),
    path('about/', views.about, name='about'),
]
