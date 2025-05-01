# Imports padrão Python
from django.shortcuts import redirect, get_object_or_404, render
from django.urls import reverse_lazy
from django.http import JsonResponse
from decimal import Decimal

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
from core.utils import limpar_carrinho, adicionar_ao_carrinho, remover_do_carrinho, migrar_carrinho_antigo, obter_itens_do_carrinho, cotar_frete_melhor_envio

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
                dias = frete['delivery_time']
                choices.append((frete['id'], f"{nome} - {servico} - R$ {preco} - {dias} dias úteis"))
            except (KeyError, TypeError):
                continue  # Ignora entradas inválidas
            
        self.fields['frete_escolhido'].choices = choices



class ShipmentMethodView(LoginRequiredMixin, FormView):
    template_name = 'shipping_method.html'
    form_class = FreteForm
    success_url = reverse_lazy('order-summary')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['fretes'] = self.get_fretes()
        return kwargs

    def get_fretes(self):
        endereco = Endereco.objects.filter(usuario=self.request.user, principal=True).first()
        if endereco:
            return cotar_frete_melhor_envio(endereco.cep, settings.MELHOR_ENVIO_TOKEN)
        return []

    def form_valid(self, form):
        frete_id = form.cleaned_data['frete_escolhido']
        frete_escolhido = next(
            (f for f in self.get_fretes() if str(f['id']) == frete_id),
            None
        )

        if frete_escolhido:
            self.request.session['frete_escolhido'] = {
                'id': frete_escolhido['id'],
                'name': frete_escolhido['name'],
                'price': float(frete_escolhido['price']),
                'company': frete_escolhido['company'],
                'delivery_time': frete_escolhido['delivery_time'],
            }
            self.request.session.modified = True
            return super().form_valid(form)

        messages.error(self.request, "Método de envio inválido")
        return self.form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['fretes'] = self.get_fretes()
        return context


    
token = settings.MELHOR_ENVIO_TOKEN



class OrderSummaryView(LoginRequiredMixin, TemplateView):
    template_name = 'order_summary.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        validation_errors = self.validate_order()
        if validation_errors:
            messages.error(self.request, validation_errors)
            return redirect('review-cart')

        itens_carrinho, subtotal = obter_itens_do_carrinho(self.request)

        frete_info = self.request.session.get('frete_escolhido')
        frete_valor = Decimal(str(frete_info.get('price'))) if frete_info else Decimal('0.00')
        total = subtotal + frete_valor

        endereco = Endereco.objects.filter(usuario=self.request.user, principal=True).first()

        context.update({
            'itens_carrinho': itens_carrinho,
            'subtotal': subtotal,
            'frete': frete_valor,
            'total': total,
            'frete_escolhido': frete_info,
            'endereco': endereco,
        })

        return context


    def validate_order(self):
        errors = []
        carrinho = self.request.session.get('carrinho', {})
        if not carrinho:
            return "Seu carrinho está vazio."

        for item_id, item in carrinho.items():
            try:
                produto = Produto.objects.get(id=item['produto_id'])
                if produto.estoque < item['quantidade']:
                    errors.append(f"{produto.nome}: estoque insuficiente")
            except Produto.DoesNotExist:
                errors.append(f"Produto {item_id} não encontrado")

        endereco = Endereco.objects.filter(usuario=self.request.user, principal=True).first()
        if not endereco:
            errors.append("Endereço principal não encontrado")
        else:
            errors.extend(self.validate_address(endereco))

        if not self.request.session.get('frete_escolhido'):
            errors.append("Método de envio não selecionado")

        return "\n".join(errors) if errors else None

    def validate_address(self, endereco):
        errors = []
        campos_obrigatorios = [
            'nome_completo', 'rua', 'numero', 'bairro',
            'cidade', 'estado', 'cep', 'telefone'
        ]
        for campo in campos_obrigatorios:
            if not getattr(endereco, campo, None):
                errors.append(f"Campo obrigatório: {campo}")
        return errors
   
   
class ProcessarPagamentoView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            # Validação final antes do pagamento
            validation_error = self.validate_order(request)
            if validation_error:
                messages.error(request, validation_error)
                return redirect('order-summary')

            # Restante da lógica de processamento...
            
        except Exception as e:
            messages.error(request, f"Erro ao processar pagamento: {str(e)}")
            return redirect('order-summary')

    def validate_order(self, request):
        """Validação final antes de processar o pagamento"""
        errors = []
        
        # 1. Verifica se o carrinho ainda existe
        carrinho = request.session.get('carrinho', {})
        if not carrinho:
            return "Seu carrinho está vazio."
        
        # 2. Verifica estoque novamente (para evitar race condition)
        for item_id, item in carrinho.items():
            if isinstance(item, dict):
                try:
                    produto = Produto.objects.select_for_update().get(id=item['produto_id'])
                    if produto.estoque < item['quantidade']:
                        errors.append(
                            f"{produto.nome} não tem estoque suficiente. " 
                            f"Disponível: {produto.estoque}, solicitado: {item['quantidade']}"
                        )
                except Produto.DoesNotExist:
                    errors.append(f"Produto ID {item_id} não está mais disponível")
        
        # 3. Verifica endereço
        endereco = Endereco.objects.filter(usuario=request.user, principal=True).first()
        if not endereco:
            errors.append("Endereço de entrega não encontrado.")
        
        # 4. Verifica frete
        if not request.session.get('frete_escolhido'):
            errors.append("Método de envio não selecionado.")
        
        return "\n".join(errors) if errors else None