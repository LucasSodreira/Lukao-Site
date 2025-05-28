// =====================
// Quantidade
// =====================
function updateQuantityDisplay(quantity) {
    document.getElementById("quantity").textContent = quantity;
    const selectedQuantityInput = document.getElementById("selected-quantity");
    if (selectedQuantityInput) {
        selectedQuantityInput.value = quantity;
    }
}

function decreaseQuantity() {
    let quantity = parseInt(document.getElementById("quantity").textContent);
    if (quantity > 1) {
        quantity--;
        updateQuantityDisplay(quantity);
    }
}

function increaseQuantity() {
    let quantity = parseInt(document.getElementById("quantity").textContent);
    const btn = document.querySelector('.size-btn.selected');
    let estoqueMaximo = Infinity; // Permite aumentar se nenhum tamanho estiver selecionado ou se não houver info de estoque

    if (btn) {
        const variacaoId = parseInt(btn.getAttribute('data-variacao-id'));
        if (variacaoId) {
            const variacao = variacoesDisponiveis.find(v => v.id === variacaoId);
            if (variacao) {
                estoqueMaximo = variacao.estoque;
            }
        }
    }

    if (quantity < estoqueMaximo) {
        quantity++;
        updateQuantityDisplay(quantity);
        document.getElementById('js-validation').innerText = ''; // Limpa aviso de estoque
    } else {
        document.getElementById('js-validation').innerText = 'Quantidade máxima em estoque atingida.';
    }
}

// =====================
// Seleção de cor/tamanho e estoque
// =====================

let selectedCorId = null;
let selectedTamanhoId = null; // Agora guardamos o ID do AtributoValor do tamanho
let selectedVariacaoId = null;

function selectColor(corId) {
    selectedCorId = corId;
    selectedTamanhoId = null; // Reseta o tamanho selecionado
    selectedVariacaoId = null; // Reseta a variação selecionada

    // Destaca cor selecionada
    document.querySelectorAll('.color-btn').forEach(btn => {
        btn.classList.remove('selected');
        if (parseInt(btn.getAttribute('data-cor-id')) === corId) {
            btn.classList.add('selected');
        }
    });

    // Habilita/desabilita e mostra/oculta botões de tamanho baseados na cor selecionada e estoque
    document.querySelectorAll('.size-btn').forEach(btn => {
        const tamanhoId = parseInt(btn.getAttribute('data-tamanho-id'));
        let disponivelNestaCor = false;
        let estoqueDisponivel = 0;

        // Verifica se existe alguma variação com a cor E o tamanho selecionados que tenha estoque
        variacoesDisponiveis.forEach(variacao => {
            const temCor = variacao.atributos.some(attr => attr.tipo === 'Cor' && attr.id === selectedCorId);
            const temTamanho = variacao.atributos.some(attr => attr.tipo === 'Tamanho' && attr.id === tamanhoId);
            if (temCor && temTamanho && variacao.estoque > 0) {
                disponivelNestaCor = true;
                estoqueDisponivel = variacao.estoque; // Poderia ser a soma, mas para o botão individual, o estoque da variação específica
            }
        });

        if (disponivelNestaCor) {
            btn.disabled = false;
            btn.classList.remove('disabled');
            btn.querySelector('.sem-estoque').style.display = 'none';
            // btn.setAttribute('data-estoque', estoqueDisponivel); // O estoque já vem da variação ao selecionar o tamanho
        } else {
            btn.disabled = true;
            btn.classList.add('disabled');
            btn.querySelector('.sem-estoque').style.display = 'inline';
        }
        btn.classList.remove('selected'); // Remove seleção de tamanho anterior
    });

    updateEstoqueInfo(null);
    updateAddToCartButtonState();
    updateQuantityDisplay(1); // Reseta quantidade para 1
}

function selectSize(btn) {
    if (btn.classList.contains('disabled')) return;

    selectedTamanhoId = parseInt(btn.getAttribute('data-tamanho-id'));

    // Destaca tamanho selecionado
    document.querySelectorAll('.size-btn').forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');

    // Encontra a variação correspondente à cor e tamanho selecionados
    const variacaoSelecionada = variacoesDisponiveis.find(v => 
        v.atributos.some(attr => attr.tipo === 'Cor' && attr.id === selectedCorId) &&
        v.atributos.some(attr => attr.tipo === 'Tamanho' && attr.id === selectedTamanhoId) &&
        v.estoque > 0
    );

    if (variacaoSelecionada) {
        selectedVariacaoId = variacaoSelecionada.id;
        updateEstoqueInfo(variacaoSelecionada.estoque);
        btn.setAttribute('data-variacao-id', variacaoSelecionada.id); // Adiciona o ID da variação ao botão
    } else {
        selectedVariacaoId = null;
        updateEstoqueInfo(0); // Ou alguma mensagem de erro
    }
    
    updateAddToCartButtonState();
    updateQuantityDisplay(1); // Reseta quantidade para 1
    document.getElementById('js-validation').innerText = ''; // Limpa aviso de estoque ao selecionar novo tamanho
}

function updateEstoqueInfo(estoque) {
    const estoqueInfo = document.getElementById('estoque-info');
    if (estoqueInfo) {
        if (estoque !== null && estoque > 0) {
            estoqueInfo.textContent = `Estoque disponível: ${estoque}`;
            estoqueInfo.style.color = 'green';
        } else if (estoque === 0) {
            estoqueInfo.textContent = 'Produto indisponível nesta combinação.';
            estoqueInfo.style.color = 'red';
        } else {
            estoqueInfo.textContent = 'Selecione cor e tamanho para ver o estoque.';
            estoqueInfo.style.color = 'orange';
        }
    }
}

function updateAddToCartButtonState() {
    const addToCartBtn = document.getElementById('add-to-cart-btn'); // Assumindo que seu botão tem este ID
    const buyNowBtn = document.querySelector('.buy-now-btn'); // E o botão de comprar agora
    const selectedVariacaoInput = document.getElementById('selected-variacao');

    if (selectedVariacaoId) {
        if (addToCartBtn) addToCartBtn.disabled = false;
        if (buyNowBtn) buyNowBtn.disabled = false;
        if (selectedVariacaoInput) selectedVariacaoInput.value = selectedVariacaoId;
    } else {
        if (addToCartBtn) addToCartBtn.disabled = true;
        if (buyNowBtn) buyNowBtn.disabled = true;
        if (selectedVariacaoInput) selectedVariacaoInput.value = '';
    }
}

// =====================
// Outras Funções (Ex: Bottom Sheet, se ainda for usar)
// =====================
function toggleBottomSheet() {
    const bottomSheet = document.getElementById('bottomSheet');
    if (bottomSheet) {
        bottomSheet.classList.toggle('open');
    }
}

// Limpa funções não mais necessárias ou que foram refatoradas acima
// function toggleColorFilter(cor) { ... } // Se não estiver usando filtros de cor desta forma

// Atualiza os event listeners para os botões de cor se eles são adicionados dinamicamente
// ou se a lógica de seleção mudou (já coberto no selectColor e selectSize)

// Garante que os botões de quantidade estejam funcionando corretamente
// (já ajustado nas funções increaseQuantity e decreaseQuantity)