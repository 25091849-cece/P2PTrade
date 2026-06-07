from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views

app_name = 'marketplace'

# REST API Router
router = DefaultRouter()
router.register(r'deals', views.DealViewSet, basename='api-deal')

urlpatterns = [
    # Template views
    path('', views.index, name='index'),
    path('create/', views.create_deal, name='create'),
    path('deals/<int:deal_id>/created/', views.deal_created, name='deal_created'),
    path('deals/<int:deal_id>/accept/', views.accept_deal, name='accept_deal'),
    path('deals/<int:deal_id>/confirm/', views.confirm_accept, name='confirm_accept'),
    path('deals/<int:deal_id>/cancel/',views.cancel_deal,name='cancel_deal'),
    
    # REST API
    path('api/', include(router.urls)),
]

