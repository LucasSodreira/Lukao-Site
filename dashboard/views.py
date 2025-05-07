from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from datetime import timedelta
from core.models import Pedido, Produto, ItemPedido, Categoria, ProdutoVariacao, Cor, Marca, ImagemProduto, Cupom, Reembolso, HistoricoPedido, Endereco
import pandas as pd
from django.db.models import Sum, Count, Avg
from django.conf import settings
from django.contrib.auth import get_user_model
from .forms import ProdutoForm, ProdutoVariacaoFormSet, PedidoUpdateForm, ReembolsoProcessForm, ClienteUpdateForm, CupomForm
from .filters import EstoqueFilter
from .filters import ProdutoFilter, PedidoFilter, ReembolsoFilter, RelatorioReembolsoFilter, ClienteFilter, CupomFilter
from django.contrib import messages
from django.http import HttpResponse
from django.core.mail import send_mail
from django.template.loader import render_to_string
import stripe
from checkout.utils import criar_envio_melhor_envio
from core.models import Notification
import requests
from django.forms import inlineformset_factory

User = get_user_model()

# Configurar Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

# --- Página Inicial ---
@staff_member_required
def dashboard_overview(request):
    end_date = timezone.now()
    start_date = end_date - timedelta(days=30)
    total_vendas = Pedido.objects.filter(data_criacao__gte=start_date).aggregate(total=Sum('total'))['total'] or 0
    pedidos_pendentes = Pedido.objects.filter(status='P').count()
    produtos_estoque_baixo = Produto.objects.filter(estoque__lt=5, estoque__gt=0).count()
    total_clientes = User.objects.filter(pedidos__isnull=False).distinct().count()

    vendas_data = Pedido.objects.filter(data_criacao__gte=start_date).values('data_criacao__date').annotate(total=Sum('total')).order_by('data_criacao__date')
    vendas_df = pd.DataFrame(list(vendas_data))
    if not vendas_df.empty:
        vendas_df['data_criacao__date'] = pd.to_datetime(vendas_df['data_criacao__date'])
        vendas_df = vendas_df.set_index('data_criacao__date').resample('D').sum().fillna(0).reset_index()
        vendas_labels = vendas_df['data_criacao__date'].dt.strftime('%Y-%m-%d').tolist()
        vendas_values = vendas_df['total'].tolist()
    else:
        vendas_labels = []
        vendas_values = []

    produtos_vendidos = ItemPedido.objects.values('produto__nome').annotate(total=Sum('quantidade')).order_by('-total')[:5]
    produtos_df = pd.DataFrame(list(produtos_vendidos))
    produtos_labels = produtos_df['produto__nome'].tolist() if not produtos_df.empty else []
    produtos_values = produtos_df['total'].tolist() if not produtos_df.empty else []

    estoque_categoria = Produto.objects.values('categoria__nome').annotate(total=Sum('estoque')).order_by('-total')
    estoque_df = pd.DataFrame(list(estoque_categoria))
    estoque_labels = estoque_df['categoria__nome'].tolist() if not estoque_df.empty else []
    estoque_values = estoque_df['total'].tolist() if not estoque_df.empty else []

    produtos_estoque_zerado = Produto.objects.filter(estoque=0, ativo=True)
    promocoes_fim = Produto.objects.filter(
        promocao_fim__isnull=False,
        promocao_fim__gte=timezone.now(),
        promocao_fim__lte=timezone.now() + timedelta(days=3),
        ativo=True
    )

    context = {
        'total_vendas': total_vendas,
        'pedidos_pendentes': pedidos_pendentes,
        'produtos_estoque_baixo': produtos_estoque_baixo,
        'total_clientes': total_clientes,
        'vendas_labels': vendas_labels,
        'vendas_values': vendas_values,
        'produtos_labels': produtos_labels,
        'produtos_values': produtos_values,
        'estoque_labels': estoque_labels,
        'estoque_values': estoque_values,
        'produtos_estoque_zerado': produtos_estoque_zerado,
        'promocoes_fim': promocoes_fim,
    }
    return render(request, 'dashboard/overview.html', context)

