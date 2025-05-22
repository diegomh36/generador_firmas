from django import forms
from .models import TrainingReport, Content
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Field

class TrainingReportForm(forms.ModelForm):
    contents = forms.ModelMultipleChoiceField(
        queryset=Content.objects.all(),
        required=False,  # Cambiado a False para permitir solo nuevos contenidos
        label="Contenidos existentes",
        widget=forms.CheckboxSelectMultiple()
    )
    
    new_contents = forms.CharField(
        required=False,
        label="Nuevos contenidos (separados por comas)",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Contenido 1, Contenido 2'})
    )
    
    sign_all = forms.ChoiceField(
        choices=[("one", "Solo la persona responsable"), ("all", "Cada participante")],
        label="¿Quién firmará?",
        widget=forms.RadioSelect(attrs={"class": "form-check"})
    )
    
    class Meta:
        model = TrainingReport
        fields = ['name', 'assistants', 'date', 'contents', 'new_contents', 'sign_all']
        widgets = {
            'name': forms.TextInput(attrs={'class':'form-control', 'placeholder':'Introduzca aquí su nombre'}),
            'assistants': forms.NumberInput(attrs={'class':'form-control'}),
            'date': forms.DateTimeInput(format="%Y-%m-%d %H:%M", attrs={'class': 'form-control', 'type': 'datetime-local'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_id = 'training-form'
        
        self.helper.layout = Layout(
            Row(
                Column('name', css_class='form-group col-md-6 mb-0'),
                Column('assistants', css_class='form-group col-md-6 mb-0'),
                css_class='form-row'
            ),
            Row(
                Column('date', css_class='form-group col-md-6 mb-0'),
                Column('sign_all', css_class='form-group col-md-6 mb-0'),
                css_class='form-row'
            ),
            Field('contents'),
            Field('new_contents'),
            Submit('submit', 'Siguiente', css_class='btn btn-primary mt-3')
        )

class ImagenForm(forms.Form):
    imagen = forms.ImageField()

class VerificationForm(forms.Form):
    titular = forms.CharField(
        label='Titular o Fragmento de la Noticia',
        widget=forms.Textarea(attrs={'rows': 3}),
        required=True,
        help_text='Ingrese el titular o un fragmento del texto que desea verificar.'
    )
    url = forms.URLField(
        label='URL de la Noticia (Opcional)',
        required=False,
        help_text='Proporcionar la URL puede mejorar la precisión del análisis.'
    )
    texto_completo = forms.CharField(
        label='Texto Completo de la Noticia (Opcional)',
        widget=forms.Textarea(attrs={'rows': 10}),
        required=False,
        help_text='Pegar el texto completo permite un análisis más detallado, especialmente útil para noticias de pago.'
    )

# verificador_noticias/forms.py

# ... (otros formularios) ...

class ImageVerificationForm(forms.Form):
    imagen = forms.ImageField(
        label='Subir Imagen de la Noticia',
        required=True, # ¡Ahora es obligatorio!
        help_text='Sube una captura de pantalla del titular o de la noticia. Solo PNG, JPEG, WEBP.'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'imagen',
            Submit('submit', 'Analizar Imagen de Noticia', css_class='btn btn-primary mt-3')
        )