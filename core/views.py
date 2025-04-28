from django.shortcuts import redirect, get_object_or_404
from django.views.generic import TemplateView
from django.views.generic import ListView, DetailView, View
from .models import Produto
from django.contrib import messages

class IndexView(ListView):
    model = Produto
    template_name = 'index.html'
    context_object_name = 'produtos'
    paginate_by = 6 # Número de produtos por página
    
class ItemView(DetailView):
    model = Produto
    template_name = 'item_view.html'
    context_object_name = 'produto'

    
class CartView(TemplateView):
    template_name = 'carrinho.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        carrinho = self.request.session.get('carrinho', {})
        produtos = Produto.objects.filter(id__in=carrinho.keys())

        lista_produtos = []
        total = 0

        for produto in produtos:
            quantidade = carrinho[str(produto.id)]
            subtotal = produto.preco * quantidade
            total += subtotal

            lista_produtos.append({
                'produto': produto,
                'quantidade': quantidade,
                'subtotal': subtotal,
            })

        context['produtos_carrinho'] = lista_produtos
        context['total_carrinho'] = total
        return context



class AddToCartView(TemplateView):
    def post(self, request, *args, **kwargs):
        produto_id = self.kwargs.get('pk')
        produto = get_object_or_404(Produto, id=produto_id)

        carrinho = request.session.get('carrinho', {})

        if str(produto.id) in carrinho:
            carrinho[str(produto.id)] += 1
        else:
            carrinho[str(produto.id)] = 1

        request.session['carrinho'] = carrinho
        request.session.modified = True

        return redirect('carrinho')  # Depois de adicionar, manda para a página do carrinho
    
class RemoverItemCarrinho(View):
    def post(self, request, *args, **kwargs):
        produto_id = request.POST.get('produto_id')

        if 'carrinho' in request.session:
            carrinho = request.session['carrinho']
            if produto_id in carrinho:
                del carrinho[produto_id]
                request.session['carrinho'] = carrinho
                messages.success(request, "Item removido com sucesso!")

        return redirect('carrinho')
    
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