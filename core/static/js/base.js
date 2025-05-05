document.addEventListener('DOMContentLoaded', function() {
    // Modal universal de entrega
    var deliveryInfoTrigger = document.getElementById('deliveryInfoTrigger');
    var deliveryModal = document.getElementById('deliveryModal');
    if (deliveryInfoTrigger && deliveryModal) {
        deliveryInfoTrigger.addEventListener('click', function() {
            deliveryModal.classList.add('active');
        });
    }
    window.closeDeliveryModal = function() {
        deliveryModal.classList.remove('active');
    };
    deliveryModal && deliveryModal.addEventListener('click', function(e) {
        if (e.target === deliveryModal) closeDeliveryModal();
    });

    // AJAX para definir endereço principal
    document.querySelectorAll('.btn-endereco-principal').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            var form = btn.closest('form');
            var url = form.action;
            var csrf = form.querySelector('[name=csrfmiddlewaretoken]').value;
            fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrf,
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(resp => resp.json())
            .then(data => {
                if (data.sucesso) {
                    // Atualiza o display do CEP na navbar
                    var cepDisplay = document.getElementById('cepDisplay');
                    if (cepDisplay) cepDisplay.textContent = data.cep;
                    // Atualiza visual dos cards
                    document.querySelectorAll('.endereco-card').forEach(function(card) {
                        card.classList.remove('principal');
                        var label = card.querySelector('.endereco-principal-label');
                        if (label) label.remove();
                        var btnPrincipal = card.querySelector('.btn-endereco-principal');
                        if (btnPrincipal) btnPrincipal.style.display = '';
                    });
                    var cardAtual = btn.closest('.endereco-card');
                    cardAtual.classList.add('principal');
                    btn.style.display = 'none';
                    var acoes = cardAtual.querySelector('.endereco-acoes');
                    var span = document.createElement('span');
                    span.className = 'endereco-principal-label';
                    span.textContent = 'Principal';
                    acoes.insertBefore(span, acoes.firstChild);
                }
            });
        });
    });

    // CEP para não autenticado (modal de CEP)
    var cepInputModal = document.getElementById('cepInputModal');
    var cepUsarBtnModal = document.getElementById('cepUsarBtnModal');
    var cepStatusModal = document.getElementById('cepStatusModal');
    var cepDisplay = document.getElementById('cepDisplay');
    if (cepInputModal && cepUsarBtnModal && cepStatusModal && cepDisplay) {
        cepUsarBtnModal.addEventListener('click', function() {
            const cep = cepInputModal.value.replace(/\D/g, '');
            if (cep.length !== 8) {
                cepStatusModal.textContent = 'Digite um CEP válido!';
                cepStatusModal.style.color = '#d32f2f';
                return;
            }
            cepStatusModal.textContent = 'Consultando...';
            cepStatusModal.style.color = '#1976d2';
            fetch('https://viacep.com.br/ws/' + cep + '/json/')
                .then(resp => resp.json())
                .then(data => {
                    if (data.erro) {
                        cepStatusModal.textContent = 'CEP não encontrado';
                        cepStatusModal.style.color = '#d32f2f';
                    } else {
                        cepStatusModal.textContent = data.localidade + ' - ' + data.uf;
                        cepStatusModal.style.color = '#1976d2';
                        if (window.usuario_logado) {
                            fetch('/salvar-cep/', {
                                method: 'POST',
                                headers: {
                                    'X-CSRFToken': getCookie('csrftoken'),
                                    'Content-Type': 'application/x-www-form-urlencoded'
                                },
                                body: 'cep=' + encodeURIComponent(cepInputModal.value)
                            })
                            .then(resp => resp.json())
                            .then(data => {
                                if (data.sucesso) {
                                    cepDisplay.textContent = cepInputModal.value;
                                }
                            });
                        } else {
                            localStorage.setItem('cep_usuario', cepInputModal.value);
                            cepDisplay.textContent = cepInputModal.value;
                        }
                        setTimeout(() => {
                            if (typeof window.closeDeliveryModal === 'function') window.closeDeliveryModal();
                        }, 1200);
                    }
                })
                .catch(() => {
                    cepStatusModal.textContent = 'Erro ao consultar CEP';
                    cepStatusModal.style.color = '#d32f2f';
                });
        });
    }

    // Após login, envie o CEP salvo no navegador para o backend
    if (localStorage.getItem('cep_usuario') && window.usuario_logado) {
        fetch('/salvar-cep/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: 'cep=' + encodeURIComponent(localStorage.getItem('cep_usuario'))
        }).then(resp => resp.json()).then(data => {
            // Opcional: atualizar interface
        });
    }

    // Barra de pesquisa: dropdown de categoria sem submit automático
    var categoryBtn = document.getElementById('categoryBtn');
    var categoryMenu = document.getElementById('categoryMenu');
    var categoriaInput = document.getElementById('categoriaInput');
    var searchForm = document.getElementById('searchForm');

    if (categoryBtn && categoryMenu && categoriaInput) {
        // Toggle menu
        categoryBtn.addEventListener('click', function(e) {
            e.preventDefault();
            categoryMenu.style.display = (categoryMenu.style.display === 'block') ? 'none' : 'block';
        });

        // Seleciona categoria sem submeter o form
        categoryMenu.querySelectorAll('a').forEach(function(link) {
            link.addEventListener('click', function(e) {
                e.preventDefault();
                var value = link.getAttribute('data-value');
                categoriaInput.value = value;
                categoryBtn.textContent = value ? value : 'Categorias';
                categoryMenu.style.display = 'none';
            });
        });

        // Fecha menu ao clicar fora
        document.addEventListener('click', function(e) {
            if (!categoryMenu.contains(e.target) && e.target !== categoryBtn) {
                categoryMenu.style.display = 'none';
            }
        });
    }

    // Não envia campos vazios no submit do searchForm
    if (searchForm) {
        searchForm.addEventListener('submit', function(e) {
            Array.from(searchForm.elements).forEach(function(el) {
                if ((el.tagName === 'INPUT' || el.tagName === 'SELECT') && !el.value) {
                    el.disabled = true;
                }
            });
        });
    }
});

// Função para pegar o CSRF token do cookie
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}