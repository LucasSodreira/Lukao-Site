from django.shortcuts import redirect 
from django.http import JsonResponse, Http404
from django.views.generic import TemplateView, ListView, DetailView, View
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models
from core.models import Produto, Cor, Endereco, Tag, ProdutoVariacao, Cupom, LogAcao
from checkout.utils import adicionar_ao_carrinho, cotar_frete_melhor_envio, obter_itens_do_carrinho
from decimal import Decimal
from core.models import ProdutoVariacao, ItemCarrinho, Carrinho
from django.views.decorators.http import require_GET
from django.core.exceptions import ValidationError


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
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        produto = self.object
        context['preco_vigente'] = produto.preco_vigente()
        context['desconto'] = produto.calcular_desconto()
        context['media_avaliacoes'] = produto.media_avaliacoes()
        try:
            context['tamanhos_disponiveis'] = produto.get_tamanhos_disponiveis()
        except AttributeError:
            context['tamanhos_disponiveis'] = []
        # Adiciona cores únicas para o template
        cores_unicas = []
        for v in produto.variacoes.all():
            if v.cor not in cores_unicas:
                cores_unicas.append(v.cor)
        context['cores_unicas'] = cores_unicas
        return context

class Product_Listing(ListView):
    model = Produto
    template_name = 'product_listing.html'
    context_object_name = 'produtos'
    paginate_by = 12  # Mostra 12 produtos por página

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        produtos = context['produtos']
        # Adiciona preço vigente e desconto para cada produto
        for produto in produtos:
            produto.preco_vigente_valor = produto.preco_vigente()
            produto.desconto_valor = produto.calcular_desconto()
        queryset = self.get_queryset()
        context['categorias'] = Produto.objects.values_list('categoria__nome', flat=True).distinct()
        context['marcas'] = Produto.objects.values_list('marca__nome', flat=True).distinct()
        context['cores_disponiveis'] = list(Cor.objects.values_list('valor_css', flat=True))
        context['cores'] = context['cores_disponiveis']
        context['tamanhos'] = ProdutoVariacao.objects.values_list('tamanho', flat=True).distinct()
        context['tags'] = Tag.objects.values_list('nome', flat=True).distinct()

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
        q = self.request.GET.get('q', '').strip()
        categoria = self.request.GET.get('categoria')
        tag = self.request.GET.get('tag')
        faixa_preco = self.request.GET.get('faixa_preco')
        preco_min = self.request.GET.get('preco_min')
        preco_max = self.request.GET.get('preco_max')
        tamanhos_raw = self.request.GET.get('tamanhos', '')
        tamanhos = [t for t in set(tamanhos_raw.split(',')) if t.strip()]
        cores_raw = self.request.GET.get('cores', '')
        cores = [c.strip().lower() for c in set(cores_raw.split(',')) if c.strip()]

        if q:
            queryset = queryset.filter(
                models.Q(nome__icontains=q) |
                models.Q(descricao__icontains=q) |
                models.Q(categoria__nome__icontains=q) |
                models.Q(marca__nome__icontains=q) |
                models.Q(tags__nome__icontains=q)
            ).distinct()

        if categoria:
            queryset = queryset.filter(categoria__nome__icontains=categoria)

        if tag:
            queryset = queryset.filter(tags__nome__iexact=tag)

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

        if cores:
            queryset = queryset.filter(variacoes__cor__valor_css__in=cores).distinct()
        if tamanhos:
            queryset = queryset.filter(variacoes__tamanho__in=tamanhos).distinct()

        sort = self.request.GET.get('sort')
        if sort == 'price_asc':
            queryset = queryset.order_by('preco')
        elif sort == 'price_desc':
            queryset = queryset.order_by('-preco')
        elif sort == 'newest':
            queryset = queryset.order_by('-id')  # ou '-data_criacao' se tiver
        else:  # popular ou padrão
            # Corrigido: ordena por id desc (novos primeiro) se não houver campo 'avaliacao'
            queryset = queryset.order_by('-id')

        return queryset

