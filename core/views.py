from django.http import HttpResponse
from django.views.generic import TemplateView


class IndexView(TemplateView):
    template_name = 'index.html'
    
class Item_View(TemplateView):
    template_name = 'item_view.html'
    
class Cart(TemplateView):
    template_name = 'carrinho.html'
    
class ReviewCart(TemplateView):
    template_name = 'review_cart.html'

class AddressView(TemplateView):
    template_name = 'address.html'
    
class LoginView(TemplateView):
    template_name = 'login.html'

class RegisterView(TemplateView):
    template_name = 'register.html'
    
class ThanksView(TemplateView):
    template_name = 'thanks.html'