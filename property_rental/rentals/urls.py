from django.urls import path
from .import views

app_name = 'rentals' # Optional, but useful for namespacing

urlpatterns = [
    path('', views.index, name='index'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('properties/', views.properties, name='properties'),
    path('tenants/', views.tenants, name='tenants'),
    path('transactions/', views.transactions, name='transactions'),
    path('profile/', views.profile_page, name='profile_page'),
    path('edit-profile/', views.edit_profile, name='edit_profile'),
    # path('settings/', views.settings, name='settings'),
    
    # API methods
    path('table-data/<str:data_type>', views.table_data, name='table_data'),
    # path('properties/table-data', views.get_properties, name='get_properties'), # TO BE DELETED
    path('handling/<str:data_type>/<int:element_id>', views.handle_element, name='handle_element'),
    path('handling/<str:data_type>', views.create_element, name='create_element'),
    # path('properties/<int:property_id>', views.property_details, name='property_details'), # TO BE DELETED
    path('new-form/<str:form_type>', views.new_form, name='new_form'),
    path('tenants/property-choices', views.property_choices, name='property_choices'),
    path('update-date', views.update_date, name='update_date'),
    path('get_chart_data', views.chart_data_request, name='chart_data_request'),
]