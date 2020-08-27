from django.shortcuts import render, redirect
from django.views.generic import ListView
from django.views.generic.base import TemplateView
from django.http import JsonResponse
from django.conf import settings
from .models import Category, Product
from .forms import CheckoutForm
from functools import wraps
import json
# Create your views here.


class GeneralContextMixin:
    """
    Recupera el contenido más común de la base de datos.
    compartido en muchos puntos de vista. Contiene solo métodos estáticos
    por lo que solo sirve como espacio de nombres para este grupo de métodos
    """

    @staticmethod
    def common_data(request, ctx=None):
        """
        Ojo: Devuelve datos comunes utilizados en muchas vistas:
        1) Árbol de categorías
        2) Carrito
        3) items_in_cart
        Si ctx se pasa como dict, agrega sus datos al
        devuelto resultado también.

        : solicitud de parámetro: pasado de Django
        : solicitud de tipo: WSGIRequest
        : param request: Dictamen opcional que se incluirá en el
                        la función devolvió el resultado.
        : type request: dict / NoneType por defecto
        """

        if ctx is None:
            ctx = {}
        ctx['categories'] = Category.objects.all()
        ctx["items_in_cart"] = 0
        if "cart" in request.session:
            ctx["cart"] = [
                item for key, item in request.session["cart"].items()
            ]
            cart_total = sum([
                int(item["quantity"]) * float(item["product_data"]["price"])
                for item in ctx["cart"]
            ])
            ctx["cart_total"] = cart_total
        else:
            ctx["cart"] = []
        ctx["items_in_cart"] = len(ctx["cart"])
        return ctx

    @staticmethod
    def validate_referrer(valid_referrers):
        """
        
        Decorador.
                Redirigir a la página de inicio si el
                la referencia de la solicitud no está en
                la lista de referencias válidas.
                Casos de uso:
                1) El usuario no debe ir a pagar
                si no proviene de la página del carrito.
                2) Debes visitar la página "gracias"
                solo después de salir del proceso de pago

                : param valid_referrers: la lista de referencias válidas
                : ingrese valid_referrers: list

        """
        def outer_wrapper(function):
            @wraps(function)
            def inner_wrapper(request, *args, **kwargs):
                referrer = str(request.META.get('HTTP_REFERER'))
                if all(r not in referrer for r in valid_referrers):
                    return redirect('home_view')
                return function(request, *args, **kwargs)
            return inner_wrapper
        return outer_wrapper

    @staticmethod
    def verify_cart_not_empty(function):
        """
        Decorator.
        If he cart is empty and the user tries to go
        to the cart or checkput page, redirects the user to the homepage.

        :param function: The decorated view
        :type function: function

        """
        @wraps(function)
        def inner_dec(request, *args, **kwargs):
            if "cart" not in request.session:
                return redirect('home_view')
            return function(request, *args, **kwargs)
        return inner_dec


class CategoryView(ListView):
    """
    Loads the products from a specific category
    """
    template_name = 'category.html'
    model = Category

    def get_context_data(self, **kwargs):
        """
        Prepara para pasar a la plantilla un contexto, que contiene:
        1) Los datos de la categoría actual
        2) Los productos pertenecientes a la categoría
        3) La cantidad estimada mostrada de cada producto basado
        en el historial de sesiones
        """

        ctx = super(__class__, self).get_context_data(**kwargs)
        ctx['category'] = Category.objects.get(id=self.kwargs["cat_id"])
        ctx['products'] = Product.objects.filter(
            category_id=self.kwargs["cat_id"]
        ).values()
        for product in ctx['products']:
            product_id = str(product["id"])
            session = self.request.session
            if ("cart" not in session or product_id not in session["cart"]):
                product["quantity"] = 1
            else:
                product["quantity"] = session["cart"][product_id]["quantity"]
        return GeneralContextMixin.common_data(self.request, ctx)


def home_view(request):
    return render(
        request,
        "home.html",
        GeneralContextMixin.common_data(request)
    )


@GeneralContextMixin.verify_cart_not_empty
def cart_view(request):
    return render(
        request,
        "cart.html",
        GeneralContextMixin.common_data(request)
    )


