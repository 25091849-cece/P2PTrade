from django import template
from django.urls import reverse, NoReverseMatch

register = template.Library()


@register.simple_tag
def url_or_placeholder(name, *args, **kwargs):
    """Return a reversed URL for "name" or '#' if the name is not resolvable.

    Usage in templates:
        {% load url_utils %}
        <a href="{% url_or_placeholder 'wallets:index' %}">Wallet</a>
    This prevents NoReverseMatch when an app's URLconf isn't yet included.
    """
    try:
        return reverse(name, args=args, kwargs=kwargs)
    except NoReverseMatch:
        return '#'

