from django.shortcuts import render
from .forms import FileForm
import requests

api = 'http://localhost:5000'

def index(request):
    context = {
        'xml_content': '',
        'processed_content': '',
        'error': ''
    }
    return render(request, 'index.html', context)

def procesar_datos(request):
    context = {
        'xml_content': '',
        'processed_content': '',
        'error': ''
    }
    
    if request.method == 'POST':
        form = FileForm(request.POST, request.FILES)
        if form.is_valid():
            archivo = request.FILES['archivo']
            if archivo.name.endswith('.xml'):
                try:
                    # Leer el contenido del archivo
                    xml_content = archivo.read().decode('utf-8')
                    
                    # Preparar los archivos para la solicitud
                    files = {
                        'archivo': ('archivo.xml', xml_content, 'application/xml')
                    }
                    
                    # Realizar la solicitud al backend Flask
                    response = requests.post(f'{api}/procesar_xml', files=files)
                    
                    if response.status_code == 200:
                        data = response.json()
                        context.update({
                            'xml_content': data['xml_content']                            
                        })
                    else:
                        context['error'] = 'Error en el procesamiento del archivo'
                except Exception as e:
                    context['error'] = f'Error: {str(e)}'
            else:
                context['error'] = 'El archivo debe ser XML'
    
    return render(request, 'index.html', context)

def peticiones(request):
    return render(request, 'peticiones.html')