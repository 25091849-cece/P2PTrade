"""
URL configuration for P2PTrade project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('', include('accounts.urls')),
    # Register app routes (namespace) so templates can reverse names like
    # 'wallets:index' without raising NoReverseMatch. Add marketplace and
    # transactions stubs so the dashboard links resolve while teams implement
    # the real modules.
    path('wallets/', include(('wallets.urls', 'wallets'), namespace='wallets')),
    path('marketplace/', include(('marketplace.urls', 'marketplace'), namespace='marketplace')),
    path('transactions/', include(('transactions.urls', 'transactions'), namespace='transactions')),
    path('disputes/', include(('disputes.urls', 'disputes'), namespace='disputes')),
    path('admin/', admin.site.urls),
]
