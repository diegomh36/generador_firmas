from django import forms 
from .models import Page, Content

class PageForm(forms.ModelForm):
    contents = forms.ModelMultipleChoiceField(
        queryset=Content.objects.all(),  
        widget=forms.CheckboxSelectMultiple,  
        required=True,  
        label="Contenidos de formación"
    )

    class Meta:
        model = Page
        fields = ['name', 'assistants', 'date', 'contents']
        widgets = {
            'name': forms.TextInput(attrs={'class':'form-control', 'placeholder':'Introduzca aquí su nombre'}),
            'assistants': forms.NumberInput(attrs={'class':'form-control'}),
            'date': forms.DateInput(format="%Y-%m-%d", attrs={'class':'form-control', 'type':'date'}),
        }
