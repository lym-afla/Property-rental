from django.urls import path
from .import views

app_name = 'rentals' # Optional, but useful for namespacing

urlpatterns = [
    path('', views.index, name='index'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('properties/', views.properties, name='properties'),
    
    # API methods
    path('properties/table-data', views.get_properties, name='get_properties'),
    path('properties/<int:property_id>', views.property_details, name='property_details'),
    path('properties/new-property-form', views.new_property_form, name='new_property_form'),
]