from django.urls import path
from dashboard.views import *

app_name = 'dashboard'

urlpatterns = [
    path('painel/', dashboard_overview, name='dashboard_home'),
    path('produtos/', produto_list, name='produto_list'),
    path('produtos/novo/', produto_create, name='produto_create'),
    path('produtos/<int:pk>/editar/', produto_update, name='produto_update'),
    path('produtos/<int:pk>/excluir/', produto_delete, name='produto_delete'),
    path('pedidos/', pedido_list, name='pedido_list'),
    path('pedidos/<int:pk>/', pedido_detail, name='pedido_detail'),
    path('pedidos/<int:pk>/atualizar/', pedido_update, name='pedido_update'),
    path('pedidos/<int:pk>/cancelar/', pedido_cancel, name='pedido_cancel'),
    path('pedidos/<int:pk>/gerar-etiqueta/', pedido_gerar_etiqueta, name='pedido_gerar_etiqueta'),
    path('pedidos/exportar/csv/', pedido_export_csv, name='pedido_export_csv'),
    path('reembolsos/', reembolso_list, name='reembolso_list'),
    path('reembolsos/<int:pk>/processar/', reembolso_process, name='reembolso_process'),
    path('relatorios/reembolsos/', relatorios_reembolsos, name='relatorios_reembolsos'),
    path('notificacoes/', notificacoes_list, name='notificacoes_list'),
    path('clientes/', cliente_list, name='cliente_list'),
    path('clientes/<int:pk>/', cliente_detail, name='cliente_detail'),
    path('clientes/<int:pk>/editar/', cliente_update, name='cliente_update'),
    path('estoque/', estoque_list, name='estoque_list'),
    path('cupons/', cupom_list, name='cupom_list'),
    path('cupons/novo/', cupom_create, name='cupom_create'),
    path('cupons/<int:pk>/editar/', cupom_update, name='cupom_update'),
    path('cupons/<int:pk>/excluir/', cupom_delete, name='cupom_delete'),
]