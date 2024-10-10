from django.shortcuts import render
import requests
# Create your views here.

#Esta es una vista de ejemplo, pero puedes agregar las que necesites
def index(request):
    return render(request, 'index.html')

