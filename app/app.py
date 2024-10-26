from flask import Flask, render_template, request, redirect
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html', xml_content='', processed_content='')

@app.route('/procesar_xml', methods=['POST'])
def procesar_datos():
    file = request.files['archivo']
    if file and file.filename.endswith('.xml'):
        xml_content = file.read().decode('utf-8')
        
        # Parsear el contenido XML
        root = ET.fromstring(xml_content)

        minidom.parseString(xml_content).toprettyxml()
        

        return render_template('index.html', xml_content=xml_content)
    else:
        return redirect('/')

if __name__ == '__main__':
    app.run(debug=True, port=5000)