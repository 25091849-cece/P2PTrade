from django.urls import path

from .views import dashboard_page, login_page, logout_view, signup_page, signup_success


urlpatterns = [
    path('', login_page, name='login'),
    path('signup/', signup_page, name='signup'),
    path('signup/success/', signup_success, name='signup_success'),
    path('dashboard/', dashboard_page, name='dashboard'),
    path('logout/', logout_view, name='logout'),
]
