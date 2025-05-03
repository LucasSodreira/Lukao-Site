from django.shortcuts import redirect, get_object_or_404
from django.http import JsonResponse, Http404
from django.views.generic import TemplateView, ListView, DetailView, View
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from core.models import Produto, Cor
from checkout.utils import adicionar_ao_carrinho, remover_do_carrinho, migrar_carrinho_antigo
from decimal import Decimal
from django.shortcuts import redirect, get_object_or_404
from user.models import Notificacao

# ==========================
# Views relacionadas aos produtos
# ==========================

class IndexView(ListView):
    model = Produto
    template_name = 'index.html'
    context_object_name = 'produtos'
    

class ItemView(DetailView):
    model = Produto
    template_name = 'item_view.html'
    context_object_name = 'produto'

class Product_Listing(ListView):
    model = Produto
    template_name = 'product_listing.html'
    context_object_name = 'produtos'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()
        context['categorias'] = Produto.objects.values_list('categoria__nome', flat=True).distinct()
        # Busca todas as cores cadastradas (model Cor)
        context['cores_disponiveis'] = list(Cor.objects.values_list('valor_css', flat=True))
        context['cores'] = context['cores_disponiveis']
        context['tamanhos'] = Produto.objects.values_list('tamanho', flat=True).distinct()

        if queryset.exists():
            preco_min = queryset.order_by('preco').first().preco
            preco_max = queryset.order_by('-preco').first().preco
            context['preco_minimo'] = preco_min
            context['preco_maximo'] = preco_max

            faixa1 = preco_min + (preco_max - preco_min) * Decimal('0.33')
            faixa2 = preco_min + (preco_max - preco_min) * Decimal('0.66')
            context['faixa_preco_1'] = int(faixa1)
            context['faixa_preco_2'] = int(faixa2)
        else:
            context['preco_minimo'] = 0
            context['preco_maximo'] = 0
            context['faixa_preco_1'] = 0
            context['faixa_preco_2'] = 0

        return context

    def get_queryset(self):
        queryset = super().get_queryset()
        categoria = self.request.GET.get('categoria')
        faixa_preco = self.request.GET.get('faixa_preco')
        preco_min = self.request.GET.get('preco_min')
        preco_max = self.request.GET.get('preco_max')
        tamanhos_raw = self.request.GET.get('tamanhos', '')
        tamanhos = [t for t in set(tamanhos_raw.split(',')) if t.strip()]
        cores_raw = self.request.GET.get('cores', '')
        cores = [c.strip().lower() for c in set(cores_raw.split(',')) if c.strip()]

        if categoria:
            queryset = queryset.filter(categoria__nome__icontains=categoria)

        if queryset.exists():
            preco_min_qs = queryset.order_by('preco').first().preco
            preco_max_qs = queryset.order_by('-preco').first().preco
            faixa1 = preco_min_qs + (preco_max_qs - preco_min_qs) * Decimal('0.33')
            faixa2 = preco_min_qs + (preco_max_qs - preco_min_qs) * Decimal('0.66')
            faixa1 = int(faixa1)
            faixa2 = int(faixa2)
        else:
            faixa1 = faixa2 = 0

        if faixa_preco:
            if faixa_preco == "faixa1":
                queryset = queryset.filter(preco__lte=faixa1)
            elif faixa_preco == "faixa2":
                queryset = queryset.filter(preco__gt=faixa1, preco__lte=faixa2)
            elif faixa_preco == "faixa3":
                queryset = queryset.filter(preco__gt=faixa2)
        else:
            if preco_min:
                queryset = queryset.filter(preco__gte=preco_min)
            if preco_max:
                queryset = queryset.filter(preco__lte=preco_max)
        # Filtro de cor: retorna produtos que tenham pelo menos uma cor associada com valor_css igual ao filtro
        if cores:
            queryset = queryset.filter(cores__cor__valor_css__in=cores).distinct()
        if tamanhos:
            queryset = queryset.filter(tamanho__in=tamanhos)

        return queryset



# ==========================
# Views relacionadas ao carrinho
# ==========================

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
        
        if chave not in carrinho:
            raise Http404("Item não encontrado no carrinho.")
        
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
        quantity = int(request.POST.get('quantity'))  # Pega a quantidade selecionada
        
        # Valida se o produto existe
        try:
            produto = Produto.objects.get(pk=produto_id)
        except ObjectDoesNotExist:
            raise Http404("Produto não encontrado.")
        
        # Adicione a lógica para armazenar o tamanho e a quantidade junto com o produto
        adicionar_ao_carrinho(request, produto_id, size=size, quantidade=quantity)
        
        return redirect('carrinho')


class RemoverItemCarrinho(View):
    def post(self, request, *args, **kwargs):
        produto_id = request.POST.get('produto_id')
        
        # Valida se o produto existe
        try:
            Produto.objects.get(pk=produto_id)
        except ObjectDoesNotExist:
            raise Http404("Produto não encontrado.")
        
        remover_do_carrinho(request, produto_id)

        response_data = {'success': True, 'message': 'Item removido com sucesso!'}

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse(response_data)
        else:
            messages.success(request, response_data['message'])
            return redirect('carrinho')

