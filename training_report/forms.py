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