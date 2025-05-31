document.addEventListener('DOMContentLoaded', function() {

    // Delegation para lidar com cliques nos botões de remoção
  document.addEventListener('click', async function(e) {
      if (e.target.classList.contains('item-remove') || e.target.closest('.item-remove')) {
          e.preventDefault();

          const form = e.target.closest('.remover-form');
          
          if (!confirm('Tem certeza que deseja remover este item?')) {
              return;
          }

          try {
              const response = await fetch(form.action, {
                  method: 'POST',
                  headers: {
                      'X-Requested-With': 'XMLHttpRequest',
                      'X-CSRFToken': form.querySelector('[name=csrfmiddlewaretoken]').value
                  },
                  body: new FormData(form)
              });

              const data = await response.json();              if (data.success) {
                  // SOLUÇÃO PARA REMOVER O ITEM VISUALMENTE
                  const itemContainer = form.closest('.cart-item');
                  
                  if (itemContainer) {
                      // Remove o divisor se existir
                      const nextHr = itemContainer.nextElementSibling;
                      if (nextHr && nextHr.classList.contains('item-divider')) {
                          nextHr.remove();
                      }
                      
                      // Adiciona animação de fade out antes de remover
                      itemContainer.style.transition = 'opacity 0.3s';
                      itemContainer.style.opacity = '0';
                      
                      // Remove o elemento após a animação
                      setTimeout(() => {
                          itemContainer.remove();
                          
                          // Atualiza os totais do carrinho
                          updateCartTotals(data);
                          
                          // Atualiza o contador do carrinho
                          updateCartCounter(data.itens_count);
                          
                          // Verifica se o carrinho está vazio
                          if (data.itens_count === 0) {
                              setTimeout(() => {
                                  window.location.reload(); // Recarrega para mostrar carrinho vazio
                              }, 500);
                          }
                      }, 300);
                  }
                  
                  showMessage('Item removido com sucesso!', 'success');
              } else {
                  showMessage(data.message || 'Erro ao remover item', 'error');
              }          } catch (error) {
              console.error('Erro:', error);
              showMessage('Erro na comunicação com o servidor', 'error');
          }
      }
  });

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