# --- Gestão de Produtos ---
@staff_member_required
def produto_list(request):
    filterset = ProdutoFilter(request.GET, queryset=Produto.objects.all())
    produtos = filterset.qs

    estoque_categoria = Produto.objects.values('categoria__nome').annotate(total=Sum('estoque')).order_by('-total')
    estoque_df = pd.DataFrame(list(estoque_categoria))
    estoque_labels = estoque_df['categoria__nome'].tolist() if not estoque_df.empty else []
    estoque_values = estoque_df['total'].tolist() if not estoque_df.empty else []

    avaliacoes = Produto.objects.annotate(media=Avg('avaliacoes__nota')).filter(avaliacoes__isnull=False).order_by('-media')[:5]
    avaliacoes_df = pd.DataFrame(list(avaliacoes.values('nome', 'media')))
    avaliacoes_labels = avaliacoes_df['nome'].tolist() if not avaliacoes_df.empty else []
    avaliacoes_values = avaliacoes_df['media'].tolist() if not avaliacoes_df.empty else []

    context = {
        'filter': filterset,
        'produtos': produtos,
        'estoque_labels': estoque_labels,
        'estoque_values': estoque_values,
        'avaliacoes_labels': avaliacoes_labels,
        'avaliacoes_values': avaliacoes_values,
    }
    return render(request, 'dashboard/produtos/list.html', context)

@staff_member_required
def produto_create(request):
    if request.method == 'POST':
        form = ProdutoForm(request.POST, request.FILES)
        variacao_formset = ProdutoVariacaoFormSet(request.POST, instance=None, prefix='variacoes')
        if form.is_valid() and variacao_formset.is_valid():
            produto = form.save()
            variacao_formset.instance = produto
            variacao_formset.save()
            messages.success(request, 'Produto criado com sucesso!')
            return redirect('dashboard:produto_list')
    else:
        form = ProdutoForm()
        variacao_formset = ProdutoVariacaoFormSet(instance=None, prefix='variacoes')
    return render(request, 'dashboard/produtos/form.html', {
        'form': form,
        'variacao_formset': variacao_formset,
        'title': 'Criar Produto'
    })

@staff_member_required
def produto_update(request, pk):
    produto = get_object_or_404(Produto, pk=pk)
    if request.method == 'POST':
        form = ProdutoForm(request.POST, request.FILES, instance=produto)
        variacao_formset = ProdutoVariacaoFormSet(request.POST, instance=produto, prefix='variacoes')
        if form.is_valid() and variacao_formset.is_valid():
            form.save()
            variacao_formset.save()
            messages.success(request, 'Produto atualizado com sucesso!')
            return redirect('dashboard:produto_list')
    else:
        form = ProdutoForm(instance=produto)
        variacao_formset = ProdutoVariacaoFormSet(instance=produto, prefix='variacoes')
    return render(request, 'dashboard/produtos/form.html', {
        'form': form,
        'variacao_formset': variacao_formset,
        'title': 'Editar Produto'
    })

@staff_member_required
def produto_delete(request, pk):
    produto = get_object_or_404(Produto, pk=pk)
    if request.method == 'POST':
        produto.delete()
        messages.success(request, 'Produto excluído com sucesso!')
        return redirect('dashboard:produto_list')
    return render(request, 'dashboard/produtos/confirm_delete.html', {'produto': produto})

# --- Gestão de Pedidos ---
@staff_member_required
def pedido_list(request):
    filterset = PedidoFilter(request.GET, queryset=Pedido.objects.all())
    pedidos = filterset.qs

    pedidos_status = Pedido.objects.values('status').annotate(total=Count('id')).order_by('status')
    status_df = pd.DataFrame(list(pedidos_status))
    status_labels = [dict(Pedido.STATUS_CHOICES).get(row['status'], row['status']) for row in pedidos_status]
    status_values = status_df['total'].tolist() if not status_df.empty else []

    pedidos_data = Pedido.objects.filter(
        data_criacao__gte=timezone.now() - timedelta(days=30)
    ).values('data_criacao__date').annotate(total=Count('id')).order_by('data_criacao__date')
    pedidos_df = pd.DataFrame(list(pedidos_data))
    if not pedidos_df.empty:
        pedidos_df['data_criacao__date'] = pd.to_datetime(pedidos_df['data_criacao__date'])
        pedidos_df = pedidos_df.set_index('data_criacao__date').resample('D').sum().fillna(0).reset_index()
        pedidos_labels = pedidos_df['data_criacao__date'].dt.strftime('%Y-%m-%d').tolist()
        pedidos_values = pedidos_df['total'].tolist()
    else:
        pedidos_labels = []
        pedidos_values = []

    context = {
        'filter': filterset,
        'pedidos': pedidos,
        'status_labels': status_labels,
        'status_values': status_values,
        'pedidos_labels': pedidos_labels,
        'pedidos_values': pedidos_values,
    }
    return render(request, 'dashboard/pedidos/list.html', context)