# ==========================
# Views relacionadas ao carrinho
# ==========================

class CartView(TemplateView):
    template_name = 'carrinho.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        itens_carrinho, total = obter_itens_do_carrinho(self.request)
        # Garante que cada item tenha uma chave única para manipulação no template
        if self.request.user.is_authenticated:
            # Para usuários autenticados, use o ID do ItemCarrinho como chave

            carrinho = Carrinho.objects.filter(usuario=self.request.user).first()
            if carrinho:
                itens_db = ItemCarrinho.objects.filter(carrinho=carrinho)
                # Corrigido: usa item.variacao.tamanho e item.variacao.cor.id
                chave_map = {}
                for item in itens_db:
                    tamanho = item.variacao.tamanho if item.variacao else None
                    cor_id = item.variacao.cor.id if item.variacao and item.variacao.cor else None
                    chave_map[(item.produto.id, tamanho, cor_id)] = item.id
                for item in itens_carrinho:
                    variacao = item.get('variacao')
                    tamanho = variacao.tamanho if variacao else None
                    cor_id = variacao.cor.id if variacao and variacao.cor else None
                    item['chave'] = chave_map.get((item['produto'].id, tamanho, cor_id), '')
            else:
                for item in itens_carrinho:
                    item['chave'] = ''
        else:
            # Para sessão, a chave já vem do dict da sessão
            # (mas garantir que sempre exista)
            for item in itens_carrinho:
                if 'chave' not in item:
                    item['chave'] = ''
        # Ajuste: garantir que cada item tenha 'variacao' (objeto ProdutoVariacao)
        for item in itens_carrinho:
            if not item.get('variacao') and 'variacao_id' in item:
                try:
                    item['variacao'] = ProdutoVariacao.objects.get(id=item['variacao_id'])
                except ProdutoVariacao.DoesNotExist:
                    item['variacao'] = None
        # Validação extra: remove itens com quantidade inválida
        itens_carrinho = [item for item in itens_carrinho if item['quantidade'] > 0]
        context['itens_carrinho'] = itens_carrinho
        context['total_carrinho'] = total

        # Lógica do cupom
        cupom_codigo = self.request.session.get('cupom')
        cupom = None
        desconto = 0
        if cupom_codigo:
            try:
                cupom = Cupom.objects.get(codigo__iexact=cupom_codigo)
                if cupom.is_valido(self.request.user):
                    total_com_cupom = cupom.aplicar(total)  # Usando método aplicar do modelo
                    desconto = total - total_com_cupom
                    total = total_com_cupom
                else:
                    self.request.session.pop('cupom', None)
                    cupom = None
            except Cupom.DoesNotExist:
                self.request.session.pop('cupom', None)
                cupom = None
        context['cupom'] = cupom
        context['desconto'] = desconto
        context['total_carrinho_com_cupom'] = total

        if self.request.user.is_authenticated:
            endereco = Endereco.objects.filter(usuario=self.request.user, principal=True).first()
            context['cep_usuario'] = endereco.cep if endereco else getattr(self.request.user, 'cep', None)
        else:
            context['cep_usuario'] = None
        return context

    def post(self, request, *args, **kwargs):
        # Lógica para aplicar cupom via POST
        cupom_codigo = request.POST.get('cupom', '').strip()
        if cupom_codigo:
            try:
                cupom = Cupom.objects.get(codigo__iexact=cupom_codigo)
                if not cupom.is_valido(request.user):
                    raise ValidationError("Cupom inválido ou expirado.")
                request.session['cupom'] = cupom.codigo
                messages.success(request, "Cupom aplicado com sucesso!")
                LogAcao.objects.create(
                    usuario=request.user if request.user.is_authenticated else None,
                    acao="Aplicou cupom",
                    detalhes=f"Cupom: {cupom.codigo}"
                )
            except Cupom.DoesNotExist:
                request.session.pop('cupom', None)
                messages.error(request, "Cupom não encontrado.")
            except ValidationError as e:
                request.session.pop('cupom', None)
                messages.error(request, str(e))
        elif 'remover_cupom' in request.POST:
            request.session.pop('cupom', None)
            messages.success(request, "Cupom removido.")
            LogAcao.objects.create(
                usuario=request.user if request.user.is_authenticated else None,
                acao="Removeu cupom",
                detalhes=""
            )
        return redirect('carrinho')

