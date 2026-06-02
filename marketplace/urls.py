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
    path('deals/<int:deal_id>/accept/', views.accept_deal, name='accept'),

    # REST API
    path('api/', include(router.urls)),
]