@staff_member_required
def pedido_detail(request, pk):
    pedido = get_object_or_404(Pedido, pk=pk)
    envio_status = None
    if pedido.melhor_envio_id:
        url = f"https://sandbox.melhorenvio.com.br/api/v2/me/shipment/{pedido.melhor_envio_id}"
        headers = {
            "Authorization": f"Bearer {settings.MELHOR_ENVIO_TOKEN}",
            "Accept": "application/json"
        }
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            envio_status = response.json()
    return render(request, 'dashboard/pedidos/detail.html', {'pedido': pedido, 'envio_status': envio_status})

@staff_member_required
def pedido_update(request, pk):
    pedido = get_object_or_404(Pedido, pk=pk)
    if request.method == 'POST':
        form = PedidoUpdateForm(request.POST, instance=pedido)
        if form.is_valid():
            old_status = pedido.status
            form.save()
            if old_status != form.instance.status:
                HistoricoPedido.objects.create(
                    pedido=pedido,
                    status_antigo=old_status,
                    status_novo=form.instance.status,
                    usuario=request.user,
                    notas='Atualização manual do status'
                )
            messages.success(request, 'Pedido atualizado com sucesso!')
            return redirect('dashboard:pedido_detail', pk=pedido.pk)
    else:
        form = PedidoUpdateForm(instance=pedido)
    return render(request, 'dashboard/pedidos/update.html', {'form': form, 'pedido': pedido})

@staff_member_required
def pedido_cancel(request, pk):
    pedido = get_object_or_404(Pedido, pk=pk)
    if pedido.status not in ['P', 'PR']:
        messages.error(request, 'Este pedido não pode ser cancelado.')
        return redirect('dashboard:pedido_detail', pk=pedido.pk)
    if request.method == 'POST':
        Reembolso.objects.create(
            pedido=pedido,
            valor=pedido.total,
            status='P',
            motivo='Cancelamento pelo administrador'
        )
        old_status = pedido.status
        pedido.status = 'C'
        pedido.save()
        HistoricoPedido.objects.create(
            pedido=pedido,
            status_antigo=old_status,
            status_novo='C',
            usuario=request.user,
            notas='Cancelamento pelo administrador'
        )
        subject = f'Cancelamento do Pedido #{pedido.id}'
        html_message = render_to_string('dashboard/emails/email_cancelamento.html', {
            'pedido': pedido,
            'motivo': 'Cancelamento pelo administrador',
            'loja_nome': 'Loja de Roupas VSG',
        })
        plain_message = f'Seu pedido #{pedido.id} foi cancelado. Valor: R${pedido.total}. Motivo: Cancelamento pelo administrador.'
        from_email = settings.DEFAULT_FROM_EMAIL
        to_email = pedido.usuario.email
        send_mail(
            subject,
            plain_message,
            from_email,
            [to_email],
            html_message=html_message,
        )
        messages.success(request, 'Pedido cancelado com sucesso! Reembolso registrado e e-mail enviado.')
        return redirect('dashboard:pedido_list')
    return render(request, 'dashboard/pedidos/confirm_cancel.html', {'pedido': pedido})