@GeneralContextMixin.validate_referrer(['/checkout/'])
def thank_you_view(request):
    """
    Vista de Gracias por la compra
    """
    return render(
        request,
        "thank-you.html",
        GeneralContextMixin.common_data(request)
    )


@GeneralContextMixin.verify_cart_not_empty
@GeneralContextMixin.validate_referrer(['/cart/', '/checkout/'])
def checkout_view(request):
    form = CheckoutForm()
    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            del request.session["cart"]
            request.session.save()
            return redirect("thank_you_view")
    ctx = {
        "form": form
    }
    return render(
        request,
        "checkout.html",
        GeneralContextMixin.common_data(request, ctx)
    )


class AJAXSessionCart(TemplateView):
    template_name = None

    def set_init_vars(self):
        """
        Assigns to the class the main
        varibales, later used in the JSON response
        """
        self.success = 1
        self.items_in_cart = 0
        self.err_msg = ""
        if "cart" not in self.request.session:
            self.request.session["cart"] = {}
        self.cart = self.request.session["cart"]

    def set_cart(self):
        """
        
        Elimina el carrito de la sesión si está vacío.
        Se asigna a la propiedad del carrito de objetos
        un dict vacío si el carrito está vacío
        o el carrito de la sesión si no está vacío.
        """
        if self.items_in_cart < 1:
            del self.request.session["cart"]
            self.request.session.save()
        try:
            self.cart = self.request.session["cart"]
        except KeyError:
            self.cart = {}

    def post(self, request):
        """
        Establece los valores de retorno predeterminados para la salida JSON.
        Validar los datos de entrada.
        Procese cada artículo guardándolo en el carrito de la sesión
        y llama a la función de retorno.
        """
        self.set_init_vars()
        for item in json.loads(request.POST["items"]):
            product_id = item["product_id"]
            quantity = item["quantity"]
            if not self.is_valid_ajax_input((product_id, quantity)):
                return self.return_error(settings.ERR_MSG_INVALID_PARAMS)
            int_quantity = int(quantity)
            if int_quantity > 0:
                product = Product.objects.filter(id=product_id)
                if not product:
                    return self.return_error(settings.ERR_MSG_NO_PRODUCT)
                else:
                    self.update_cart_with_product(
                        product_id,
                        quantity,
                        product
                    )
            else:
                self.delete_product_from_cart(product_id)
        self.request.session.save()
        self.items_in_cart = len(self.request.session["cart"])
        self.set_cart()
        return self.return_json()

    def return_error(self, error):
        """
        Finalmente devuelve JsonResponse
        con algún error AJAX.

        : param error: el mensaje de error
        : error de tipo: Str
        """

        self.success = 0
        self.err_msg = error
        return self.return_json()

    def delete_product_from_cart(self, product_id):
        """
        Elimina un producto del carrito.

        : param var: product_id
        : tipo var: str
        """
        try:
            del self.request.session["cart"][product_id]
        except KeyError:
            pass

    def update_cart_with_product(self, product_id, quantity, product):
        """
        Agregar / actualizar un producto en el carrito.

        : param product_id: el ID del producto
        : ingrese product_id: str
        : param cantidad: Cantidad
        : ingrese la cantidad: str
        : parámetro de producto: conjunto de consultas de producto filtrado
        : tipo de producto: QuerySet
        """
        product_data = {
                k: str(v) for k, v in
                product.values()[0].items()
            }
        self.request.session["cart"].update(
            {product_id: {
                "quantity": quantity,
                "product_data": product_data
                }
             }
        )

    def return_json(self):
        """
        Returns the JSON output to the front-end.
        """
        data = {
            'success': self.success,
            'err_msg': self.err_msg,
            'items_in_cart': self.items_in_cart,
            'cart': self.cart
        }
        return JsonResponse(data)

    def is_valid_ajax_input(self, fields):
        """
        Devuelve True si todos los campos
        son representaciones de cadena de números enteros,
        e.g. "4", "6"

        :param fields: A tuple with the fields
        :type fields: tuple
        """
        if any(isinstance(f, str) is not True for f in fields):
            return False
        if any(f.isdigit() is not True for f in fields):
            return False
        return True
