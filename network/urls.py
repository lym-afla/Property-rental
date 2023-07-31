
from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("login", views.login_view, name="login"),
    path("logout", views.logout_view, name="logout"),
    path("register", views.register, name="register"),
    path("profile/<str:username>", views.user_profile, name="user_profile"),
    path('profile/<str:username>/follow/', views.follow_user, name='follow'),
    
    # API routes
    path("posts", views.new_post, name="new_post"),
    path("posts/<str:filter>", views.get_posts, name="get_posts"),
    path("profile/<str:profile_username>/posts", views.get_posts, name="get_posts"),
    path("posts/<int:id>/edit", views.edit_post, name="edit_post"),
]
