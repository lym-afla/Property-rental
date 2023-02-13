from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("wiki/<str:entry>", views.entry, name="entry"),
    path("search", views.search, name='search'),
    path("add-entry", views.add_page, name="new_page"),
    path("edit-entry", views.edit_page, name="edit"),
    path("random", views.random_page, name="random")
]
