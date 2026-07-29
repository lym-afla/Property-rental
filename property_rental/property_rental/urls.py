"""
URL configuration for property_rental project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.http import HttpResponseNotFound
from django.urls import path, include


def api_not_found(request, exception):
    """Return a plain 404 response when an API route is not registered."""
    return HttpResponseNotFound()


handler404 = api_not_found

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('rentals.urls')),
]
