from django.urls import include, path, re_path
from .import views
from .views import SpaView

app_name = 'rentals' # Optional, but useful for namespacing

urlpatterns = [
    # Task 17: DRF /api/v1/ namespace.
    path('api/v1/', include('rentals.api.urls')),
    path('', views.index, name='index'),
    path('logout/', views.logout_view, name='logout'),

    # API methods
    path('table-data/<str:data_type>', views.table_data, name='table_data'),
    path('handling/<str:data_type>/<int:element_id>', views.handle_element, name='handle_element'),
    path('handling/<str:data_type>', views.create_element, name='create_element'),
    path('vacate-tenant/<int:tenant_id>', views.vacate_tenant, name='vacate_tenant'),
    path('new-form/<str:form_type>', views.new_form, name='new_form'),
    path('tenants/property-choices', views.property_choices, name='property_choices'),
    path('get_chart_data', views.chart_data_request, name='chart_data_request'),
    path('properties/valuation/<int:property_id>', views.property_valuation, name='property_valuation'),
    path('update-fx/', views.update_fx_view, name='update_fx'),

    # Handle Chrome DevTools and well-known requests
    path('.well-known/appspecific/com.chrome.devtools.json', views.chrome_devtools_config, name='chrome_devtools'),
    path('.well-known/<path:path>', views.well_known_handler, name='well_known'),
]

# Task 6: SPA catch-all (MUST be appended LAST).
urlpatterns += [
    path('', SpaView.as_view()),
    re_path(r'^.*/$', SpaView.as_view()),
]
