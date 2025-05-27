document.addEventListener('DOMContentLoaded', function() {
    // Theme Toggle
    const themeToggle = document.getElementById('theme-toggle');
    const html = document.documentElement;
    
    // Check for saved theme preference
    const savedTheme = localStorage.getItem('theme') || 'light';
    html.setAttribute('data-theme', savedTheme);
    
    // // Função para trocar ícones SVG conforme o tema
    // function trocarSVGsPorTema(theme) {
    //     // Logo
    //     const logoImg = document.getElementById('logo-img');
    //     if (logoImg) {
    //         logoImg.src = theme === 'dark' ? '/static/images/logo.svg' : '/static/images/logo-dark.svg';
    //     }
    
    // }

    // Troca inicial ao carregar
    // trocarSVGsPorTema(savedTheme);

    

    // Category Dropdown
    const categoryBtn = document.getElementById('categoryBtn');
    const categoryMenu = document.getElementById('categoryMenu');
    const categoriaInput = document.getElementById('categoriaInput');

    if (categoryBtn && categoryMenu) {
        categoryBtn.addEventListener('click', () => {
            const isExpanded = categoryBtn.getAttribute('aria-expanded') === 'true';
            categoryBtn.setAttribute('aria-expanded', !isExpanded);
            categoryMenu.style.display = isExpanded ? 'none' : 'block';
        });

        // Close menu when clicking outside
        document.addEventListener('click', (e) => {
            if (!categoryBtn.contains(e.target) && !categoryMenu.contains(e.target)) {
                categoryMenu.style.display = 'none';
                categoryBtn.setAttribute('aria-expanded', 'false');
            }
        });

        // Handle menu items
        categoryMenu.querySelectorAll('a').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const value = item.getAttribute('data-value');
                categoriaInput.value = value;
                categoryBtn.textContent = value || 'Categorias';
                categoryMenu.style.display = 'none';
                categoryBtn.setAttribute('aria-expanded', 'false');
            });
        });
    }

    // User Menu
    const userDropdown = document.querySelector('.infos-dropdown');
    const userMenu = document.querySelector('.infos-menu');

    if (userDropdown && userMenu) {
        userDropdown.addEventListener('click', () => {
            const isExpanded = userDropdown.getAttribute('aria-expanded') === 'true';
            userDropdown.setAttribute('aria-expanded', !isExpanded);
            userMenu.style.display = isExpanded ? 'none' : 'block';
        });

        // Close menu when clicking outside
        document.addEventListener('click', (e) => {
            if (!userDropdown.contains(e.target) && !userMenu.contains(e.target)) {
                userMenu.style.display = 'none';
                userDropdown.setAttribute('aria-expanded', 'false');
            }
        });
    }

    // Loading Overlay
    const loadingOverlay = document.getElementById('loading-overlay');
    
    function showLoading() {
        loadingOverlay.style.display = 'flex';
        loadingOverlay.setAttribute('aria-hidden', 'false');
    }
    
    function hideLoading() {
        loadingOverlay.style.display = 'none';
        loadingOverlay.setAttribute('aria-hidden', 'true');
    }

    // Add loading state to all forms
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', () => {
            showLoading();
        });
    });

    // Add loading state to all links that might trigger a page load
    document.querySelectorAll('a:not([target="_blank"])').forEach(link => {
        link.addEventListener('click', (e) => {
            if (!link.getAttribute('href').startsWith('#')) {
                showLoading();
            }
        });
    });

    // Handle browser back/forward
    window.addEventListener('pageshow', (e) => {
        if (e.persisted) {
            hideLoading();
        }
    });

    // Cart Count Update
    function updateCartCount() {
        const cartCount = document.querySelector('.cart-count');
        if (cartCount) {
            fetch('/api/cart/count/')
                .then(response => response.json())
                .then(data => {
                    cartCount.textContent = data.count;
                    cartCount.setAttribute('aria-label', `${data.count} itens no carrinho`);
                })
                .catch(error => console.error('Erro ao atualizar contador do carrinho:', error));
        }
    }

    // Update cart count every 30 seconds
    setInterval(updateCartCount, 30000);
    updateCartCount();

    // Keyboard Navigation
    document.addEventListener('keydown', (e) => {
        // Skip to main content
        if (e.key === 'Tab' && e.shiftKey) {
            const skipLink = document.querySelector('.skip-link');
            if (skipLink) {
                skipLink.focus();
            }
        }
    });

    // Notifications
    const notifications = document.querySelectorAll('.alert');
    notifications.forEach(notification => {
        // Auto-hide notifications after 5 seconds
        setTimeout(() => {
            notification.style.opacity = '0';
            setTimeout(() => {
                notification.remove();
            }, 300);
        }, 5000);
    });

    // Form Validation
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', (e) => {
            const requiredFields = form.querySelectorAll('[required]');
            let isValid = true;

            requiredFields.forEach(field => {
                if (!field.value.trim()) {
                    isValid = false;
                    field.classList.add('error');
                    
                    // Create error message if it doesn't exist
                    let errorMessage = field.nextElementSibling;
                    if (!errorMessage || !errorMessage.classList.contains('error-message')) {
                        errorMessage = document.createElement('div');
                        errorMessage.classList.add('error-message');
                        field.parentNode.insertBefore(errorMessage, field.nextSibling);
                    }
                    errorMessage.textContent = 'Este campo é obrigatório';
                } else {
                    field.classList.remove('error');
                    const errorMessage = field.nextElementSibling;
                    if (errorMessage && errorMessage.classList.contains('error-message')) {
                        errorMessage.remove();
                    }
                }
            });

            if (!isValid) {
                e.preventDefault();
            }
        });
    });

    // Smooth Scrolling
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

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

    // Não envia campos vazios no submit do searchForm
    var searchForm = document.getElementById('searchForm');
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