class ManipularItemCarrinho(View):
    def post(self, request, *args, **kwargs):
        chave = kwargs.get('chave')
        if not chave:
            messages.error(request, "Chave do item não informada.")
            return redirect('carrinho')
        if request.user.is_authenticated:
            # Manipula o ItemCarrinho no banco
            from core.models import ItemCarrinho
            try:
                item = ItemCarrinho.objects.get(id=chave, carrinho__usuario=request.user)
            except ItemCarrinho.DoesNotExist:
                raise Http404("Item não encontrado no carrinho.")
            self.manipular_quantidade_db(item)
            # Remove se quantidade <= 0
            if item.quantidade <= 0:
                item.delete()
            else:
                item.save()
        else:
            # Manipula o carrinho na sessão
            carrinho = request.session.get('carrinho', {})
            if chave not in carrinho:
                raise Http404("Item não encontrado no carrinho.")
            self.manipular_quantidade(carrinho[chave])
            if carrinho[chave]['quantidade'] <= 0:
                del carrinho[chave]
            request.session['carrinho'] = carrinho
            request.session.modified = True
        return redirect('carrinho')

    def manipular_quantidade_db(self, item):
        # Para sobrescrever nas subclasses
        pass

    def manipular_quantidade(self, item):
        # Para sobrescrever nas subclasses
        pass

class AumentarItemView(ManipularItemCarrinho):
    def manipular_quantidade_db(self, item):
        item.quantidade += 1
    def manipular_quantidade(self, item):
        item['quantidade'] += 1

class DiminuirItemView(ManipularItemCarrinho):
    def manipular_quantidade_db(self, item):
        item.quantidade -= 1
    def manipular_quantidade(self, item):
        item['quantidade'] -= 1

class RemoverItemView(ManipularItemCarrinho):
    def manipular_quantidade_db(self, item):
        item.quantidade = 0
    def manipular_quantidade(self, item):
        item['quantidade'] = 0

class AddToCartView(View):
    def post(self, request, *args, **kwargs):
        # Troca: agora espera variacao_id ao invés de size/tamanho
        variacao_id = request.POST.get('variacao_id')
        quantity = request.POST.get('quantity')
        try:
            quantity = int(quantity)
            if quantity < 1:
                raise ValueError
        except (TypeError, ValueError):
            messages.error(request, "Quantidade inválida.")
            return redirect('carrinho')
        try:
            variacao = ProdutoVariacao.objects.get(pk=variacao_id)
        except ProdutoVariacao.DoesNotExist:
            messages.error(request, "Variação do produto não encontrada.")
            return redirect('carrinho')
        produto_id = variacao.produto.id

        # Ajuste: passa variacao_id para a função utilitária
        adicionar_ao_carrinho(request, produto_id, variacao_id=variacao_id, quantidade=quantity)
        LogAcao.objects.create(
            usuario=request.user if request.user.is_authenticated else None,
            acao="Adicionou ao carrinho",
            detalhes=f"Produto: {produto_id}, Variação: {variacao_id}, Quantidade: {quantity}"
        )
        messages.success(request, "Produto adicionado ao carrinho!")
        return redirect('carrinho')

