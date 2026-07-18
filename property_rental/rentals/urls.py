from django.urls import include, path
from .import views

app_name = 'rentals' # Optional, but useful for namespacing

urlpatterns = [
    # Task 17: DRF /api/v1/ namespace. Mounted under ``rentals.urls`` (which
    # the project urls.py mounts at the empty prefix), so the full path is
    # ``/api/v1/properties/`` etc. The router + ChartDataView live in
    # ``rentals.api.urls`` to keep the API surface self-contained.
    path('api/v1/', include('rentals.api.urls')),
    path('', views.index, name='index'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('properties/', views.properties, name='properties'),
    path('tenants/', views.tenants, name='tenants'),
    path('transactions/', views.transactions, name='transactions'),
    path('profile/', views.profile_page, name='profile_page'),
    path('edit-profile/', views.edit_profile, name='edit_profile'),
    path('fx/', views.fx_list, name='fx_list'),
    
    # API methods
    path('table-data/<str:data_type>', views.table_data, name='table_data'),
    # path('properties/table-data', views.get_properties, name='get_properties'), # TO BE DELETED
    path('handling/<str:data_type>/<int:element_id>', views.handle_element, name='handle_element'),
    path('handling/<str:data_type>', views.create_element, name='create_element'),
    path('vacate-tenant/<int:tenant_id>', views.vacate_tenant, name='vacate_tenant'),
    # path('properties/<int:property_id>', views.property_details, name='property_details'), # TO BE DELETED
    path('new-form/<str:form_type>', views.new_form, name='new_form'),
    path('tenants/property-choices', views.property_choices, name='property_choices'),
    path('get_chart_data', views.chart_data_request, name='chart_data_request'),
    path('properties/valuation/<int:property_id>', views.property_valuation, name='property_valuation'),
    path('update-fx/', views.update_fx_view, name='update_fx'),
    
    # Handle Chrome DevTools and well-known requests
    path('.well-known/appspecific/com.chrome.devtools.json', views.chrome_devtools_config, name='chrome_devtools'),
    path('.well-known/<path:path>', views.well_known_handler, name='well_known'),
]