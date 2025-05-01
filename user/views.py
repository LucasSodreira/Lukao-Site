from django.shortcuts import render
from django.views.generic import TemplateView

# Create your views here.


class LoginView(TemplateView):
    template_name = 'login.html'

class RegisterView(TemplateView):
    template_name = 'register.html'

class ProfileView(TemplateView):
    template_name = 'personal_info.html'
    
class Addres_ManagementView(TemplateView):
    template_name = 'address_management.html'
    
class Order_DetailView(TemplateView):
    template_name = 'order_details.html'
    
class Purchase_HistoryView(TemplateView):
    template_name = 'purchase_history.html'
