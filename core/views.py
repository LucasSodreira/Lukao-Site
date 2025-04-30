# Imports padrão Python
from django.shortcuts import redirect, get_object_or_404, render
from django.urls import reverse_lazy
from django.http import JsonResponse

# Imports Django (Views, Forms, Models, Messages, Transactions)
from django.views.generic import TemplateView, ListView, DetailView, View, CreateView, UpdateView
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.db import transaction
from django.views.generic.edit import FormView

# Imports do seu app
from django import forms
from .models import Produto, Endereco, Pedido, ItemPedido, Categoria
from .forms import EnderecoForm
from django.conf import settings
from core.utils import limpar_carrinho, adicionar_ao_carrinho, remover_do_carrinho, migrar_carrinho_antigo, cotar_frete_melhor_envio

# ============================

class IndexView(ListView):
     model = Produto
     template_name = 'index.html'
     context_object_name = 'produtos'


class ItemView(DetailView):
    model = Produto
    template_name = 'item_view.html'
    context_object_name = 'produto'


class CartView(TemplateView):
    template_name = 'carrinho.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        carrinho = self.request.session.get('carrinho', {})
        itens_carrinho = []
        
        # Migra carrinho antigo para novo formato se necessário
        if any(isinstance(v, int) for v in carrinho.values()):
            carrinho = migrar_carrinho_antigo(carrinho)
            self.request.session['carrinho'] = carrinho
            self.request.session.modified = True
        
        # Obtém todos os IDs de produtos únicos
        produto_ids = []
        for item in carrinho.values():
            if isinstance(item, dict) and 'produto_id' in item:
                produto_ids.append(item['produto_id'])
        
        produtos = Produto.objects.filter(id__in=produto_ids)
        produto_dict = {p.id: p for p in produtos}
        
        for chave, item in carrinho.items():
            if isinstance(item, dict) and 'produto_id' in item:
                produto = produto_dict.get(item['produto_id'])
                if produto:
                    itens_carrinho.append({
                        'chave': chave,
                        'produto': produto,
                        'quantidade': item['quantidade'],
                        'size': item.get('size'),
                        'subtotal': produto.preco * item['quantidade']
                    })
        
        total = sum(item['subtotal'] for item in itens_carrinho)
        
        context['itens_carrinho'] = itens_carrinho
        context['total_carrinho'] = total
        return context


class ManipularItemCarrinho(View):
    def post(self, request, *args, **kwargs):
        chave = kwargs.get('chave')
        carrinho = request.session.get('carrinho', {})
        
        if chave in carrinho:
            self.manipular_quantidade(carrinho[chave])
            
            if carrinho[chave]['quantidade'] <= 0:
                del carrinho[chave]
            
            request.session['carrinho'] = carrinho
            request.session.modified = True
        
        return redirect('carrinho')

class AumentarItemView(ManipularItemCarrinho):
    def manipular_quantidade(self, item):
        item['quantidade'] += 1

class DiminuirItemView(ManipularItemCarrinho):
    def manipular_quantidade(self, item):
        item['quantidade'] -= 1

class RemoverItemView(ManipularItemCarrinho):
    def manipular_quantidade(self, item):
        item['quantidade'] = 0  # Será removido na verificação

