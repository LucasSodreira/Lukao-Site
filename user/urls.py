from django.urls import path
from user.views import *

app_name = 'user'

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('registrar/', RegisterView.as_view(), name='register'),
    path('order-detail/', Order_DetailView.as_view(), name='order_detail'),
    path('purchase-history/', Purchase_HistoryView.as_view(), name='purchase_history'),
    path('personal-info/', ProfileView.as_view(), name='personal_info'),
    path('address-management/', Addres_ManagementView.as_view(), name='address_management'),
    
]
