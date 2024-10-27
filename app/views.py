from django.shortcuts import render
from .forms import FileForm
import requests
import logging
import os
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom

# Configurar logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

api = 'http://localhost:5000'

def index(request):
    context = {
        'xml_content': '',
        'processed_content': '',
        'error': ''
    }
    return render(request, 'index.html', context)

def remove_blank_lines(xml_string):
    # Eliminar líneas en blanco y espacios innecesarios
    lines = xml_string.split('\n')
    return '\n'.join(line for line in lines if line.strip())

def format_xml(xml_string):
    """Formatea el XML con sangría adecuada y sin espacios adicionales"""
    try:
        # Parsear el XML
        dom = minidom.parseString(xml_string)
        
        # Obtener el XML formateado
        formatted_xml = dom.toprettyxml(indent='  ')
        
        # Eliminar líneas en blanco y espacios innecesarios
        cleaned_xml = remove_blank_lines(formatted_xml)
        
        return cleaned_xml
    except Exception as e:
        logger.error(f"Error formateando XML: {str(e)}")
        return xml_string

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
            logger.debug(f"Archivo recibido: {archivo.name}")
            
            if archivo.name.endswith('.xml'):
                try:
                    # Leer y decodificar el contenido del archivo XML cargado
                    xml_content = archivo.read()
                    try:
                        xml_content = xml_content.decode('utf-8')
                    except UnicodeDecodeError:
                        xml_content = xml_content.decode('latin-1')
                    
                    # Formatear el XML de entrada
                    formatted_input = format_xml(xml_content)
                    context['xml_content'] = formatted_input
                    
                    # Crear archivo temporal para enviarlo a Flask
                    temp_filename = 'temp_xml_file.xml'
                    with open(temp_filename, 'w', encoding='utf-8') as f:
                        f.write(xml_content)
                    
                    # Enviar el archivo a Flask para el procesamiento
                    with open(temp_filename, 'rb') as f:
                        files = {
                            'archivo': ('archivo.xml', f, 'application/xml')
                        }
                        logger.debug("Enviando solicitud a Flask")
                        response = requests.post(f'{api}/procesar_xml', files=files)
                        logger.debug(f"Respuesta recibida: {response.status_code}")
                    
                    if response.status_code == 200:
                        data = response.json()
                        processed_xml = data.get('xml_content', '')
                        
                        # Formatear el XML de salida
                        formatted_output = format_xml(processed_xml)
                        context['processed_content'] = formatted_output
                    else:
                        error_msg = response.json().get('error', 'Error desconocido en el servidor')
                        logger.error(f"Error en Flask: {error_msg}")
                        context['error'] = f'Error en el servidor: {error_msg}'
                    
                    # Limpiar archivo temporal
                    if os.path.exists(temp_filename):
                        os.remove(temp_filename)
                    
                except Exception as e:
                    logger.error(f"Error procesando archivo: {str(e)}")
                    context['error'] = f'Error procesando archivo: {str(e)}'
            else:
                context['error'] = 'El archivo debe ser XML'
        else:
            context['error'] = 'Formulario inválido'
            
    return render(request, 'index.html', context)


def peticiones(request):
    return render(request, 'peticiones.html')

def ayuda(request):
    return render(request, 'ayuda.html')