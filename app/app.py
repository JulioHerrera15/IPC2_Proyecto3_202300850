from flask import Flask, request, jsonify, render_template, session
import xml.etree.ElementTree as ET
from datetime import datetime
import re
import logging
from flask_cors import CORS
from flask_session import Session

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SESSION_TYPE'] = 'filesystem'
app.secret_key = 'cL4V3s3cr3t4'

Session(app)

CORS(app, supports_credentials=True)

class Message:
    def __init__(self, date, social_network, user, companies, text):
        self.date = date
        self.social_network = social_network
        self.user = user
        self.companies = companies
        self.text = text
        self.positive_words = 0
        self.negative_words = 0

def extract_message_info(message_text):
    # Extract date
    date_match = re.search(r'(\d{2}/\d{2}/\d{4})', message_text)
    date = date_match.group(1).strip() if date_match else None
    
    # Extract social network
    social_match = re.search(r'Red social: (\w+)', message_text)
    social_network = social_match.group(1).strip() if social_match else None
    
    # Extract user
    user_match = re.search(r'Usuario: ([^\n]+)', message_text)
    user = user_match.group(1).strip() if user_match else None
    
    return date, social_network, user

def analyze_sentiment(text, positive_words, negative_words):
    text_lower = text.lower()
    pos_count = sum(1 for word in positive_words if word.lower() in text_lower)
    neg_count = sum(1 for word in negative_words if word.lower() in text_lower)
    
    total_words = pos_count + neg_count
    if total_words == 0:
        return 0, 0, "neutro"
        
    pos_percentage = (pos_count / total_words) * 100
    neg_percentage = (neg_count / total_words) * 100
    
    sentiment = "positivo" if pos_count > neg_count else "negativo" if neg_count > pos_count else "neutro"
    
    return pos_count, neg_count, sentiment

def detect_companies_and_services(text, companies_dict):
    detected = []
    text_lower = text.lower()
    
    for company in companies_dict:
        company_name = company['nombre'].strip().lower()
        # Verificar si el nombre de la empresa está en el texto
        if re.search(r'\b' + re.escape(company_name) + r'\b', text_lower):
            for service in company['servicios']:
                service_name = service['nombre'].strip().lower()
                # Normalizar alias para evitar espacios o mayúsculas
                aliases = [alias.strip().lower() for alias in service.get('alias', [])]
                
                # Verificar si el nombre del servicio o algún alias está en el texto
                if re.search(r'\b' + re.escape(service_name) + r'\b', text_lower) or \
                    any(re.search(r'\b' + re.escape(alias) + r'\b', text_lower) for alias in aliases):
                    detected.append({
                        'nombre': company['nombre'].strip(),
                        'servicio': service['nombre'].strip()
                    })
                    logger.debug(f"Empresa '{company['nombre']}' y servicio '{service['nombre']}' detectados en el mensaje.")

    return detected


@app.route('/reset_session', methods=['GET'])
def reset_session():
    session.clear()
    return jsonify({'status': 'success'})

