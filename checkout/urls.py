from django.urls import path
from checkout.views import *
from .views import usar_checkout_rapido, desativar_checkout_rapido, salvar_cep_usuario
from .webhooks import stripe_webhook

app_name = 'checkout'

urlpatterns = [
    path('select-address/', AddressSelection.as_view(), name='select_address'),
    path('select-frete/', ShipmentMethodView.as_view(), name='select_frete'),
    path('endereco/', EnderecoCreateView.as_view(), name='endereco'),
    path('endereco/<int:pk>/editar/', EnderecoEditView.as_view(), name='editar-endereco'),
    path('endereco/<int:pk>/excluir/', ExcluirEnderecoView.as_view(), name='excluir-endereco'),
    path('endereco/<int:pk>/principal/', DefinirEnderecoPrincipal.as_view(), name='definir-endereco-principal'),
    path('stripe_create_payment_intent/', stripe_create_payment_intent, name='stripe_create_payment_intent'),
    path('thanks/', ThanksView.as_view(), name='thanks'),
    path('ordem/', OrderSummaryView.as_view(), name='order-summary'),
    path('usar_checkout_rapido/', usar_checkout_rapido, name='usar_checkout_rapido'),
    path('desativar_checkout_rapido/', desativar_checkout_rapido, name='desativar_checkout_rapido'),
    path('salvar_cep/', salvar_cep_usuario, name='salvar_cep_usuario'),
    path('webhook/', stripe_webhook, name='stripe-webhook'),
]