class AddToCartView(View):
    def post(self, request, *args, **kwargs):
        produto_id = self.kwargs.get('pk')
        size = request.POST.get('size', 'medium')  # Pega o tamanho selecionado
        
        # Adicione a lógica para armazenar o tamanho junto com o produto
        adicionar_ao_carrinho(request, produto_id, size=size)
        
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
    template_name = 'review_cart.html'
    
    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        endereco = Endereco.objects.filter(usuario=request.user).last()
        context['endereco'] = endereco
        context['tem_endereco'] = endereco is not None
        return render(request, self.template_name, context)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        carrinho = self.request.session.get('carrinho', {})
        itens_carrinho = []
        
        # Migra carrinho antigo para novo formato se necessário
        if any(isinstance(v, int) for v in carrinho.values()):
            carrinho = migrar_carrinho_antigo(carrinho)
            self.request.session['carrinho'] = carrinho
            self.request.session.modified = True
        
        # Obtém todos os IDs de produtos únicos
        produto_ids = []
        for item in carrinho.values():
            if isinstance(item, dict) and 'produto_id' in item:
                produto_ids.append(item['produto_id'])
        
        produtos = Produto.objects.filter(id__in=produto_ids)
        produto_dict = {p.id: p for p in produtos}
        
        for chave, item in carrinho.items():
            if isinstance(item, dict) and 'produto_id' in item:
                produto = produto_dict.get(item['produto_id'])
                if produto:
                    itens_carrinho.append({
                        'chave': chave,
                        'produto': produto,
                        'quantidade': item['quantidade'],
                        'size': item.get('size'),
                        'subtotal': produto.preco * item['quantidade']
                    })
        
        total = sum(item['subtotal'] for item in itens_carrinho)
        
        context['itens_carrinho'] = itens_carrinho
        context['total_carrinho'] = total
        return context

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
                
                # Obtém todos os IDs de produtos únicos
                produto_ids = []
                for item in carrinho.values():
                    if isinstance(item, dict) and 'produto_id' in item:
                        produto_ids.append(item['produto_id'])
                
                produtos = Produto.objects.filter(id__in=produto_ids)
                produto_dict = {p.id: p for p in produtos}
                
                for item in carrinho.values():
                    if isinstance(item, dict) and 'produto_id' in item:
                        produto = produto_dict.get(item['produto_id'])
                        if produto:
                            quantidade = item['quantidade']
                            subtotal = produto.preco * quantidade
                            total += subtotal

                            ItemPedido.objects.create(
                                pedido=pedido,
                                produto=produto,
                                quantidade=quantidade,
                                preco_unitario=produto.preco,
                                tamanho=item.get('size')
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


class EnderecoEditView(UpdateView):
    model = Endereco
    form_class = EnderecoForm
    template_name = 'address.html'
    success_url = reverse_lazy('endereco-view')

    def get_queryset(self):
        return Endereco.objects.filter(usuario=self.request.user)
class EnderecoCreateView(CreateView):
    model = Endereco
    form_class = EnderecoForm
    template_name = 'address.html'
    success_url = reverse_lazy('endereco-view')

    def form_valid(self, form):
        form.instance.usuario = self.request.user
        return super().form_valid(form)

@method_decorator(login_required, name='dispatch')
class DefinirEnderecoPrincipal(View):
    def post(self, request, pk):
        endereco = get_object_or_404(Endereco, pk=pk, usuario=request.user)

        # Desativa os outros como principal
        Endereco.objects.filter(usuario=request.user, principal=True).update(principal=False)

        # Ativa este como principal
        endereco.principal = True
        endereco.save()

        return redirect('endereco-view')

@method_decorator(login_required, name='dispatch')
class ExcluirEnderecoView(View):
    def post(self, request, pk):
        endereco = get_object_or_404(Endereco, pk=pk, usuario=request.user)
        endereco.delete()
        return redirect('endereco-view')

class LoginView(TemplateView):
    template_name = 'login.html'


class RegisterView(TemplateView):
    template_name = 'register.html'


class ThanksView(TemplateView):
    template_name = 'thanks.html'
    
class AddressSelection(TemplateView):
    template_name = 'address_selection.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.request.user.is_authenticated:
            enderecos = Endereco.objects.filter(usuario=self.request.user)
            context['enderecos'] = enderecos
        else:
            context['enderecos'] = []

        return context
    
token = settings.MELHOR_ENVIO_TOKEN

class FreteForm(forms.Form):
    frete_escolhido = forms.ChoiceField(widget=forms.RadioSelect)

    def __init__(self, *args, **kwargs):
        fretes = kwargs.pop('fretes', [])
        super().__init__(*args, **kwargs)
        choices = []

        for frete in fretes:
            try:
                nome = frete['company']['name']
                servico = frete['name']
                preco = frete['price']
                dias = frete['delivery_time']['days']
                choices.append((frete['id'], f"{nome} - {servico} - R$ {preco} - {dias} dias úteis"))
            except (KeyError, TypeError):
                continue  # Ignora entradas inválidas
            
        self.fields['frete_escolhido'].choices = choices

class ShipmentMethodView(LoginRequiredMixin, FormView):
    template_name = 'shipping_method.html'
    form_class = FreteForm
    success_url = reverse_lazy('review-cart')

    def get_fretes(self):
        endereco = Endereco.objects.filter(usuario=self.request.user, principal=True).first()
        if endereco:
            return cotar_frete_melhor_envio(endereco.cep, token)
        return []

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['fretes'] = self.get_fretes()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['fretes'] = self.get_fretes()
        return context

    def form_valid(self, form):
        frete_escolhido = form.cleaned_data['frete_escolhido']
        self.request.session['frete_escolhido'] = frete_escolhido
        self.request.session.modified = True
        return super().form_valid(form)
    
