from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('procesar_xml', views.procesar_datos, name='procesar_datos'),    
    path('peticiones', views.peticiones, name='peticiones'),
]