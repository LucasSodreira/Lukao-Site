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

    input.value = cores.join(',');
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

    const coresFiltradas = [...new Set(cores)].filter(c => c);
    input.value = coresFiltradas.join(',');
}

function toggleColorFilter(cor) {
    const colorFiltersInput = document.getElementById('colorFilters');

    // Define a cor selecionada diretamente no campo oculto
    colorFiltersInput.value = cor;

    // Submete o formulário para aplicar o filtro
    
}