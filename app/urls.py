from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('procesar_xml', views.procesar_datos, name='procesar_datos'),    
    path('peticiones', views.peticiones, name='peticiones'),
    path('ayuda', views.ayuda, name='ayuda'),
    path('resumen_fecha', views.resumen_fecha, name='resumen_fecha'),
    path('resumen_rango_fecha', views.resumen_rango_fecha, name='resumen_rango_fecha'),
    path('reset', views.reset, name='reset'),
    path('prueba_mensaje', views.prueba_mensaje, name='prueba_mensaje'),
    path('consultar_datos', views.consultar_datos, name='consultar_datos'),
    path('descargar_pdf', views.descargar_pdf, name='descargar_pdf'),
    path('store_chart_image', views.store_chart_image, name='store_chart_image')
]