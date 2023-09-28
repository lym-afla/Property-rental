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
    path('table-data/<str:data_type>', views.table_data, name='table_data'),
    path('properties/table-data', views.get_properties, name='get_properties'), # TO BE DELETED
    path('handling/<str:data_type>/<int:element_id>', views.element_details, name='element_details'),
    path('properties/<int:property_id>', views.property_details, name='property_details'), # TO BE DELETED
    path('properties/new-form/<str:form_type>', views.new_form, name='new_form'),
]