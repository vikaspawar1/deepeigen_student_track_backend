"""
Custom form widgets for the Django administrative interface.

Provides enhanced widgets for foreign key fields, including inline 
'Add' buttons and popup handling for related models.
"""
from django.forms import widgets
from django import forms
from django.utils.safestring import mark_safe
from django.urls import reverse
from django.contrib.staticfiles import finders
from django.apps import apps


class ForeignKeyAddButtonWidget(widgets.Select):
    """
    A Select widget that appends a primary 'Add' button linked to the related model's admin add page.
    """
    def __init__(self, model, *args, **kwargs):
        self.model = model
        super(ForeignKeyAddButtonWidget, self).__init__(*args, **kwargs)

    def render(self, name, value, attrs=None, renderer=None):
        related_url = reverse(f'admin:{self.model._meta.app_label}_{self.model._meta.model_name}_add')
        output = super(ForeignKeyAddButtonWidget, self).render(name, value, attrs, renderer)
        add_button = f'<a href="{related_url}" class="btn btn-primary" target="_blank">Add</a>'
        return mark_safe(output + add_button)



class CustomAdminWidget(forms.Select):
    """
    A Select widget designed for the Django admin that includes a plus icon link 
    for adding related items via a popup window.
    """
    def __init__(self, rel, admin_site, *args, **kwargs):
        self.rel = rel
        self.admin_site = admin_site
        super().__init__(*args, **kwargs)

    def render(self, name, value, attrs=None, renderer=None):
        output = super().render(name, value, attrs, renderer)
       
        if isinstance(self.rel, str):
            # Get the model from the app registry
            try:
                model = apps.get_model(self.rel)
            except LookupError:
                raise ValueError(f"Model '{self.rel}' not found in the app registry.")
        else:
            model = self.rel
        app_label = model.app_label
        model_name = model.model
        print(type(self.rel),type(app_label), type(model_name))
        related_url = reverse('admin:%s_%s_add?to_field=id&popup=0'%(app_label,model_name))
        print('url-- ',related_url)
        icon_path=finders.find('admin/img/icon-addlink.svg')
        add_button = f'<a href="{related_url}" class="related-widget-wrapper-link add-related" ' \
                     f'onclick="showAddAnotherPopup(this);console.log(this);"> ' \
                     f'<img src="{icon_path}" ' \
                     f'width="10" height="10" alt="Add another"/></a>'
        return mark_safe(output + add_button)     