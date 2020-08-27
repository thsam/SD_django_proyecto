from django.contrib import admin
from .models import Category, Product
from mptt.admin import DraggableMPTTAdmin
from . import forms
from django.db.models import F
# Register your models here.


class CategoryDraggableMPTTAdmin(DraggableMPTTAdmin):
    """
    Applies the Django-MPTT draggable widget to the categories
    so that their levels can be viewed and changed with a single
    mouse move.
    """
    exclude = ('slug',)
    form = forms.CategoryForm


class ProductModelAdmin(admin.ModelAdmin):
    """
    Excluye el campo slug del formulario como debería ser
    generado automáticamente. Filtra las categorías de una manera
    que asegura que un producto se pueda poner solo en una hoja (abajo)
    nodo y no en una categoría que contenga subcategorías.
    """

    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
        """
        Filters the category queryset so that only leaf nodes are selected.
        """

        if db_field.name == "category":
            kwargs["queryset"] = Category.objects.filter(rght=F('lft') + 1)
        return super(__class__, self).formfield_for_foreignkey(
            db_field, request, **kwargs
        )


admin.site.register(Category, CategoryDraggableMPTTAdmin)
admin.site.register(Product, ProductModelAdmin)
