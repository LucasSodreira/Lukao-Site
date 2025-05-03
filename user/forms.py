# forms.py
from django import forms
import re
from django.contrib.auth.forms import UserChangeForm, PasswordChangeForm
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from user.models import Perfil


User = get_user_model()

class CustomUserChangeForm(UserChangeForm):
    current_password = forms.CharField(
        label="Senha Atual",
        widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}),
        required=False
    )
    new_password = forms.CharField(
        label="Nova Senha",
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        required=False
    )
    confirm_password = forms.CharField(
        label="Confirmar Nova Senha",
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        required=False
    )

    class Meta:
        model = User
        fields = ('username', 'email',
                 'current_password', 'new_password', 'confirm_password')


    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        current_password = cleaned_data.get('current_password')

        if new_password or confirm_password or current_password:
            if not (new_password and confirm_password and current_password):
                raise ValidationError("Para alterar a senha, todos os campos de senha são obrigatórios")
            
            if new_password != confirm_password:
                raise ValidationError("As novas senhas não coincidem")
            
            user = self.instance
            if not user.check_password(current_password):
                raise ValidationError("Senha atual incorreta")
        
        return cleaned_data
    
class PerfilForm(forms.ModelForm):
    class Meta:
        model = Perfil
        fields = [
            'cpf', 'telefone', 'data_nascimento', 'sexo',
            'endereco_padrao', 'newsletter'
        ]
        widgets = {
            'data_nascimento': forms.DateInput(attrs={'type': 'date'}),
            'sexo': forms.Select(),
        }
        
        
    def clean_cpf(self):
        cpf = self.cleaned_data.get('cpf')
        if cpf:
            cpf = re.sub(r'[^0-9]', '', cpf)
            if len(cpf) != 11:
                raise ValidationError("CPF deve conter 11 dígitos")
        return cpf