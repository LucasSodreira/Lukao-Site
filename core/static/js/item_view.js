// =====================
// Quantidade
// =====================
function updateQuantityDisplay(quantity) {
    document.getElementById("quantity").textContent = quantity;
    document.getElementById("selected-quantity").value = quantity;
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
    quantity++;
    updateQuantityDisplay(quantity);
}

// =====================
// Bottom Sheet (mobile filtros)
// =====================
function toggleBottomSheet() {
    const bottomSheet = document.getElementById('bottomSheet');
    bottomSheet.classList.toggle('open');
}

// =====================
// Seleção de cor/tamanho e estoque
// =====================

// Mapeia as variações para fácil acesso no JS
// O array 'variacoes' deve ser definido no template item_view.html
// Exemplo de definição no template:
// <script>const variacoes = [...];</script>
let selectedCorId = null;
let selectedTamanho = null;
let selectedVariacaoId = null;

function selectColor(corId) {
    selectedCorId = corId;
    // Destaca cor selecionada
    document.querySelectorAll('.color-btn').forEach(btn => {
        btn.classList.toggle('selected', btn.getAttribute('data-cor-id') == corId);
        // Corrige: sempre mostra todas as cores
        btn.style.display = '';
    });
    // Mostra todos os tamanhos, mas só habilita os da cor selecionada
    document.querySelectorAll('.size-btn').forEach(btn => {
        if (btn.getAttribute('data-cor-id') == corId) {
            btn.style.display = '';
            if (parseInt(btn.getAttribute('data-estoque')) > 0) {
                btn.disabled = false;
                btn.classList.remove('disabled');
            } else {
                btn.disabled = true;
                btn.classList.add('disabled');
            }
        } else {
            btn.style.display = '';
            btn.disabled = true;
            btn.classList.add('disabled');
        }
    });
    // Limpa seleção de tamanho e mantém a mensagem de estoque limpa
    selectedTamanho = null;
    selectedVariacaoId = null;
    const estoqueInfo = document.getElementById('estoque-info');
    if (estoqueInfo) estoqueInfo.innerText = '';
    const selectedVariacao = document.getElementById('selected-variacao');
    if (selectedVariacao) selectedVariacao.value = '';
    const addToCartBtn = document.getElementById('add-to-cart-btn');
    if (addToCartBtn) addToCartBtn.disabled = true;
}

function selectSize(btn) {
    if (btn.classList.contains('disabled')) return;
    selectedTamanho = btn.getAttribute('data-tamanho');
    selectedVariacaoId = btn.getAttribute('data-variacao-id');
    // Destaca tamanho selecionado
    document.querySelectorAll('.size-btn').forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');
    // Mostra estoque
    const estoque = btn.getAttribute('data-estoque');
    const estoqueInfo = document.getElementById('estoque-info');
    if (estoqueInfo) estoqueInfo.innerText = `Estoque disponível: ${estoque}`;
    const selectedVariacao = document.getElementById('selected-variacao');
    if (selectedVariacao) selectedVariacao.value = selectedVariacaoId;
    const addToCartBtn = document.getElementById('add-to-cart-btn');
    if (addToCartBtn) addToCartBtn.disabled = (parseInt(estoque) === 0);
}

// Inicialização: seleciona a primeira cor disponível e tamanho disponível
document.addEventListener('DOMContentLoaded', function() {
    // Seleciona a primeira cor com estoque
    let firstCorId = null;
    const btns = document.querySelectorAll('.size-btn');
    for (let i = 0; i < btns.length; i++) {
        if (parseInt(btns[i].getAttribute('data-estoque')) > 0) {
            firstCorId = btns[i].getAttribute('data-cor-id');
            break;
        }
    }
    if (firstCorId) {
        selectColor(firstCorId);
        // Seleciona o primeiro tamanho disponível para essa cor
        let firstSizeBtn = Array.from(document.querySelectorAll('.size-btn')).find(
            btn => btn.getAttribute('data-cor-id') == firstCorId && parseInt(btn.getAttribute('data-estoque')) > 0
        );
        if (firstSizeBtn) {
            selectSize(firstSizeBtn);
        }
    }

    // Lógica para o botão Buy Now (pode ser igual ao Add to Cart ou diferente)
    const buyNowBtn = document.querySelector('.buy-now-btn');
    if (buyNowBtn) {
        buyNowBtn.addEventListener('click', function() {
            const form = document.querySelector('.add-to-cart-form');
            if (form) form.submit();
        });
    }
});

function toggleColorFilter(cor) {
    const input = document.getElementById('colorFilters');
    let cores = input.value ? input.value.split(',') : [];

    const index = cores.indexOf(cor);
    if (index > -1) {
        cores.splice(index, 1);
    } else {
        cores.push(cor);
    }

    // Remove duplicatas e entradas vazias
    const coresFiltradas = [...new Set(cores)].filter(c => c);
    input.value = coresFiltradas.join(',');
}

function validateAddToCart() {
    let msg = '';
    const variacaoId = document.getElementById('selected-variacao').value;
    const quantity = parseInt(document.getElementById('selected-quantity').value);
    if (!variacaoId) {
        msg = 'Selecione uma cor e tamanho disponível.';
    } else if (isNaN(quantity) || quantity < 1) {
        msg = 'Quantidade inválida.';
    } else {
        // Checa estoque
        const btn = document.querySelector('.size-btn.selected');
        if (btn) {
            const estoque = parseInt(btn.getAttribute('data-estoque'));
            if (quantity > estoque) {
                msg = `Só há ${estoque} unidade(s) disponível(is) para esta variação.`;
            }
        }
    }
    document.getElementById('js-validation').innerText = msg;
    return msg === '';
}

function validateBuyNow() {
    if (validateAddToCart()) {
        document.getElementById('add-to-cart-form').submit();
    }
}

// Bloqueia envio do formulário pelo Enter se não estiver válido
const addToCartForm = document.getElementById('add-to-cart-form');
if (addToCartForm) {
    addToCartForm.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !validateAddToCart()) {
            e.preventDefault();
        }
    });
}

// Avisa se tentar aumentar quantidade além do estoque
function increaseQuantity() {
    let quantity = parseInt(document.getElementById("quantity").textContent);
    const btn = document.querySelector('.size-btn.selected');
    let estoque = 9999;
    if (btn) {
        estoque = parseInt(btn.getAttribute('data-estoque'));
    }
    if (quantity < estoque) {
        quantity++;
        updateQuantityDisplay(quantity);
        document.getElementById('js-validation').innerText = '';
    } else {
        document.getElementById('js-validation').innerText = `Só há ${estoque} unidade(s) disponível(is) para esta variação.`;
    }
}

function decreaseQuantity() {
    let quantity = parseInt(document.getElementById("quantity").textContent);
    if (quantity > 1) {
        quantity--;
        updateQuantityDisplay(quantity);
        document.getElementById('js-validation').innerText = '';
    }
}

document.querySelectorAll('.color-circle').forEach(btn => {
    btn.addEventListener('click', function() {
        const corId = this.getAttribute('data-cor-id');
        selectColor(corId);
    });
});