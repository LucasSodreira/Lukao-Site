from django.urls import path
from checkout.views import *
app_name = 'checkout'

urlpatterns = [
    path('select-address/', AddressSelection.as_view(), name='select_address'),
    path('select-frete/', ShipmentMethodView.as_view(), name='select_frete'),
    
    path('endereco/', EnderecoCreateView.as_view(), name='endereco'),
    path('endereco/<int:pk>/editar/', EnderecoEditView.as_view(), name='editar-endereco'),
    path('endereco/<int:pk>/excluir/', ExcluirEnderecoView.as_view(), name='excluir-endereco'),
    path('endereco/<int:pk>/principal/', DefinirEnderecoPrincipal.as_view(), name='definir-endereco-principal'),
    
    path('ordem/', OrderSummaryView.as_view(), name='order-summary'),
    path('thanks/', ThanksView.as_view(), name='thanks'),
]