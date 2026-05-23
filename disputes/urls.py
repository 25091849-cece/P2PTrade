from django.urls import path

from . import views

app_name = 'disputes'

urlpatterns = [
    path('', views.index, name='index'),
    path('raise/<int:txn_id>/', views.raise_dispute, name='raise'),
    path('cancel/<int:txn_id>/', views.cancel_dispute, name='cancel'),
]

