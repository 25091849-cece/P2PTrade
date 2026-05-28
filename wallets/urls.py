from django.urls import path

from . import views

app_name = 'wallets'

urlpatterns = [
    path('', views.index, name='index'),
    path('clear-verification/', views.clear_verification, name='clear_verification'),
]

