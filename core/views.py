from django.shortcuts import redirect, get_object_or_404, render
from django.views.generic import TemplateView
from django.views.generic import ListView, DetailView, View, CreateView
from django.urls import reverse_lazy
from .models import Produto, Endereco, Pedido, ItemPedido
from django.contrib import messages
from django.http import JsonResponse
from .forms import EnderecoForm
from django.db import transaction

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
        response_data = {'success': False, 'message': 'Item não encontrado'}

        if 'carrinho' in request.session and produto_id in request.session['carrinho']:
            carrinho = request.session['carrinho']
            del carrinho[produto_id]
            request.session['carrinho'] = carrinho
            request.session.modified = True
            
            response_data = {
                'success': True,
                'message': 'Item removido com sucesso!',
                'itens_count': sum(carrinho.values())
            }

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse(response_data)
        else:
            if response_data['success']:
                messages.success(request, response_data['message'])
            else:
                messages.error(request, response_data['message'])
            return redirect('carrinho')
      
class ReviewCart(View):
    def get(self, request, *args, **kwargs):
        carrinho = request.session.get('carrinho', {})
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

        # Obter o endereço do usuário ou None se não existir
        endereco = Endereco.objects.filter(usuario=request.user).last()

        context = {
            'produtos_carrinho': lista_produtos,
            'total_carrinho': total,
            'endereco': endereco,
            'tem_endereco': endereco is not None  # Adiciona flag para verificar se tem endereço
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
                # Cria o pedido sem ID específico
                pedido = Pedido(
                    usuario=request.user,
                    endereco_entrega=endereco,
                    total=0
                )
                pedido.save()  # Isso vai gerar um novo ID

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

                request.session['carrinho'] = {}
                request.session.modified = True

                messages.success(request, "Pedido finalizado com sucesso!")
                return redirect('thanks')

        except Exception as e:
            messages.error(request, f"Erro ao finalizar o pedido: {str(e)}")
            return redirect('review-cart')
    
class AddressView(CreateView):
    model = Endereco
    form_class = EnderecoForm
    template_name = 'address.html'
    success_url = reverse_lazy('review-cart')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Verifica se já existe um endereço para edição
        endereco_existente = Endereco.objects.filter(usuario=self.request.user).first()
        if endereco_existente:
            kwargs['instance'] = endereco_existente
        return kwargs

    def form_valid(self, form):
        endereco = form.save(commit=False)
        endereco.usuario = self.request.user
        endereco.save()
        self.request.session.modified = True  # Garantir atualização do session
        return super().form_valid(form)
    
class LoginView(TemplateView):
    template_name = 'login.html'

class RegisterView(TemplateView):
    template_name = 'register.html'
    
class ThanksView(TemplateView):
    template_name = 'thanks.html'