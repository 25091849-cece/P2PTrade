from django.urls import path

from . import views

app_name = 'transactions'

urlpatterns = [
    path('', views.index, name='index'),
    path('admin/', views.admin_index, name='admin_index'),
    path('<int:txn_id>/export/pdf/', views.export_pdf, name='export_pdf'),
    path('export/summary/', views.export_summary_pdf, name='export_summary'),
]

