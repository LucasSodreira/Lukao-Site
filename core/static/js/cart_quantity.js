document.addEventListener('DOMContentLoaded', function() {

      // Aumentar quantidade
    document.addEventListener('click', async function(e) {
        if (e.target.classList.contains('quantity-increase')) {
            e.preventDefault();

            const form = e.target.closest('form');
            await handleQuantityAjax(form, 'aumentar');
        }
        if (e.target.classList.contains('quantity-decrease')) {
            e.preventDefault();

            const form = e.target.closest('form');
            await handleQuantityAjax(form, 'diminuir');
        }
    });async function handleQuantityAjax(form, tipo) {
        const url = form.action;
        const csrf = form.querySelector('[name=csrfmiddlewaretoken]').value;
        const itemDiv = form.closest('.cart-item'); // Container do item
        const quantitySpan = itemDiv.querySelector('.quantity-control span');        
        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrf
                },
                body: new FormData(form)
            });
            
            if (response.ok) {
                const data = await response.json();
                
                if (data.success) {
                    // Se o item foi removido (quantidade chegou a 0), remove o item
                    if (tipo === 'diminuir' && quantitySpan) {
                        const currentQty = parseInt(quantitySpan.textContent);
                        if (currentQty <= 1) {
                            // Remove o item e o divisor se existir
                            const nextHr = itemDiv.nextElementSibling;
                            if (nextHr && nextHr.classList.contains('item-divider')) {
                                nextHr.remove();
                            }
                            itemDiv.remove();
                            showMessage('Item removido do carrinho', 'success');
                        } else {
                            quantitySpan.textContent = currentQty - 1;
                            // Atualizar subtotal do item
                            updateItemSubtotal(itemDiv, currentQty - 1);
                        }
                    } else if (tipo === 'aumentar' && quantitySpan) {
                        const currentQty = parseInt(quantitySpan.textContent);
                        quantitySpan.textContent = currentQty + 1;
                        // Atualizar subtotal do item
                        updateItemSubtotal(itemDiv, currentQty + 1);
                    }
                    
                    // Atualizar totais do carrinho
                    updateCartTotals(data);
                    
                    // Atualizar contador do carrinho no header (se existir)
                    updateCartCounter(data.itens_count);
                    
                    showMessage('Carrinho atualizado!', 'success');
                } else {
                    showMessage(data.message || 'Erro ao atualizar carrinho', 'error');
                }
            } else {
                showMessage('Erro ao atualizar quantidade', 'error');
            }
        } catch (err) {
            console.error('Erro:', err);
            showMessage('Erro de comunicação', 'error');
        }
    }
    
    function updateItemSubtotal(itemDiv, newQuantity) {
        const priceElement = itemDiv.querySelector('.item-price');
        const subtotalElement = itemDiv.querySelector('.item-subtotal');
        
        if (priceElement && subtotalElement) {
            // Extrair preço unitário
            const priceText = priceElement.textContent;
            const priceMatch = priceText.match(/R\$\s*([\d,]+\.?\d*)/);
            if (priceMatch) {
                const unitPrice = parseFloat(priceMatch[1].replace(',', '.'));
                const newSubtotal = (unitPrice * newQuantity).toFixed(2);
                subtotalElement.textContent = `Subtotal: R$ ${newSubtotal.replace('.', ',')}`;
            }
        }
    }
    
    function updateCartTotals(data) {
        // Atualizar subtotal no resumo do pedido
        const summaryRows = document.querySelectorAll('.summary-row');
        summaryRows.forEach(row => {
            const label = row.querySelector('span:first-child');
            if (label && label.textContent.trim() === 'Subtotal') {
                const valueSpan = row.querySelector('span:last-child');
                if (valueSpan) {
                    valueSpan.textContent = `R$ ${data.subtotal.toFixed(2).replace('.', ',')}`;
                }
            }
        });
        
        // Atualizar desconto (se houver)
        if (data.desconto > 0) {
            const discountRow = document.querySelector('.summary-row.discount');
            if (discountRow) {
                const valueSpan = discountRow.querySelector('span:last-child');
                if (valueSpan) {
                    valueSpan.textContent = `-R$ ${data.desconto.toFixed(2).replace('.', ',')}`;
                }
            }
        }
        
        // Atualizar total
        const totalElement = document.querySelector('#total-com-frete, .summary-total span:last-child');
        if (totalElement) {
            totalElement.textContent = `R$ ${data.total_com_cupom.toFixed(2).replace('.', ',')}`;
        }
        
        // Verificar se carrinho ficou vazio
        if (data.itens_count === 0) {
            setTimeout(() => {
                window.location.reload(); // Recarrega para mostrar mensagem de carrinho vazio
            }, 1000);
        }
    }
    
    function updateCartCounter(count) {
        const cartCounters = document.querySelectorAll('.cart-count, #cart-count, .carrinho-contador');
        cartCounters.forEach(counter => {
            counter.textContent = count;
        });
    }

    function showMessage(text, type) {
        const messageDiv = document.getElementById('mensagem-carrinho') || createMessageDiv();
        messageDiv.textContent = text;
        messageDiv.className = `mensagem ${type}`;
        messageDiv.style.display = 'block';
        setTimeout(() => {
            messageDiv.style.display = 'none';
        }, 3000);
    }
    function createMessageDiv() {
        const div = document.createElement('div');
        div.id = 'mensagem-carrinho';
        div.style.position = 'fixed';
        div.style.top = '20px';
        div.style.right = '20px';
        div.style.padding = '15px';
        div.style.borderRadius = '5px';
        div.style.color = 'white';
        div.style.zIndex = '1000';
        document.body.appendChild(div);
        return div;
    }
});
