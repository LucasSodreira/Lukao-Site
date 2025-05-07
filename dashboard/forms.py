from django import forms
from core.models import Produto, ProdutoVariacao, Pedido, Reembolso, Cupom
from django.forms import inlineformset_factory
from django.contrib.auth import get_user_model
from django.conf import settings

class ProdutoForm(forms.ModelForm):
    class Meta:
        model = Produto
        fields = [
            'nome', 'descricao', 'preco', 'preco_original', 'preco_promocional',
            'promocao_inicio', 'promocao_fim', 'categoria', 'marca', 'tags',
            'estoque', 'imagem', 'visivel', 'ativo', 'destaque',
            'sku', 'codigo_barras', 'seo_title', 'seo_description',
            'peso', 'width', 'height', 'length'
        ]
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 4}),
            'promocao_inicio': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'promocao_fim': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'tags': forms.SelectMultiple(attrs={'class': 'form-select'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        preco_promocional = cleaned_data.get('preco_promocional')
        preco = cleaned_data.get('preco')
        if preco_promocional and preco and preco_promocional > preco:
            self.add_error('preco_promocional', 'O preço promocional deve ser menor que o preço atual.')
        return cleaned_data

ProdutoVariacaoFormSet = inlineformset_factory(
    Produto, ProdutoVariacao,
    fields=('cor', 'tamanho', 'estoque', 'sku', 'peso', 'width', 'height', 'length'),
    extra=1,
    can_delete=True
)

class PedidoUpdateForm(forms.ModelForm):
    class Meta:
        model = Pedido
        fields = ['status', 'codigo_rastreamento']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'codigo_rastreamento': forms.TextInput(attrs={'class': 'form-control'}),
        }

class ReembolsoProcessForm(forms.ModelForm):
    class Meta:
        model = Reembolso
        fields = ['status', 'notas']
        widgets = {
            'status': forms.Select(choices=[('A', 'Aprovado'), ('R', 'Rejeitado')], attrs={'class': 'form-select'}),
            'notas': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

class ClienteUpdateForm(forms.ModelForm):
    class Meta:
        model = get_user_model()
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

class CupomForm(forms.ModelForm):
    class Meta:
        model = Cupom
        fields = [
            'codigo', 'descricao', 'desconto_percentual', 'desconto_valor',
            'ativo', 'validade', 'uso_unico', 'max_usos', 'usos', 'usuario'
        ]
        widgets = {
            'codigo': forms.TextInput(attrs={'class': 'form-control'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'desconto_percentual': forms.NumberInput(attrs={'class': 'form-control'}),
            'desconto_valor': forms.NumberInput(attrs={'class': 'form-control'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'validade': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'uso_unico': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'max_usos': forms.NumberInput(attrs={'class': 'form-control'}),
            'usos': forms.NumberInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
            'usuario': forms.Select(attrs={'class': 'form-select'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        desconto_percentual = cleaned_data.get('desconto_percentual')
        desconto_valor = cleaned_data.get('desconto_valor')
        if not desconto_percentual and not desconto_valor:
            raise forms.ValidationError("Pelo menos um tipo de desconto deve ser fornecido.")
        if desconto_percentual and desconto_valor:
            raise forms.ValidationError("Apenas um tipo de desconto pode ser definido.")
        return cleaned_data