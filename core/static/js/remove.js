document.addEventListener('DOMContentLoaded', function() {
  // Delegation para lidar com cliques nos botões de remoção
  document.addEventListener('click', async function(e) {
      if (e.target.closest('.item-remove')) {
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

              const data = await response.json();

              if (data.success) {
                  // SOLUÇÃO PARA REMOVER O ITEM VISUALMENTE
                  const itemContainer = form.closest('.item-carrinho, tr, .cart-item, .row-item');
                  
                  if (itemContainer) {
                      // Adiciona animação de fade out antes de remover
                      itemContainer.style.transition = 'opacity 0.3s';
                      itemContainer.style.opacity = '0';
                      
                      // Remove o elemento após a animação
                      setTimeout(() => {
                          itemContainer.remove();
                          
                          // Atualiza o total ou contador se existir
                          if (data.itens_count !== undefined) {
                              const counter = document.querySelector('.cart-count, .carrinho-contador');
                              if (counter) counter.textContent = data.itens_count;
                          }
                          
                          // Verifica se o carrinho está vazio
                          if (data.itens_count === 0) {
                              const emptyCart = document.querySelector('.carrinho-vazio, .empty-cart');
                              if (emptyCart) emptyCart.style.display = 'block';
                          }
                      }, 300);
                  }
                  
                  showMessage('Item removido com sucesso!', 'success');
              } else {
                  showMessage(data.message || 'Erro ao remover item', 'error');
              }
          } catch (error) {
              console.error('Erro:', error);
              showMessage('Erro na comunicação com o servidor', 'error');
          }
      }
  });

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