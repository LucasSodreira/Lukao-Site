import django_filters
from core.models import Produto, Pedido, Reembolso, Categoria, Marca, Cupom
from django.conf import settings
from django.db import models
from django.db.models import Count
from django.contrib.auth import get_user_model

User = settings.AUTH_USER_MODEL

class ProdutoFilter(django_filters.FilterSet):
    nome = django_filters.CharFilter(lookup_expr='icontains', label='Nome')
    categoria = django_filters.ModelChoiceFilter(queryset=Categoria.objects.all(), label='Categoria')
    marca = django_filters.ModelChoiceFilter(queryset=Marca.objects.all(), label='Marca')
    estoque = django_filters.RangeFilter(label='Estoque (Mín-Máx)')
    ativo = django_filters.BooleanFilter(label='Ativo')

    class Meta:
        model = Produto
        fields = ['nome', 'categoria', 'marca', 'estoque', 'ativo']

class PedidoFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=Pedido.STATUS_CHOICES, label='Status')
    data_criacao = django_filters.DateFromToRangeFilter(label='Data de Criação')
    usuario = django_filters.CharFilter(field_name='usuario__username', lookup_expr='icontains', label='Usuário')
    total = django_filters.RangeFilter(label='Valor Total (R$)')
    cupom = django_filters.ModelChoiceFilter(queryset=Cupom.objects.all(), label='Cupom Usado')

    class Meta:
        model = Pedido
        fields = ['status', 'data_criacao', 'usuario', 'total', 'cupom']

class ReembolsoFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=Reembolso.STATUS_CHOICES, label='Status')
    pedido = django_filters.NumberFilter(field_name='pedido__id', label='ID do Pedido')

    class Meta:
        model = Reembolso
        fields = ['status', 'pedido']

class RelatorioReembolsoFilter(django_filters.FilterSet):
    data_criacao = django_filters.DateFromToRangeFilter(label='Data de Criação')
    status = django_filters.ChoiceFilter(choices=Reembolso.STATUS_CHOICES, label='Status')

    class Meta:
        model = Reembolso
        fields = ['data_criacao', 'status']

class ClienteFilter(django_filters.FilterSet):
    nome = django_filters.CharFilter(method='filter_nome', label='Nome')
    total_pedidos = django_filters.RangeFilter(method='filter_total_pedidos', label='Número de Pedidos')

    class Meta:
        model = get_user_model()
        fields = ['nome', 'total_pedidos']

    def filter_nome(self, queryset, name, value):
        return queryset.filter(
            models.Q(username__icontains=value) |
            models.Q(first_name__icontains=value) |
            models.Q(last_name__icontains=value)
        )

    def filter_total_pedidos(self, queryset, name, value):
        return queryset.annotate(total_pedidos=Count('pedidos')).filter(
            total_pedidos__range=(value.start or 0, value.stop or float('inf'))
        )
        
class EstoqueFilter(django_filters.FilterSet):
    nome = django_filters.CharFilter(lookup_expr='icontains', label='Nome')
    categoria = django_filters.ModelChoiceFilter(queryset=Categoria.objects.all(), label='Categoria')
    estoque = django_filters.RangeFilter(label='Estoque (Mín-Máx)')

    class Meta:
        model = Produto
        fields = ['nome', 'categoria', 'estoque']

class CupomFilter(django_filters.FilterSet):
    codigo = django_filters.CharFilter(lookup_expr='icontains', label='Código')
    validade = django_filters.DateFromToRangeFilter(label='Validade')

    class Meta:
        model = Cupom
        fields = ['codigo', 'validade']