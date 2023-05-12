from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("login", views.login_view, name="login"),
    path("logout", views.logout_view, name="logout"),
    path("register", views.register, name="register"),
    path("create-listing", views.create_listing, name="create_listing"),
    path("listing/<int:listing_id>", views.show_listing, name="show_listing"),
    path("edit-watchlist/<int:listing_id>", views.edit_watchlist, name="edit_watchlist"),
    path("close_listing/<int:listing_id>", views.close_listing, name="close_listing"),
    path("add-comment/<int:listing_id>", views.add_comment, name="add_comment"),
    path("categories", views.categories, name="categories"),
]