@staff_member_required
def pedido_export_csv(request):
    filterset = PedidoFilter(request.GET, queryset=Pedido.objects.all())
    pedidos = filterset.qs

    data = []
    for pedido in pedidos:
        data.append({
            'ID': pedido.id,
            'Usuário': pedido.usuario.username,
            'Data': pedido.data_criacao.strftime('%d/%m/%Y %H:%M'),
            'Total': pedido.total,
            'Status': pedido.get_status_display(),
            'Código de Rastreamento': pedido.codigo_rastreamento or 'Não informado',
            'Endereço': f'{pedido.endereco_entrega.rua}, {pedido.endereco_entrega.numero}, {pedido.endereco_entrega.cidade}',
            'Cupom': pedido.cupom.codigo if pedido.cupom else 'Nenhum',
        })

    df = pd.DataFrame(data)
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="pedidos_{timezone.now().strftime("%Y-%m-%d")}.csv"'
    df.to_csv(path_or_buf=response, index=False, encoding='utf-8')
    return response

@staff_member_required
def pedido_gerar_etiqueta(request, pk):
    pedido = get_object_or_404(Pedido, pk=pk)
    if pedido.status not in ['PR', 'E']:
        messages.error(request, 'Este pedido não está em um status válido para gerar etiqueta.')
        return redirect('dashboard:pedido_detail', pk=pedido.pk)
    if request.method == 'POST':
        response = criar_envio_melhor_envio(pedido, settings.MELHOR_ENVIO_TOKEN)
        if 'id' in response:
            pedido.melhor_envio_id = response['id']
            pedido.codigo_rastreamento = response.get('tracking', '')
            pedido.save()
            HistoricoPedido.objects.create(
                pedido=pedido,
                status_antigo=pedido.status,
                status_novo=pedido.status,
                usuario=request.user,
                notas='Etiqueta gerada via Melhor Envio'
            )
            messages.success(request, 'Etiqueta gerada com sucesso!')
        else:
            messages.error(request, f'Erro ao gerar etiqueta: {response.get("message", "Erro desconhecido")}')
        return redirect('dashboard:pedido_detail', pk=pedido.pk)
    return render(request, 'dashboard/pedidos/confirm_gerar_etiqueta.html', {'pedido': pedido})

# --- Gestão de Reembolsos ---
@staff_member_required
def reembolso_list(request):
    filterset = ReembolsoFilter(request.GET, queryset=Reembolso.objects.all())
    reembolsos = filterset.qs
    context = {
        'filter': filterset,
        'reembolsos': reembolsos,
    }
    return render(request, 'dashboard/reembolsos/list.html', context)

@staff_member_required
def reembolso_process(request, pk):
    reembolso = get_object_or_404(Reembolso, pk=pk)
    if reembolso.status != 'P':
        messages.error(request, 'Este reembolso não está pendente.')
        return redirect('dashboard:reembolso_list')
    if request.method == 'POST':
        form = ReembolsoProcessForm(request.POST, instance=reembolso)
        if form.is_valid():
            status = form.cleaned_data['status']
            reembolso.notas = form.cleaned_data['notas']
            reembolso.status = status
            if status == 'A' and reembolso.pedido.payment_intent_id:
                try:
                    stripe_refund = stripe.Refund.create(
                        payment_intent=reembolso.pedido.payment_intent_id,
                        amount=int(reembolso.valor * 100),
                    )
                    reembolso.status = 'C'
                    reembolso.notas += f'\nReembolso Stripe ID: {stripe_refund.id}'
                except stripe.error.StripeError as e:
                    messages.error(request, f'Erro ao processar reembolso na Stripe: {str(e)}')
                    return redirect('dashboard:reembolso_process', pk=pk)
            reembolso.save()
            subject = f'Atualização do Reembolso do Pedido #{reembolso.pedido.id}'
            html_message = render_to_string('dashboard/emails/email_reembolso_status.html', {
                'reembolso': reembolso,
                'status': reembolso.get_status_display(),
                'loja_nome': 'Loja de Roupas VSG',
            })
            plain_message = f'O reembolso do seu pedido #{reembolso.pedido.id} foi {reembolso.get_status_display().lower()}.'
            from_email = settings.DEFAULT_FROM_EMAIL
            to_email = reembolso.pedido.usuario.email
            send_mail(
                subject,
                plain_message,
                from_email,
                [to_email],
                html_message=html_message,
            )
            messages.success(request, f'Reembolso {reembolso.get_status_display().lower()} com sucesso!')
            return redirect('dashboard:reembolso_list')
    else:
        form = ReembolsoProcessForm(instance=reembolso)
    return render(request, 'dashboard/reembolsos/process.html', {'form': form, 'reembolso': reembolso})