@app.route('/procesar_xml', methods=['POST'])
def procesar_datos():
    try:
        file = request.files.get('archivo')
        if not file:
            return jsonify({'error': 'No se recibió ningún archivo'}), 400

        # Leer archivo XML
        tree = ET.parse(file)
        root = tree.getroot()

        # Extraer palabras positivas y negativas
        positive_words = [word.text for word in root.findall('.//sentimientos_positivos/palabra')]
        negative_words = [word.text for word in root.findall('.//sentimientos_negativos/palabra')]

        # Log palabras positivas y negativas
        logger.debug(f"Palabras positivas extraídas: {positive_words}")
        logger.debug(f"Palabras negativas extraídas: {negative_words}")

        
        # Extraer empresas y servicios
        companies = []
        for empresa in root.findall('.//empresas_analizar/empresa'):
            company_dict = {
                'nombre': empresa.find('nombre').text,
                'servicios': []
            }
            for servicio in empresa.findall('.//servicios/servicio'):
                service_dict = {
                    'nombre': servicio.get('nombre'),
                    'alias': [alias.text for alias in servicio.findall('alias')]
                }
                company_dict['servicios'].append(service_dict)
            companies.append(company_dict)
        
        # Log empresas extraídas
        logger.debug(f"Empresas extraídas: {companies}")

        # Almacenar empresas y palabras en la sesión
        session['companies'] = companies
        session['positive_words'] = positive_words
        session['negative_words'] = negative_words
        session.modified = True
        logger.debug("Datos almacenados en la sesión con éxito")        


        # Procesar mensajes
        messages = []
        for mensaje in root.findall('.//lista_mensajes/mensaje'):
            message_text = mensaje.text
            date, social_network, user = extract_message_info(message_text)
            
            detected_companies = detect_companies_and_services(message_text, companies)
            pos_count, neg_count, sentiment = analyze_sentiment(message_text, positive_words, negative_words)
            
            if detected_companies:
                messages.append({
                    'date': date,
                    'social_network': social_network,
                    'user': user,
                    'companies': detected_companies,
                    'positive_words': pos_count,
                    'negative_words': neg_count,
                    'sentiment': sentiment
                })

        # Almacenar mensajes en la sesión
        session['messages'] = messages
        logger.debug(f"Mensajes almacenados en la sesión: {messages}")


        # Crear XML de salida
        output_root = ET.Element('lista_respuestas')
        
        # Agrupar mensajes por fecha
        messages_by_date = {}
        for msg in messages:
            date = msg['date']
            if date not in messages_by_date:
                messages_by_date[date] = []
            messages_by_date[date].append(msg)

        # Crear elementos
        for date, date_messages in messages_by_date.items():
            respuesta = ET.SubElement(output_root, 'respuesta')
            
            fecha = ET.SubElement(respuesta, 'fecha')
            fecha.text = date
            
            mensajes = ET.SubElement(respuesta, 'mensajes')
            total = ET.SubElement(mensajes, 'total')
            total.text = str(len(date_messages))
            
            positivos = ET.SubElement(mensajes, 'positivos')
            negativos = ET.SubElement(mensajes, 'negativos')
            neutros = ET.SubElement(mensajes, 'neutros')
            
            pos_count = sum(1 for msg in date_messages if msg['sentiment'] == 'positivo')
            neg_count = sum(1 for msg in date_messages if msg['sentiment'] == 'negativo')
            neu_count = sum(1 for msg in date_messages if msg['sentiment'] == 'neutro')
            
            positivos.text = str(pos_count)
            negativos.text = str(neg_count)
            neutros.text = str(neu_count)
            
            analisis = ET.SubElement(respuesta, 'analisis')
            
            # Procesar datos de empresas
            companies_data = {}
            for msg in date_messages:
                for company in msg['companies']:
                    company_name = company['nombre']
                    service_name = company['servicio']
                    
                    if company_name not in companies_data:
                        companies_data[company_name] = {
                            'total': 0,
                            'positivos': 0,
                            'negativos': 0,
                            'neutros': 0,
                            'servicios': {}
                        }
                    
                    companies_data[company_name]['total'] += 1
                    if msg['sentiment'] == 'positivo':
                        companies_data[company_name]['positivos'] += 1
                    elif msg['sentiment'] == 'negativo':
                        companies_data[company_name]['negativos'] += 1
                    else:
                        companies_data[company_name]['neutros'] += 1
                        
                    if service_name not in companies_data[company_name]['servicios']:
                        companies_data[company_name]['servicios'][service_name] = {
                            'total': 0,
                            'positivos': 0,
                            'negativos': 0,
                            'neutros': 0
                        }
                    
                    companies_data[company_name]['servicios'][service_name]['total'] += 1
                    if msg['sentiment'] == 'positivo':
                        companies_data[company_name]['servicios'][service_name]['positivos'] += 1
                    elif msg['sentiment'] == 'negativo':
                        companies_data[company_name]['servicios'][service_name]['negativos'] += 1
                    else:
                        companies_data[company_name]['servicios'][service_name]['neutros'] += 1

            # Añadir empresas al XML
            for company_name, company_data in companies_data.items():
                empresa = ET.SubElement(analisis, 'empresa')
                empresa.set('nombre', company_name)
                
                mensajes_empresa = ET.SubElement(empresa, 'mensajes')
                total = ET.SubElement(mensajes_empresa, 'total')
                total.text = str(company_data['total'])
                
                positivos = ET.SubElement(mensajes_empresa, 'positivos')
                positivos.text = str(company_data['positivos'])
                
                negativos = ET.SubElement(mensajes_empresa, 'negativos')
                negativos.text = str(company_data['negativos'])
                
                neutros = ET.SubElement(mensajes_empresa, 'neutros')
                neutros.text = str(company_data['neutros'])
                
                servicios = ET.SubElement(empresa, 'servicios')
                for service_name, service_data in company_data['servicios'].items():
                    servicio = ET.SubElement(servicios, 'servicio')
                    servicio.set('nombre', service_name)
                    
                    mensajes_servicio = ET.SubElement(servicio, 'mensajes')
                    total = ET.SubElement(mensajes_servicio, 'total')
                    total.text = str(service_data['total'])
                    
                    positivos = ET.SubElement(mensajes_servicio, 'positivos')
                    positivos.text = str(service_data['positivos'])
                    
                    negativos = ET.SubElement(mensajes_servicio, 'negativos')
                    negativos.text = str(service_data['negativos'])
                    
                    neutros = ET.SubElement(mensajes_servicio, 'neutros')
                    neutros.text = str(service_data['neutros'])

        # Convertir XML a string
        output_xml = ET.tostring(output_root, encoding='unicode', method='xml')
        
        return jsonify({
            'xml_content': output_xml
        })

    except Exception as e:
        logger.error(f"Error processing XML: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/peticiones', methods=['GET'])
def peticiones():
    messages = session.get('messages', [])
    logger.debug(f"Mensajes recuperados: {messages}")
    return jsonify({'messages': messages})

@app.route('/obtener_empresas', methods=['GET'])
def obtener_empresas():
    messages = session.get('messages', [])
    empresas = set()
    for message in messages:
        for company in message['companies']:
            empresas.add(company['nombre'])
        logger.debug(f"Empresa detectada: {company['nombre']}")           
    
    return jsonify({'empresas': list(empresas)})
    

@app.route('/obtener_servicios', methods=['GET'])
def obtener_servicios():
    messages = session.get('messages', [])
    servicios = set()
    for message in messages:
        for company in message['companies']:
            servicios.add(company['servicio'])
            logger.debug(f"Servicio detectado: {company['servicio']}")
    return jsonify({'servicios': list(servicios)})

@app.route('/obtener_alias', methods=['GET'])
def obtener_alias():
    companies = session.get('companies', [])
    servicios_con_alias = {}
    for company in companies:
        for servicio in company['servicios']:
            if 'alias' in servicio:
                servicios_con_alias[servicio['nombre']] = servicio['alias']
                for alias_item in servicio['alias']:
                    logger.debug(f"Alias detectado: {alias_item} para servicio: {servicio['nombre']}")
            else:
                logger.debug(f"Servicio sin 'alias': {servicio}")
    return jsonify({'servicios_con_alias': servicios_con_alias})

@app.route('/obtener_palabras', methods=['GET'])
def obtener_palabras():
    positive_words = session.get('positive_words', [])
    negative_words = session.get('negative_words', [])
    logger.debug(f"Palabras positivas recuperadas: {positive_words}")
    logger.debug(f"Palabras negativas recuperadas: {negative_words}")
    return jsonify({'positive_words': positive_words, 'negative_words': negative_words})

@app.route('/resumen_fecha', methods=['GET'])
def resumen_fecha():    
    # Obtener parámetros de fecha y empresa
    fecha = request.args.get('fecha')
    empresa = request.args.get('empresa', 'todas')

    # Convertir la fecha al formato 'dd/mm/yyyy' si no está en ese formato
    try:
        fecha = datetime.strptime(fecha, '%Y-%m-%d').strftime('%d/%m/%Y')
    except ValueError:
        pass  # Si ya está en el formato correcto, no hacer nada

    # Obtener mensajes de la sesión
    messages = session.get('messages', [])
    logger.debug(f"Mensajes recuperados de la sesión antes de aplicar filtros: {messages}")

    # Filtrar por fecha
    messages = [msg for msg in messages if msg['date'] == fecha]
    logger.debug(f"Mensajes después de filtrar por fecha ({fecha}): {messages}")
    
    # Filtrar por empresa si es especificada
    if empresa.lower() != 'todas':
        messages = [msg for msg in messages if any(c['nombre'] == empresa for c in msg['companies'])]
        logger.debug(f"Mensajes después de filtrar por empresa ({empresa}): {messages}")    

    # Contar mensajes clasificados
    total = len(messages)
    positivos = sum(1 for msg in messages if msg['sentiment'] == 'positivo')
    negativos = sum(1 for msg in messages if msg['sentiment'] == 'negativo')
    neutros = sum(1 for msg in messages if msg['sentiment'] == 'neutro')
    
    logger.debug(f"Conteos - Total: {total}, Positivos: {positivos}, Negativos: {negativos}, Neutros: {neutros}")

    return jsonify({
        'total': total,
        'positivos': positivos,
        'negativos': negativos,
        'neutros': neutros
    })

from datetime import datetime

@app.route('/resumen_rango_fecha', methods=['GET'])
def resumen_rango_fecha():
    # Obtener parámetros de fecha inicio, fin y empresa
    fecha_inicio = request.args.get('fecha_inicio')
    fecha_fin = request.args.get('fecha_fin')
    empresa = request.args.get('empresa', 'todas')

    # Convertir las fechas a objetos datetime
    try:
        fecha_inicio_dt = datetime.strptime(fecha_inicio, '%Y-%m-%d')
        fecha_fin_dt = datetime.strptime(fecha_fin, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': 'Formato de fecha no válido'}), 400

    # Obtener mensajes de la sesión
    messages = session.get('messages', [])
    logger.debug(f"Mensajes recuperados de la sesión antes de aplicar filtros: {messages}")

    # Filtrar por rango de fechas convirtiendo `msg['date']` también a datetime
    filtered_messages = []
    for msg in messages:
        try:
            msg_date = datetime.strptime(msg['date'], '%d/%m/%Y')
            if fecha_inicio_dt <= msg_date <= fecha_fin_dt:
                filtered_messages.append(msg)
        except ValueError:
            logger.warning(f"Formato de fecha no válido en el mensaje: {msg['date']}")

    logger.debug(f"Mensajes después de filtrar por rango de fechas ({fecha_inicio} - {fecha_fin}): {filtered_messages}")

    # Filtrar por empresa si es especificada
    if empresa.lower() != 'todas':
        filtered_messages = [msg for msg in filtered_messages if any(c['nombre'] == empresa for c in msg['companies'])]
        logger.debug(f"Mensajes después de filtrar por empresa ({empresa}): {filtered_messages}")

    # Contar mensajes clasificados
    total = len(filtered_messages)
    positivos = sum(1 for msg in filtered_messages if msg['sentiment'] == 'positivo')
    negativos = sum(1 for msg in filtered_messages if msg['sentiment'] == 'negativo')
    neutros = sum(1 for msg in filtered_messages if msg['sentiment'] == 'neutro')

    logger.debug(f"Conteos - Total: {total}, Positivos: {positivos}, Negativos: {negativos}, Neutros: {neutros}")

    return jsonify({
        'total': total,
        'positivos': positivos,
        'negativos': negativos,
        'neutros': neutros
    })

# Endpoint para procesar el mensaje individual
@app.before_request
def before_request():
    logger.debug(f"Contenido de la sesión antes de la solicitud: {session.items()}")

@app.route('/procesar_mensaje', methods=['POST'])
def procesar_mensaje():
    data = request.get_json()
    mensaje = data.get('mensaje')
    empresas = data.get('empresas', [])
    positive_words = data.get('positive_words', [])
    negative_words = data.get('negative_words', [])
    
    try:
        logger.debug(f"Mensaje XML recibido: {mensaje}")
        logger.debug(f"Empresas recibidas: {empresas}")
        logger.debug(f"Palabras positivas recibidas: {positive_words}")
        logger.debug(f"Palabras negativas recibidas: {negative_words}")

        # Parsear el mensaje XML de entrada
        root = ET.fromstring(mensaje)
        mensaje_texto = root.text.strip().lower()  # Convertir a minúsculas para normalizar
        logger.debug(f"Mensaje de texto procesado: {mensaje_texto}")
        
        # Extraer información del mensaje usando regex
        fecha = re.search(r"\d{2}/\d{2}/\d{4}", mensaje_texto).group(0)
        usuario = re.search(r"usuario:\s*(\S+)", mensaje_texto).group(1)
        red_social = re.search(r"red social:\s*(\S+)", mensaje_texto).group(1)
        logger.debug(f"Fecha extraída: {fecha}, Usuario extraído: {usuario}, Red social extraída: {red_social}")

        # Normalizar listas de palabras positivas y negativas
        positive_words = [word.lower().strip() for word in positive_words]
        negative_words = [word.lower().strip() for word in negative_words]

        # Contar palabras positivas y negativas en el mensaje
        pos_count = sum(1 for word in re.findall(r'\b\w+\b', mensaje_texto) if word in positive_words)
        neg_count = sum(1 for word in re.findall(r'\b\w+\b', mensaje_texto) if word in negative_words)
        logger.debug(f"Palabras positivas contadas: {pos_count}")
        logger.debug(f"Palabras negativas contadas: {neg_count}")

        # Análisis de sentimiento
        sentimiento_total = pos_count + neg_count
        porcentaje_positivo = (pos_count / sentimiento_total) * 100 if sentimiento_total else 0
        porcentaje_negativo = (neg_count / sentimiento_total) * 100 if sentimiento_total else 0
        sentimiento_final = "positivo" if porcentaje_positivo > porcentaje_negativo else "negativo"
        logger.debug(f"Análisis de sentimiento: {sentimiento_final}")

        # Extraer empresas y servicios mencionados en el mensaje
        logger.debug("Entrando a la función para detectar compañías y servicios")
        empresas_detectadas = []
        
        for company in empresas:
            if isinstance(company, dict) and 'nombre' in company and 'servicios' in company:
                company_name = company['nombre'].strip().lower()
                logger.debug(f"Procesando empresa: {company_name}")
                
                # Verificar si la empresa está mencionada en el mensaje
                if re.search(r'\b' + re.escape(company_name) + r'\b', mensaje_texto):
                    servicios_detectados = set()  # Usar set para evitar duplicados
                    
                    for servicio in company['servicios']:
                        if isinstance(servicio, dict) and 'nombre' in servicio and 'alias' in servicio:
                            # Verificar cada alias del servicio
                            for alias in servicio['alias']:
                                alias = alias.strip().lower()
                                if re.search(r'\b' + re.escape(alias) + r'\b', mensaje_texto):
                                    # Si encuentra el alias, agregar el nombre del servicio
                                    servicios_detectados.add(servicio['nombre'].strip())
                                    logger.debug(f"Alias '{alias}' encontrado para servicio: {servicio['nombre']}")
                    
                    # Solo agregar la empresa si se detectaron servicios
                    if servicios_detectados:
                        empresas_detectadas.append({
                            'nombre': company['nombre'].strip(),
                            'servicios': list(servicios_detectados)
                        })
                        logger.debug(f"Empresa detectada: {company['nombre']} con servicios: {list(servicios_detectados)}")

        # Crear XML de salida
        respuesta = ET.Element('respuesta')
        ET.SubElement(respuesta, 'fecha').text = fecha
        ET.SubElement(respuesta, 'red_social').text = red_social
        ET.SubElement(respuesta, 'usuario').text = usuario
        empresas_element = ET.SubElement(respuesta, 'empresas')

        for empresa in empresas_detectadas:
            empresa_element = ET.SubElement(empresas_element, 'empresa', nombre=empresa['nombre'])
            for servicio in empresa['servicios']:
                ET.SubElement(empresa_element, 'servicio').text = servicio

        ET.SubElement(respuesta, 'palabras_positivas').text = str(pos_count)
        ET.SubElement(respuesta, 'palabras_negativas').text = str(neg_count)
        ET.SubElement(respuesta, 'sentimiento_positivo').text = f"{porcentaje_positivo:.2f}%"
        ET.SubElement(respuesta, 'sentimiento_negativo').text = f"{porcentaje_negativo:.2f}%"
        ET.SubElement(respuesta, 'sentimiento_analizado').text = sentimiento_final

        # Convertir el XML de respuesta a cadena
        respuesta_xml = ET.tostring(respuesta, encoding="utf-8").decode("utf-8")
        logger.debug(f"XML de respuesta generado: {respuesta_xml}")
        return jsonify({'respuesta_xml': respuesta_xml})

    except Exception as e:
        logger.error(f"Error al procesar el mensaje: {str(e)}")
        return jsonify({'error': f"Error al procesar el mensaje: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)