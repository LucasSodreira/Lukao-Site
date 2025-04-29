# Imports padrão Python
from django.shortcuts import redirect, get_object_or_404, render
from django.urls import reverse_lazy
from django.http import JsonResponse

# Imports Django (Views, Forms, Models, Messages, Transactions)
from django.views.generic import TemplateView, ListView, DetailView, View, CreateView, UpdateView
from django.contrib import messages
from django.db import transaction

# Imports do seu app
from .models import Produto, Endereco, Pedido, ItemPedido
from .forms import EnderecoForm
from core.utils import limpar_carrinho, adicionar_ao_carrinho, remover_do_carrinho, calcular_total_carrinho

# ============================

class IndexView(ListView):
    model = Produto
    template_name = 'index.html'
    context_object_name = 'produtos'
    paginate_by = 6  # Número de produtos por página


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

        for produto in produtos:
            quantidade = carrinho[str(produto.id)]
            subtotal = produto.preco * quantidade

            lista_produtos.append({
                'produto': produto,
                'quantidade': quantidade,
                'subtotal': subtotal,
            })

        total = calcular_total_carrinho(self.request)

        context['produtos_carrinho'] = lista_produtos
        context['total_carrinho'] = total
        return context


class AddToCartView(TemplateView):
    def post(self, request, *args, **kwargs):
        produto_id = self.kwargs.get('pk')
        adicionar_ao_carrinho(request, produto_id)
        return redirect('carrinho')


class RemoverItemCarrinho(View):
    def post(self, request, *args, **kwargs):
        produto_id = request.POST.get('produto_id')

        remover_do_carrinho(request, produto_id)

        response_data = {'success': True, 'message': 'Item removido com sucesso!'}

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse(response_data)
        else:
            messages.success(request, response_data['message'])
            return redirect('carrinho')


class ReviewCart(View):
    def get(self, request, *args, **kwargs):
        carrinho = request.session.get('carrinho', {})
        produtos = Produto.objects.filter(id__in=carrinho.keys())

        lista_produtos = []
        total = calcular_total_carrinho(self.request)

        for produto in produtos:
            quantidade = carrinho[str(produto.id)]
            subtotal = produto.preco * quantidade

            lista_produtos.append({
                'produto': produto,
                'quantidade': quantidade,
                'subtotal': subtotal,
            })

        endereco = Endereco.objects.filter(usuario=request.user).last()

        context = {
            'produtos_carrinho': lista_produtos,
            'total_carrinho': total,
            'endereco': endereco,
            'tem_endereco': endereco is not None
        }
        return render(request, 'review_cart.html', context)

    def post(self, request, *args, **kwargs):
        endereco = Endereco.objects.filter(usuario=request.user).last()
        carrinho = request.session.get('carrinho', {})

        if not endereco:
            messages.error(request, "Você precisa cadastrar um endereço antes de finalizar o pedido.")
            return redirect('review-cart')
            
        if not carrinho:
            messages.error(request, "Seu carrinho está vazio.")
            return redirect('review-cart')

        try:
            with transaction.atomic():
                pedido = Pedido(
                    usuario=request.user,
                    endereco_entrega=endereco,
                    total=0
                )
                pedido.save()

                total = 0
                produtos = Produto.objects.filter(id__in=carrinho.keys())
                
                for produto in produtos:
                    quantidade = carrinho[str(produto.id)]
                    subtotal = produto.preco * quantidade
                    total += subtotal

                    ItemPedido.objects.create(
                        pedido=pedido,
                        produto=produto,
                        quantidade=quantidade,
                        preco_unitario=produto.preco
                    )

                    produto.estoque -= quantidade
                    produto.save()

                pedido.total = total
                pedido.save()

                limpar_carrinho(request)

                messages.success(request, "Pedido finalizado com sucesso!")
                return redirect('thanks')

        except Exception as e:
            messages.error(request, f"Erro ao finalizar o pedido: {str(e)}")
            return redirect('review-cart')


class AddressView(UpdateView):
    model = Endereco
    form_class = EnderecoForm
    template_name = 'address.html'
    success_url = reverse_lazy('review-cart')

    def get_object(self, queryset=None):
        # Garante que sempre retorne um endereço vinculado ao usuário
        obj, created = Endereco.objects.get_or_create(usuario=self.request.user)
        print(obj)
        return obj

    def form_valid(self, form):
        # Garante o vínculo com o usuário antes de salvar
        form.instance.usuario = self.request.user
        print(form.instance.usuario)
        return super().form_valid(form)

class LoginView(TemplateView):
    template_name = 'login.html'


class RegisterView(TemplateView):
    template_name = 'register.html'


class ThanksView(TemplateView):
    template_name = 'thanks.html'
