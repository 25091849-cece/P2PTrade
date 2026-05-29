from django.urls import path

from . import views

app_name = 'wallets'

urlpatterns = [
    path('', views.index, name='index'),
    path('deposit/', views.deposit, name='deposit'),
    path('deposit/top-up/', views.top_up, name='top_up'),
    path('withdraw/', views.withdraw, name='withdraw'),
    path('clear-verification/', views.clear_verification, name='clear_verification'),
]

