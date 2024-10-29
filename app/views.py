from django.shortcuts import render, redirect
from django.http import HttpResponse
from .forms import FileForm
from django.views.decorators.csrf import csrf_exempt
import base64
import requests
import logging
import os
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import io
from datetime import datetime
import json

# Configurar logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

api = 'http://localhost:5000'

# Crear una sesión de requests que mantendrá las cookies entre solicitudes
flask_session = requests.Session()

@csrf_exempt
def store_chart_image(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        image_data = data['image']
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
        if 'chart_images' not in request.session:
            request.session['chart_images'] = []
        request.session['chart_images'].append({
            'image': image_data,
            'timestamp': timestamp
        })
        request.session.modified = True
        return HttpResponse(status=200)
    return HttpResponse(status=400)

def index(request):
    context = {
        'xml_content': '',
        'processed_content': '',
        'error': ''
    }
    return render(request, 'index.html', context)

def reset(request):
    # Limpiar la sesión de Django
    request.session.flush()
    
    # Limpiar la sesión de Flask
    try:
        response = flask_session.get(f'{api}/reset_session')
        if response.status_code != 200:
            logger.error(f"Error al limpiar la sesión de Flask: {response.status_code}")
    except Exception as e:
        logger.error(f"Error conectando con Flask para limpiar la sesión: {str(e)}")
    
    # Redirigir a la página principal
    return redirect('index')

def format_xml(xml_string):
    """Formatea el XML con sangría adecuada y sin espacios adicionales"""
    try:
        # Si es un string válido de XML, formatearlo
        if isinstance(xml_string, str):
            # Remove literal '\n' strings and extra quotes
            xml_string = xml_string.replace('\\n', '\n').strip('"\'')
            
            if xml_string.strip().startswith('<?xml') or xml_string.strip().startswith('<'):
                dom = minidom.parseString(xml_string)
                formatted_xml = dom.toprettyxml(indent='  ')
                # Remove empty lines while preserving indentation
                lines = formatted_xml.split('\n')
                cleaned_lines = [line for line in lines if line.strip()]
                return '\n'.join(cleaned_lines)
        return xml_string
    except Exception as e:
        logger.error(f"Error formateando XML: {str(e)}")
        return xml_string

def remove_blank_lines(xml_string):
    """Elimina líneas en blanco manteniendo la indentación"""
    lines = xml_string.split('\n')
    return '\n'.join(line for line in lines if line.strip())

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

                        # Almacenar el contenido procesado en la sesión
                        request.session['processed_content'] = formatted_output
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

def store_request_data(request, data, request_type):
    if 'requests' not in request.session:
        request.session['requests'] = []
    
    # Add timestamp to the request data
    if isinstance(data, dict):
        data_with_timestamp = data.copy()
    else:
        data_with_timestamp = {'content': data}
    
    data_with_timestamp['timestamp'] = datetime.now().strftime('%Y%m%d%H%M%S%f')
    
    request.session['requests'].append({
        'type': request_type,
        'data': data_with_timestamp
    })
    request.session.modified = True

def consultar_datos(request):
    context = {
        'processed_content': request.session.get('processed_content', ''),
        'error': ''
    }
    store_request_data(request, context['processed_content'], 'consultar_datos')
    return render(request, 'consultar_datos.html', context)

def resumen_fecha(request):
    context = {'total': 0, 'positivos': 0, 'negativos': 0, 'neutros': 0, 'empresas': []}
    
    try:
        response = flask_session.get(f'{api}/obtener_empresas')
        if response.status_code == 200:
            empresas_data = response.json()
            context['empresas'] = empresas_data.get('empresas', [])
            
            if request.method == 'POST':
                fecha = request.POST.get('fecha')
                empresa = request.POST.get('empresa', 'todas')

                context['fecha'] = fecha
                context['empresa'] = empresa
                
                response = flask_session.get(f'{api}/resumen_fecha', params={'fecha': fecha, 'empresa': empresa})
                if response.status_code == 200:
                    data = response.json()
                    if data['total'] == 0:
                        context['error'] = 'No se encontraron mensajes para la fecha ingresada.'
                    else:
                        context.update(data)
                        store_request_data(request, context, 'resumen_fecha')
                else:
                    context['error'] = 'Error en la solicitud al servidor.'
        else:
            context['error'] = 'Error al obtener la lista de empresas.'
    except Exception as e:
        context['error'] = 'Error conectando con el servidor.'
    
    return render(request, 'resumen_fecha.html', context)

def resumen_rango_fecha(request):
    context = {'total': 0, 'positivos': 0, 'negativos': 0, 'neutros': 0, 'empresas': []}

    try:
        response = flask_session.get(f'{api}/obtener_empresas')
        if response.status_code == 200:
            empresas_data = response.json()
            context['empresas'] = empresas_data.get('empresas', [])

            if request.method == 'POST':
                fecha_inicio = request.POST.get('fecha_inicio')
                fecha_fin = request.POST.get('fecha_fin')
                empresa = request.POST.get('empresa', 'todas')

                context['fecha_inicio'] = fecha_inicio
                context['fecha_fin'] = fecha_fin
                context['empresa'] = empresa

                response = flask_session.get(f'{api}/resumen_rango_fecha', params={'fecha_inicio': fecha_inicio, 'fecha_fin': fecha_fin, 'empresa': empresa})
                if response.status_code == 200:
                    data = response.json()
                    if data['total'] == 0:
                        context['error'] = 'No se encontraron mensajes para el rango de fechas ingresado.'
                    else:
                        context.update(data)
                        store_request_data(request, context, 'resumen_rango_fecha')
                else:
                    context['error'] = 'Error en la solicitud al servidor.'
        else:
            context['error'] = 'Error al obtener la lista de empresas.'
    except Exception as e:
        context['error'] = 'Error conectando con el servidor.'
    
    return render(request, 'resumen_rango_fecha.html', context)

def prueba_mensaje(request):
    context = {}

    try:
        # Obtener empresas
        response_empresas = flask_session.get(f'{api}/obtener_empresas')
        if response_empresas.status_code == 200:
            empresas_data = response_empresas.json()
            context['empresas'] = empresas_data.get('empresas', [])
        else:
            context['error'] = 'Error al obtener la lista de empresas.'
            return render(request, 'prueba_mensaje.html', context)

        # Obtener servicios
        response_servicios = flask_session.get(f'{api}/obtener_servicios')
        if response_servicios.status_code == 200:
            servicios_data = response_servicios.json()
            context['servicios'] = servicios_data.get('servicios', [])
            context['servicios_con_alias'] = servicios_data.get('servicios_con_alias', {})
        else:
            context['error'] = 'Error al obtener la lista de servicios.'
            return render(request, 'prueba_mensaje.html', context)

        # Obtener alias
        response_alias = flask_session.get(f'{api}/obtener_alias')
        if response_alias.status_code == 200:
            alias_data = response_alias.json()
            context['servicios_con_alias'] = alias_data.get('servicios_con_alias', {})
            logger.debug(f"Alias obtenidos: {context['servicios_con_alias']}")
        else:
            context['error'] = 'Error al obtener los alias.'
            return render(request, 'prueba_mensaje.html', context)

        # Obtener palabras positivas y negativas
        response_palabras = flask_session.get(f'{api}/obtener_palabras')
        if response_palabras.status_code == 200:
            palabras_data = response_palabras.json()
            context['positive_words'] = palabras_data.get('positive_words', [])
            context['negative_words'] = palabras_data.get('negative_words', [])
        else:
            context['error'] = 'Error al obtener las palabras.'
            return render(request, 'prueba_mensaje.html', context)

        if request.method == 'POST':
            mensaje = request.POST.get('mensaje')
            
            # Estructurar los datos de las empresas y servicios como diccionarios
            empresas = []
            for empresa in context['empresas']:
                empresa_dict = {
                    'nombre': empresa,
                    'servicios': []
                }
                for servicio in context['servicios']:
                    # Añadir los alias correspondientes
                    alias = context['servicios_con_alias'].get(servicio, [])
                    empresa_dict['servicios'].append({
                        'nombre': servicio,
                        'alias': alias
                    })
                empresas.append(empresa_dict)
            
            # Preparar los datos para enviar a Flask
            payload = {
                'mensaje': mensaje,
                'empresas': empresas,
                'positive_words': context['positive_words'],
                'negative_words': context['negative_words']
            }
            
            # Enviar el mensaje XML y los datos adicionales a Flask
            try:
                response = requests.post(f"{api}/procesar_mensaje", json=payload)
                
                if response.status_code == 200:                
                    data = response.json()
                    if 'respuesta_xml' in data:
                        context['respuesta_xml'] = format_xml(data['respuesta_xml'])
                    else:
                        context['error'] = 'Error en el procesamiento del mensaje XML.'
                else:
                    context['error'] = 'Error en la solicitud a Flask.'
            except Exception as e:
                logger.error(f"Error enviando el mensaje a Flask: {str(e)}")
                context['error'] = f'Error enviando el mensaje a Flask: {str(e)}'
    except Exception as e:
        logger.error(f"Error conectando con el servidor: {str(e)}")
        context['error'] = f'Error conectando con el servidor: {str(e)}'
    
    return render(request, 'prueba_mensaje.html', context)

def generate_pdf(request):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y_position = height - 50  # Starting position from top
    
    requests_data = request.session.get('requests', [])
    chart_images = request.session.get('chart_images', [])
    
    # Create a dictionary to map chart images to their corresponding requests
    chart_map = {}
    for chart in chart_images:
        try:
            timestamp = datetime.strptime(chart['timestamp'], '%Y%m%d%H%M%S%f')
            chart_map[timestamp] = chart['image']
        except ValueError:
            logger.error(f"Invalid timestamp format: {chart['timestamp']}")
            continue

    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, y_position, "Reporte de Peticiones")
    y_position -= 40
    
    for req in requests_data:
        # Check if we need a new page
        if y_position < 100:
            p.showPage()
            p.setFont("Helvetica-Bold", 14)
            y_position = height - 50
        
        # Add title for each request
              
        
        
        if req['type'] == 'consultar_datos':
            p.setFont("Helvetica-Bold", 14)  
            p.drawString(50, y_position, f"Tipo de solicitud: Consultar Datos")
            y_position -= 30
            p.setFont("Helvetica", 12)
            # Extract XML content from the data structure
            xml_content = req['data'].get('content', req['data'])
            if isinstance(xml_content, dict):
                xml_content = xml_content.get('data', '')
            
            # Try to format the XML content
            try:
                # Remove any extra escapes and format the XML
                if isinstance(xml_content, str):
                    # Remove literal '\n' strings and clean up the string
                    xml_content = xml_content.replace('\\n', '\n')
                    xml_content = xml_content.strip('"\'')
                    
                    # If the content ends with timestamp information, remove it
                    timestamp_index = xml_content.find(", 'timestamp':")
                    if timestamp_index != -1:
                        xml_content = xml_content[:timestamp_index]
                    
                    # Format the XML with proper indentation
                    formatted_xml = format_xml(xml_content)
                    
                    # Split into lines and draw each line
                    lines = formatted_xml.split('\n')
                    
                    for line in lines:
                        if y_position < 50:
                            p.showPage()
                            p.setFont("Helvetica", 12)
                            y_position = height - 50
                        
                        # Calculate indentation level based on leading spaces
                        indent_level = (len(line) - len(line.lstrip())) // 2
                        x_position = 70 + (indent_level * 10)  # 10 pixels per indent level
                        
                        # Draw the line without the leading spaces
                        p.drawString(x_position, y_position, line.lstrip())
                        y_position -= 15
                
            except Exception as e:
                logger.error(f"Error formatting XML in PDF: {str(e)}")
                # Fallback: just print the raw content
                p.drawString(70, y_position, str(xml_content))
                y_position -= 15
                
        elif req['type'] in ['resumen_fecha', 'resumen_rango_fecha']:
            data = req['data']
            
            # Add date information
            if req['type'] == 'resumen_fecha':
                p.setFont("Helvetica-Bold", 14)
                p.drawString(50, y_position, f"Tipo de solicitud: Ver resumen de mensajes por fecha")
                y_position -= 30
                p.setFont("Helvetica", 12)
                p.drawString(70, y_position, f"Fecha: {data.get('fecha', 'N/A')}")
                y_position -= 20
            else:
                p.setFont("Helvetica-Bold", 14)
                p.drawString(50, y_position, f"Tipo de solicitud: Ver resumen de mensajes por rango de fechas")
                y_position -= 30
                p.setFont("Helvetica", 12)
                p.drawString(70, y_position, f"Fecha inicio: {data.get('fecha_inicio', 'N/A')}")
                y_position -= 20
                p.drawString(70, y_position, f"Fecha fin: {data.get('fecha_fin', 'N/A')}")
                y_position -= 20
            
            # Add company and statistics
            p.drawString(70, y_position, f"Empresa: {data.get('empresa', 'Todas')}")
            y_position -= 20
            
            # Statistics in a more organized layout
            stats_data = [
                ('Total de mensajes', data.get('total', 0)),
                ('Mensajes positivos', data.get('positivos', 0)),
                ('Mensajes negativos', data.get('negativos', 0)),
                ('Mensajes neutros', data.get('neutros', 0))
            ]
            
            for label, value in stats_data:
                if y_position < 50:
                    p.showPage()
                    p.setFont("Helvetica", 12)
                    y_position = height - 50
                p.drawString(70, y_position, f"{label}: {value}")
                y_position -= 20
            
            # Add corresponding chart if exists
            request_time_str = data.get('timestamp', '')
            if request_time_str:
                try:
                    request_time = datetime.strptime(request_time_str, '%Y%m%d%H%M%S%f')
                    
                    # Find the closest chart by timestamp
                    closest_chart_time = None
                    min_time_diff = float('inf')
                    
                    for chart_time in chart_map.keys():
                        time_diff = abs((chart_time - request_time).total_seconds())
                        if time_diff < min_time_diff and time_diff < 60:  # Within 60 seconds
                            min_time_diff = time_diff
                            closest_chart_time = chart_time
                    
                    if closest_chart_time:
                        # Ensure enough space for the chart
                        if y_position < 250:
                            p.showPage()
                            p.setFont("Helvetica", 12)
                            y_position = height - 50
                        
                        # Add chart title
                        p.setFont("Helvetica-Bold", 12)
                        p.drawString(70, y_position, "Gráfico de distribución de mensajes:")
                        y_position -= 20
                        p.setFont("Helvetica", 12)
                        
                        chart_data = chart_map[closest_chart_time]
                        image_data = base64.b64decode(chart_data.split(',')[1])
                        temp_image = f'temp_chart_{closest_chart_time.strftime("%Y%m%d%H%M%S")}.png'
                        
                        with open(temp_image, 'wb') as f:
                            f.write(image_data)
                        
                        # Add chart with proper positioning
                        p.drawImage(temp_image, 70, y_position - 200, width=400, height=200)
                        os.remove(temp_image)
                        y_position -= 220
                
                except (ValueError, KeyError) as e:
                    logger.error(f"Error processing chart for request: {str(e)}")
            
            y_position -= 30
        
        # Add spacing and separator line between requests
        if y_position < 50:
            p.showPage()
            p.setFont("Helvetica", 12)
            y_position = height - 50
            
        p.line(50, y_position + 20, width - 50, y_position + 20)
        y_position -= 40
    
    p.save()
    buffer.seek(0)
    return buffer

def descargar_pdf(request):
    buffer = generate_pdf(request)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="reporte.pdf"'
    return response


def ayuda(request):
    return render(request, 'ayuda.html')
