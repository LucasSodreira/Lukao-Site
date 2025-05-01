from django import forms
from core.models import Endereco

class EnderecoForm(forms.ModelForm):
    class Meta:
        model = Endereco
        fields = ['nome_completo', 'telefone', 'cep', 'estado', 'cidade', 
                 'bairro', 'rua', 'numero', 'complemento', 'principal']
        widgets = {
            'telefone': forms.TextInput(attrs={
                'placeholder': '(99) 99999-9999',
                'data-mask': '(00) 00000-0000'
            }),
            'cep': forms.TextInput(attrs={
                'placeholder': '12345-678',
                'data-mask': '00000-000'
            }),
            'complemento': forms.TextInput(attrs={
                'placeholder': 'Opcional'
            })
        }