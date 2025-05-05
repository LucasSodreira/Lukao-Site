function toggleBottomSheet() {
    const bottomSheet = document.getElementById('bottomSheet');
    bottomSheet.classList.toggle('active');
}

// Função para aplicar os filtros
function applyFilters() {
    const selectedSizes = Array.from(document.querySelectorAll('.sizes input:checked')).map(input => input.id);
    const selectedColors = Array.from(document.querySelectorAll('.colors div.selected')).map(div => div.style.backgroundColor);
    const priceRange = document.querySelector('.price-range input').value;

    const products = document.querySelectorAll('.product-card');
    products.forEach(product => {
        const productPrice = parseInt(product.querySelector('.price').textContent.replace('$', ''));
        const productSize = product.dataset.size;
        const productColor = product.dataset.color;

        const matchesSize = selectedSizes.length === 0 || selectedSizes.includes(productSize);
        const matchesColor = selectedColors.length === 0 || selectedColors.includes(productColor);
        const matchesPrice = productPrice <= priceRange;

        if (matchesSize && matchesColor && matchesPrice) {
            product.style.display = 'block';
        } else {
            product.style.display = 'none';
        }
    });
}

// Adiciona evento de clique para os filtros de cores
document.querySelectorAll('.colors div').forEach(colorDiv => {
    colorDiv.addEventListener('click', () => {
        colorDiv.classList.toggle('selected');
    });
});

// Adiciona evento ao botão de aplicar filtros
document.querySelectorAll('.apply-filter').forEach(button => {
    button.addEventListener('click', () => {
        applyFilters();
        toggleBottomSheet(); // Fecha o Bottom Sheet no mobile
    });
});

function selectCategoria(categoria) {
    const input = document.getElementById('categoriaFilter');
    input.value = categoria;
}

// Preenche o input oculto de preço quando o usuário mexe no slider
document.getElementById('priceRange').addEventListener('change', function() {
    document.getElementById('priceFilter').value = this.value;
});

function toggleSizeFilter(tamanho) {
    const input = document.getElementById('sizeFilters');
    let tamanhos = input.value ? input.value.split(',') : [];

    const index = tamanhos.indexOf(tamanho);
    if (index > -1) {
        tamanhos.splice(index, 1);
    } else {
        tamanhos.push(tamanho);
    }

    // Remove duplicatas e entradas vazias
    const tamanhosFiltrados = [...new Set(tamanhos)].filter(t => t);
    input.value = tamanhosFiltrados.join(',');
}

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

function clearCustomPriceAndSubmit() {
    // Atualiza o label antes de submeter
    var checkedRadio = document.querySelector('input[name="faixa_preco"]:checked');
    if (checkedRadio) {
        var label = checkedRadio.closest('label').textContent.trim();
        document.getElementById('faixa_preco_label').value = label;
    }
    document.getElementById('preco_min').value = '';
    document.getElementById('preco_max').value = '';
    document.getElementById('filterForm').submit();
}

function clearPriceRangeSelection() {
    // Desmarca qualquer radio button de faixa de preço selecionado ao digitar nos inputs
    const radios = document.querySelectorAll('input[name="faixa_preco"]');
    radios.forEach(radio => {
        radio.checked = false; // Garante que os radios sejam desmarcados
    });
}

function removeFilter(paramName, paramValue = null) {
    const url = new URL(window.location.href);
    const params = url.searchParams;

    if (paramName === 'faixa_preco') {
        params.delete('faixa_preco');
        params.delete('faixa_preco_label'); // Limpa o label também!
    } else if (paramName === 'cores' || paramName === 'tamanhos') {
        // Lógica para remover valor específico de parâmetro multivalor (separado por vírgula)
        let values = params.get(paramName) ? params.get(paramName).split(',') : [];
        if (paramValue) {
            // Filtra para remover o valor específico
            values = values.filter(v => v.trim() !== paramValue.trim());
        }
        // Se ainda houver valores, atualiza o parâmetro
        if (values.length > 0) {
            params.set(paramName, values.join(','));
        } else {
            // Se não houver mais valores, remove o parâmetro completamente
            params.delete(paramName);
        }
    } else if (paramName === 'preco_custom') {
         // Caso especial para remover min e max juntos
         params.delete('preco_min');
         params.delete('preco_max');
    } else {
        // Remove parâmetro simples (categoria, faixa_preco)
        params.delete(paramName);
    }

    // Limpa parâmetros que possam ter ficado vazios (ex: cores=, tamanhos=)
    const keysToDelete = [];
    for (const [key, value] of params.entries()) {
        if (value === '') {
            keysToDelete.push(key);
        }
    }
    keysToDelete.forEach(key => params.delete(key));

    // Redireciona para a nova URL sem o filtro
    window.location.href = url.toString();
}

document.querySelectorAll('input[name="faixa_preco"]').forEach(function(radio) {
    radio.addEventListener('change', function() {
        // Pega o texto do label da faixa selecionada
        var label = this.closest('label').textContent.trim();
        document.getElementById('faixa_preco_label').value = label;
    });
});

document.querySelectorAll('.clear-all-filters').forEach(btn => {
    btn.addEventListener('click', function(e) {
        // Se for um link, não precisa fazer nada, pois a URL já será limpa
        // Se for um botão que submete o form, limpe os campos ocultos:
        document.getElementById('faixa_preco_label').value = '';
    });
});

function toggleFilterSection(headerElem) {
    const section = headerElem.closest('.filter-section');
    section.classList.toggle('collapsed');
}

document.addEventListener('DOMContentLoaded', function() {
    function removeEmptyHiddenInputs(form) {
        // Crie um array para evitar problemas ao remover elementos durante a iteração
        const hiddenInputs = Array.from(form.querySelectorAll('input[type="hidden"]'));
        hiddenInputs.forEach(function(el) {
            if (!el.value) {
                el.remove();
            }
        });
        // Opcional: também remove selects vazios se necessário
        const selects = Array.from(form.querySelectorAll('select'));
        selects.forEach(function(el) {
            if (!el.value) {
                el.remove();
            }
        });
    }

    var filterForm = document.getElementById('filterForm');
    if (filterForm) {
        filterForm.addEventListener('submit', function(e) {
            removeEmptyHiddenInputs(filterForm);
        });
    }
    var mobileFilterForm = document.getElementById('mobileFilterForm');
    if (mobileFilterForm) {
        mobileFilterForm.addEventListener('submit', function(e) {
            removeEmptyHiddenInputs(mobileFilterForm);
        });
    }
});