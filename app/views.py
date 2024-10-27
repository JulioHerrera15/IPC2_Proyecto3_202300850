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

# Crear una sesión de requests que mantendrá las cookies entre solicitudes
flask_session = requests.Session()

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
                        # Usa la sesión persistente para hacer la solicitud POST
                        response = flask_session.post(f'{api}/procesar_xml', files=files)
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
    try:
        # Usa la misma sesión para hacer la solicitud GET
        response = flask_session.get(f'{api}/peticiones')
        logger.debug(f"Respuesta cruda de Flask: {response.text}")
        if response.status_code == 200:
            data = response.json().get('messages', [])
            logger.debug(f"Mensajes recibidos de Flask: {data}")
        else:
            logger.error("Error al obtener mensajes desde Flask.")
            data = []
    except Exception as e:
        logger.error(f"Error conectando con Flask: {str(e)}")
        data = []

    return render(request, 'peticiones.html', {'messages': data})

def resumen_fecha(request):
    context = {'total': 0, 'positivos': 0, 'negativos': 0, 'neutros': 0, 'empresas': []}
    
    # Intento de obtener la lista de empresas al cargar la página
    try:
        response = flask_session.get(f'{api}/obtener_empresas')
        if response.status_code == 200:
            empresas_data = response.json()
            context['empresas'] = empresas_data.get('empresas', [])
            
            logger.debug(f"Lista de empresas obtenida: {context['empresas']}")
            
            if request.method == 'POST':
                # Recibir los parámetros de la solicitud POST
                fecha = request.POST.get('fecha')
                empresa = request.POST.get('empresa', 'todas')

                context['fecha'] = fecha
                context['empresa'] = empresa
                logger.debug(f"Parámetros recibidos - Fecha: {fecha}, Empresa: {empresa}")
                
                try:
                    # Llamar a la API Flask para obtener el resumen de mensajes según fecha y empresa
                    response = flask_session.get(f'{api}/resumen_fecha', params={'fecha': fecha, 'empresa': empresa})
                    if response.status_code == 200:
                        data = response.json()
                        context.update(data)
                        
                        logger.debug(f"Datos de resumen obtenidos: {data}")
                    else:
                        logger.error(f"Error en la solicitud a Flask: {response.status_code}")
                except Exception as e:
                    logger.error(f"Error conectando con Flask: {str(e)}")
        else:
            logger.error("Error al obtener la lista de empresas desde Flask.")
    except Exception as e:
        logger.error(f"Error conectando con Flask: {str(e)}")
    
    logger.debug(f"Contexto final para la plantilla: {context}")
    return render(request, 'resumen_fecha.html', context)



def ayuda(request):
    return render(request, 'ayuda.html')