# --- Relatórios de Reembolsos ---
@staff_member_required
def relatorios_reembolsos(request):
    filterset = RelatorioReembolsoFilter(request.GET, queryset=Reembolso.objects.all())
    reembolsos = filterset.qs

    reembolsos_data = reembolsos.values('data_criacao__date').annotate(total=Sum('valor')).order_by('data_criacao__date')
    reembolsos_df = pd.DataFrame(list(reembolsos_data))
    if not reembolsos_df.empty:
        reembolsos_df['data_criacao__date'] = pd.to_datetime(reembolsos_df['data_criacao__date'])
        reembolsos_df = reembolsos_df.set_index('data_criacao__date').resample('M').sum().fillna(0).reset_index()
        reembolsos_labels = reembolsos_df['data_criacao__date'].dt.strftime('%Y-%m').tolist()
        reembolsos_values = reembolsos_df['total'].tolist()
    else:
        reembolsos_labels = []
        reembolsos_values = []

    if 'export' in request.GET:
        data = []
        for reembolso in reembolsos:
            data.append({
                'ID': reembolso.id,
                'Pedido': reembolso.pedido.id,
                'Valor': reembolso.valor,
                'Status': reembolso.get_status_display(),
                'Data': reembolso.data_criacao.strftime('%d/%m/%Y %H:%M'),
                'Motivo': reembolso.motivo or 'Não informado',
                'Notas': reembolso.notas or 'Nenhuma',
            })
        df = pd.DataFrame(data)
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="reembolsos_{timezone.now().strftime("%Y-%m-%d")}.csv"'
        df.to_csv(path_or_buf=response, index=False, encoding='utf-8')
        return response

    context = {
        'filter': filterset,
        'reembolsos': reembolsos,
        'reembolsos_labels': reembolsos_labels,
        'reembolsos_values': reembolsos_values,
    }
    return render(request, 'dashboard/relatorios/reembolsos.html', context)

# --- Notificações ---
@staff_member_required
def notificacoes_list(request):
    notificacoes = Notification.objects.filter(recipient=request.user).order_by('-timestamp')
    if request.method == 'POST' and 'mark_all_read' in request.POST:
        notificacoes.update(unread=False)
        messages.success(request, 'Todas as notificações foram marcadas como lidas.')
        return redirect('dashboard:notificacoes_list')
    context = {
        'notificacoes': notificacoes,
    }
    return render(request, 'dashboard/notificacoes/list.html', context)

# --- Gestão de Clientes ---
@staff_member_required
def cliente_list(request):
    filterset = ClienteFilter(request.GET, queryset=User.objects.filter(pedidos__isnull=False).distinct())
    clientes = filterset.qs

    clientes_pedidos = User.objects.filter(pedidos__isnull=False).annotate(total_pedidos=Count('pedidos')).order_by('-total_pedidos')[:5]
    clientes_df = pd.DataFrame(list(clientes_pedidos.values('username', 'total_pedidos')))
    clientes_labels = clientes_df['username'].tolist() if not clientes_df.empty else []
    clientes_values = clientes_df['total_pedidos'].tolist() if not clientes_df.empty else []

    context = {
        'filter': filterset,
        'clientes': clientes,
        'clientes_labels': clientes_labels,
        'clientes_values': clientes_values,
    }
    return render(request, 'dashboard/clientes/list.html', context)

@staff_member_required
def cliente_detail(request, pk):
    cliente = get_object_or_404(User, pk=pk)
    enderecos = Endereco.objects.filter(usuario=cliente)
    pedidos = Pedido.objects.filter(usuario=cliente).order_by('-data_criacao')
    # Favoritos: Assumindo que não há modelo Favorito. Descomentar se existir.
    # favoritos = Favorito.objects.filter(usuario=cliente)
    context = {
        'cliente': cliente,
        'enderecos': enderecos,
        'pedidos': pedidos,
        # 'favoritos': favoritos,
    }
    return render(request, 'dashboard/clientes/detail.html', context)

