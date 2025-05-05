# import stripe
# from django.conf import settings
# from django.http import HttpResponse
# from django.views.decorators.csrf import csrf_exempt
# from core.models import Pedido
# import json

# @csrf_exempt # Desabilita CSRF para webhooks externos
# def stripe_webhook(request):
#     payload = request.body
#     sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
#     endpoint_secret = settings.STRIPE_WEBHOOK_SECRET # Configure no settings.py
#     event = None

#     try:
#         event = stripe.Webhook.construct_event(
#             payload, sig_header, endpoint_secret
#         )
#     except ValueError as e:
#         # Payload inválido
#         return HttpResponse(status=400)
#     except stripe.error.SignatureVerificationError as e:
#         # Assinatura inválida
#         return HttpResponse(status=400)

#     # Lida com o evento payment_intent.succeeded
#     if event['type'] == 'payment_intent.succeeded':
#         payment_intent = event['data']['object'] # contém o PaymentIntent
#         print('PaymentIntent bem-sucedido!', payment_intent)
#         # Busca o pedido usando o metadata
#         pedido_id = payment_intent.get('metadata', {}).get('pedido_id')
#         if pedido_id:
#             try:
#                 pedido = Pedido.objects.get(id=pedido_id)
#                 # Atualiza o status do pedido para Concluído ou Processando
#                 # Evita atualizar se já estiver concluído/cancelado
#                 if pedido.status == 'P': # Apenas se estava Pendente
#                     pedido.status = 'C' # Ou outro status apropriado como 'Processando Pagamento'
#                     pedido.metodo_pagamento = f"stripe_{payment_intent.payment_method_types[0]}" # Ex: stripe_card, stripe_pix
#                     pedido.save()
#                     # Aqui você pode:
#                     # - Enviar email de confirmação
#                     # - Limpar o carrinho do usuário (se não foi feito antes)
#                     # - Disparar signals para outras ações (ex: nota fiscal)
#                     print(f"Pedido {pedido_id} atualizado para {pedido.status}")
#             except Pedido.DoesNotExist:
#                 print(f"Erro: Pedido {pedido_id} não encontrado.")
#         else:
#             print("Erro: pedido_id não encontrado nos metadados do PaymentIntent.")

#     # Lida com outros eventos se necessário (ex: payment_intent.payment_failed)
#     elif event['type'] == 'payment_intent.payment_failed':
#         payment_intent = event['data']['object']
#         print('PaymentIntent falhou!', payment_intent)
#         pedido_id = payment_intent.get('metadata', {}).get('pedido_id')
#         if pedido_id:
#              try:
#                 pedido = Pedido.objects.get(id=pedido_id)
#                 # Opcional: Mudar status para 'Falha no Pagamento' ou notificar usuário
#                 print(f"Falha no pagamento do Pedido {pedido_id}")
#              except Pedido.DoesNotExist:
#                 print(f"Erro: Pedido {pedido_id} não encontrado para falha.")

#     else:
#         print(f'Evento não tratado: {event["type"]}')

#     return HttpResponse(status=200) # Confirma recebimento para o Stripe
pass # Adiciona um pass para evitar erro de arquivo vazio se todo o conteúdo for comentado
