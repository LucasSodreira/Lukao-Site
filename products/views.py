from django.shortcuts import render
from django.core.paginator import Paginator
from django.db.models import Q, Min, Max
from .models import Product

def category_view(request):
    products = Product.objects.all()
    categories = [c[0] for c in Product.CATEGORY_CHOICES]
    colors = [c[0] for c in Product.COLOR_CHOICES]
    sizes = [s[0] for s in Product.SIZE_CHOICES]
    dress_styles = [d[0] for d in Product.DRESS_STYLE_CHOICES]

    # Filtros GET
    category = request.GET.get('category')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    color = request.GET.getlist('color')
    size = request.GET.getlist('size')
    dress_style = request.GET.getlist('dress_style')

    filters = Q()
    if category and category in categories:
        filters &= Q(category=category)
    if min_price:
        try:
            min_price_val = float(min_price)
            filters &= Q(price__gte=min_price_val)
        except ValueError:
            pass
    if max_price:
        try:
            max_price_val = float(max_price)
            filters &= Q(price__lte=max_price_val)
        except ValueError:
            pass
    if min_price and max_price:
        try:
            if float(min_price) > float(max_price):
                min_price, max_price = None, None  # Ignora filtro inválido
        except ValueError:
            pass
    if color:
        filters &= Q(color__in=[c for c in color if c in colors])
    if size:
        filters &= Q(size__in=[s for s in size if s in sizes])
    if dress_style:
        filters &= Q(dress_style__in=[d for d in dress_style if d in dress_styles])

    filtered_products = products.filter(filters).order_by('-rating', 'price')

    # Paginação
    paginator = Paginator(filtered_products, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Para slider de preço
    price_range = products.aggregate(Min('price'), Max('price'))
    min_db_price = int(price_range['price__min'] or 50)
    max_db_price = int(price_range['price__max'] or 200)

    context = {
        'products': page_obj,
        'categories': Product.CATEGORY_CHOICES,
        'colors': Product.COLOR_CHOICES,
        'sizes': Product.SIZE_CHOICES,
        'dress_styles': Product.DRESS_STYLE_CHOICES,
        'selected': {
            'category': category,
            'min_price': min_price,
            'max_price': max_price,
            'color': color,
            'size': size,
            'dress_style': dress_style,
        },
        'min_db_price': min_db_price,
        'max_db_price': max_db_price,
        'total_products': filtered_products.count(),
        'paginator': paginator,
        'page_obj': page_obj,
    }
    return render(request, 'category_page.html', context)
