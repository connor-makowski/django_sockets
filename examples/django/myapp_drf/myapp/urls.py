"""
URL configuration for myapp project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
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
from django.shortcuts import render
from django.urls import path

from rest_framework.authtoken.models import Token
from django.contrib.auth.decorators import login_required

@login_required(login_url="/admin/login/")
def client_view(request):
    '''
    Render the client.html template
    '''
    # Get or create a token for the user
    token, created = Token.objects.get_or_create(user=request.user)
    # Pass the user and token to the client.html template
    return render(request, 'client.html', {'user': request.user, 'token': token})

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', client_view),
]