@staff_member_required
def cliente_update(request, pk):
    cliente = get_object_or_404(User, pk=pk)
    EnderecoFormSet = inlineformset_factory(User, Endereco, fields=('rua', 'numero', 'complemento', 'bairro', 'cidade', 'estado', 'cep'), extra=1, can_delete=True)
    if request.method == 'POST':
        form = ClienteUpdateForm(request.POST, instance=cliente)
        endereco_formset = EnderecoFormSet(request.POST, instance=cliente)
        if form.is_valid() and endereco_formset.is_valid():
            form.save()
            endereco_formset.save()
            messages.success(request, 'Informações do cliente atualizadas com sucesso!')
            return redirect('dashboard:cliente_detail', pk=cliente.pk)
    else:
        form = ClienteUpdateForm(instance=cliente)
        endereco_formset = EnderecoFormSet(instance=cliente)
    return render(request, 'dashboard/clientes/update.html', {
        'form': form,
        'endereco_formset': endereco_formset,
        'cliente': cliente,
    })

@staff_member_required
def estoque_list(request):
    filterset = EstoqueFilter(request.GET, queryset=Produto.objects.all())
    produtos = filterset.qs

    estoque_categoria = Produto.objects.values('categoria__nome').annotate(total=Sum('estoque')).order_by('-total')
    estoque_df = pd.DataFrame(list(estoque_categoria))
    estoque_labels = estoque_df['categoria__nome'].tolist() if not estoque_df.empty else []
    estoque_values = estoque_df['total'].tolist() if not estoque_df.empty else []

    if 'export' in request.GET:
        data = []
        for produto in produtos:
            data.append({
                'ID': produto.id,
                'Nome': produto.nome,
                'Categoria': produto.categoria.nome if produto.categoria else 'Sem categoria',
                'Marca': produto.marca.nome if produto.marca else 'Sem marca',
                'Estoque': produto.estoque,
                'Preço': produto.preco,
                'Ativo': 'Sim' if produto.ativo else 'Não',
            })
        df = pd.DataFrame(data)
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="estoque_{timezone.now().strftime("%Y-%m-%d")}.csv"'
        df.to_csv(path_or_buf=response, index=False, encoding='utf-8')
        return response

    context = {
        'filter': filterset,
        'produtos': produtos,
        'estoque_labels': estoque_labels,
        'estoque_values': estoque_values,
    }
    return render(request, 'dashboard/estoque/list.html', context)

@staff_member_required
def cupom_list(request):
    filterset = CupomFilter(request.GET, queryset=Cupom.objects.all())
    cupons = filterset.qs

    cupons_uso = Pedido.objects.filter(cupom__isnull=False).values('cupom__codigo').annotate(total=Count('id')).order_by('-total')
    cupons_df = pd.DataFrame(list(cupons_uso))
    cupons_labels = cupons_df['cupom__codigo'].tolist() if not cupons_df.empty else []
    cupons_values = cupons_df['total'].tolist() if not cupons_df.empty else []

    context = {
        'filter': filterset,
        'cupons': cupons,
        'cupons_labels': cupons_labels,
        'cupons_values': cupons_values,
    }
    return render(request, 'dashboard/cupons/list.html', context)

@staff_member_required
def cupom_create(request):
    if request.method == 'POST':
        form = CupomForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cupom criado com sucesso!')
            return redirect('dashboard:cupom_list')
    else:
        form = CupomForm()
    return render(request, 'dashboard/cupons/form.html', {'form': form, 'title': 'Criar Cupom'})

@staff_member_required
def cupom_update(request, pk):
    cupom = get_object_or_404(Cupom, pk=pk)
    if request.method == 'POST':
        form = CupomForm(request.POST, instance=cupom)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cupom atualizado com sucesso!')
            return redirect('dashboard:cupom_list')
    else:
        form = CupomForm(instance=cupom)
    return render(request, 'dashboard/cupons/form.html', {'form': form, 'title': 'Editar Cupom'})

@staff_member_required
def cupom_delete(request, pk):
    cupom = get_object_or_404(Cupom, pk=pk)
    if request.method == 'POST':
        cupom.delete()
        messages.success(request, 'Cupom excluído com sucesso!')
        return redirect('dashboard:cupom_list')
    return render(request, 'dashboard/cupons/confirm_delete.html', {'cupom': cupom})