# forms.py (Django)
from django import forms

class FileForm(forms.Form):
    archivo = forms.FileField(
        label='Archivo XML',
        required=True
    )