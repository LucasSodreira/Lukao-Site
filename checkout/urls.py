from django.urls import path
from checkout.views import *
# from . import webhooks # Comentado temporariamente

app_name = 'checkout'

urlpatterns = [
    path('select-address/', AddressSelection.as_view(), name='select_address'),
    path('select-frete/', ShipmentMethodView.as_view(), name='select_frete'),
    path('endereco/', EnderecoCreateView.as_view(), name='endereco'),
    path('endereco/<int:pk>/editar/', EnderecoEditView.as_view(), name='editar-endereco'),
    path('endereco/<int:pk>/excluir/', ExcluirEnderecoView.as_view(), name='excluir-endereco'),
    path('endereco/<int:pk>/principal/', DefinirEnderecoPrincipal.as_view(), name='definir-endereco-principal'),
    path('checkout_stripe/', checkout_stripe, name='checkout_stripe'),
    path('stripe_create_payment_intent/', stripe_create_payment_intent, name='stripe_create_payment_intent'),
    path('thanks/', ThanksView.as_view(), name='thanks'),
    path('ordem/', OrderSummaryView.as_view(), name='order-summary'),
    # path('stripe-webhook/', webhooks.stripe_webhook, name='stripe_webhook'), # Comentado temporariamente
]