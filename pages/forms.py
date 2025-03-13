from django import forms 
from .models import Page, Content

class PageForm(forms.ModelForm):
    contents = forms.ModelMultipleChoiceField(
        queryset=Content.objects.all(),  
        widget=forms.CheckboxSelectMultiple,  
        required=True,  
        label="Contenidos de formación"
    )
    sign_all = forms.ChoiceField(
        choices=[("one", "Solo la persona responsable"), ("all", "Cada participante")],
        label="¿Quién firmará?",
        widget=forms.RadioSelect(attrs={"class": "form-check"})
    )

    class Meta:
        model = Page
        fields = ['name', 'assistants', 'date', 'contents', 'sign_all']
        widgets = {
            'name': forms.TextInput(attrs={'class':'form-control', 'placeholder':'Introduzca aquí su nombre'}),
            'assistants': forms.NumberInput(attrs={'class':'form-control'}),
            'date': forms.DateInput(format="%Y-%m-%d", attrs={'class':'form-control', 'type':'date'}),
        }