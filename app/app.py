from flask import Flask, render_template, request, redirect
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
from flask_cors import CORS
from flask import jsonify


app = Flask(__name__)
CORS(app)

listadoEmocionesPositivas = []
listadoEmocionesNegativas = []
listadoEmocionesNeutras = []

class Empresa:
    def __init__(self, nombre, servicios):
        self.nombre = nombre
        self.servicios = []

    def __str__(self):
        return f'Empresa: {self.nombre}, Servicios: {self.servicios}'
    
    def to_dict(self):
        return {
            'nombre': self.nombre,
            'servicios': [servicio.__dict__ for servicio in self.servicios]
        }

@app.route('/')
def index():
    return render_template('index.html', xml_content='')

@app.route('/procesar_xml', methods=['POST'])
def procesar_datos():
    try:
        file = request.files.get('archivo')
        if file and file.filename.endswith('.xml'):
            # Leer y procesar el XML
            xml_content = file.read().decode('utf-8')
            
            # Parsear y formatear el XML
            root = ET.fromstring(xml_content)
            formatted_xml = minidom.parseString(ET.tostring(root)).toprettyxml()
            
            return jsonify({
                'xml_content': xml_content,                
            })
        return jsonify({'error': 'Archivo no válido'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)