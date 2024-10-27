from flask import Flask, request, jsonify, render_template, session
import xml.etree.ElementTree as ET
from datetime import datetime
import re
import logging
from flask_cors import CORS

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'cL4V3s3cr3t4'  # Cambia esto a una clave secreta segura
CORS(app)

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
        if company_name in text_lower:
            for service in company['servicios']:
                service_name = service['nombre'].strip().lower()
                aliases = [alias.strip().lower() for alias in service.get('alias', [])]
                
                if service_name in text_lower or any(alias in text_lower for alias in aliases):
                    detected.append({
                        'nombre': company['nombre'].strip(),
                        'servicio': service['nombre'].strip()
                    })
    
    return detected

@app.route('/procesar_xml', methods=['POST'])
def procesar_datos():
    try:
        file = request.files.get('archivo')
        if not file:
            return jsonify({'error': 'No se recibió ningún archivo'}), 400

        # Parse input XML
        tree = ET.parse(file)
        root = tree.getroot()

        # Extract dictionary data
        positive_words = [word.text for word in root.findall('.//sentimientos_positivos/palabra')]
        negative_words = [word.text for word in root.findall('.//sentimientos_negativos/palabra')]
        
        # Extract companies and services
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

        # Process messages
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

        # Store messages in session
        session['messages'] = messages

        # Generate output XML
        output_root = ET.Element('lista_respuestas')
        
        # Group messages by date
        messages_by_date = {}
        for msg in messages:
            date = msg['date']
            if date not in messages_by_date:
                messages_by_date[date] = []
            messages_by_date[date].append(msg)

        # Create response elements
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
            
            # Process companies
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

            # Add companies to XML
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

        # Convert to string
        output_xml = ET.tostring(output_root, encoding='unicode', method='xml')
        
        return jsonify({
            'xml_content': output_xml
        })

    except Exception as e:
        logger.error(f"Error processing XML: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/consultar_datos', methods=['GET'])
def consultar_datos():
    messages = session.get('messages', [])
    return render_template('resultados.html', messages=messages)

if __name__ == '__main__':
    app.run(debug=True, port=5000)