class RemoverItemCarrinho(View):
    def post(self, request, *args, **kwargs):
        chave = kwargs.get('chave')
        if request.user.is_authenticated:
            # Remove pelo banco
            try:
                item = ItemCarrinho.objects.get(id=chave, carrinho__usuario=request.user)
                item.delete()
                response_data = {'success': True, 'message': 'Item removido com sucesso!'}
            except ItemCarrinho.DoesNotExist:
                raise Http404("Item não encontrado no carrinho.")
        else:
            # Remove da sessão
            carrinho = request.session.get('carrinho', {})
            if chave in carrinho:
                del carrinho[chave]
                request.session['carrinho'] = carrinho
                request.session.modified = True
                response_data = {'success': True, 'message': 'Item removido com sucesso!'}
            else:
                raise Http404("Item não encontrado no carrinho.")

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            LogAcao.objects.create(
                usuario=request.user if request.user.is_authenticated else None,
                acao="Removeu item do carrinho (AJAX)",
                detalhes=f"Chave: {chave}"
            )
            return JsonResponse(response_data)
        else:
            LogAcao.objects.create(
                usuario=request.user if request.user.is_authenticated else None,
                acao="Removeu item do carrinho",
                detalhes=f"Chave: {chave}"
            )
            messages.success(request, response_data['message'])
            return redirect('carrinho')

@login_required
def salvar_cep_usuario(request):
    if request.method == 'POST':
        cep = request.POST.get('cep', '').replace('-', '').strip()
        if len(cep) == 8 and cep.isdigit():
            endereco = Endereco.objects.filter(usuario=request.user, principal=True).first()
            if endereco:
                if endereco.cep != cep:
                    endereco.cep = cep
                    endereco.save(update_fields=['cep'])
            else:
                request.user.cep = cep
                request.user.save(update_fields=['cep'])
            return JsonResponse({'sucesso': True, 'cep': cep})
        return JsonResponse({'sucesso': False, 'erro': 'CEP inválido'})
    return JsonResponse({'sucesso': False, 'erro': 'Requisição inválida'})

@require_GET
def calcular_frete(request):
    cep = request.GET.get('cep', '').replace('-', '').strip()
    if len(cep) != 8 or not cep.isdigit():
        return JsonResponse({'sucesso': False, 'erro': 'CEP inválido'})
    try:
        itens_carrinho, subtotal = obter_itens_do_carrinho(request)
        if not itens_carrinho:
            return JsonResponse({'sucesso': False, 'erro': 'Carrinho vazio'})
        from django.conf import settings
        produtos = []
        for item in itens_carrinho:
            produto = item['produto']
            tamanho = item.get('size')
            # Busca a variação correta pelo produto e tamanho
            variacao = ProdutoVariacao.objects.filter(produto=produto, tamanho=tamanho).first()
            peso = float(variacao.peso) if variacao and hasattr(variacao, 'peso') and variacao.peso else float(produto.peso or 1)
            # Se você tiver campos width, height, length na variação, use-os aqui
            width = getattr(variacao, 'width', 15) if variacao else 15
            height = getattr(variacao, 'height', 10) if variacao else 10
            length = getattr(variacao, 'length', 20) if variacao else 20
            produtos.append({
                "weight": peso,
                "width": width,
                "height": height,
                "length": length,
                "insurance_value": float(item['subtotal']),
                "quantity": item['quantidade']
            })
        token = getattr(settings, 'MELHOR_ENVIO_TOKEN', '')
        fretes = cotar_frete_melhor_envio(cep, token, produtos)
        if isinstance(fretes, dict) and 'error' in fretes:
            return JsonResponse({'sucesso': False, 'erro': 'Erro ao consultar frete'})
        if not fretes:
            return JsonResponse({'sucesso': False, 'erro': 'Nenhum frete encontrado'})
        melhor = min(fretes, key=lambda f: float(f.get('price', 9999)))
        return JsonResponse({
            'sucesso': True,
            'valor': float(melhor['price']),
            'descricao': f"{melhor['company']['name']} - {melhor['name']} ({melhor['delivery_time']} dias úteis)"
        })
    except Exception as e:
        return JsonResponse({'sucesso': False, 'erro': 'Erro ao calcular frete'})


