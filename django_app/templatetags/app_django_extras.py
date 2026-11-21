from django import template

register = template.Library()


@register.filter
def get_item(mapping, key):
    """{{ dict|get_item:key }} — dictionary lookup in templates."""
    if not mapping:
        return None
    return mapping.get(key)


@register.filter(name='cut_string')
def cut_string(value, arg: int):
    value = str(value or '')
    return value if len(value) <= int(arg) else f'{value[:int(arg)].rstrip()}…'


@register.filter
def rating_class(score):
    try:
        score = float(score)
    except (TypeError, ValueError):
        return 'none'
    return 'high' if score >= 7 else 'mid' if score >= 5 else 'low'


@register.simple_tag(takes_context=True)
def query_with(context, **kwargs):
    """Current query string with some parameters replaced (``None`` removes them)."""
    params = context['request'].GET.copy()
    for key, value in kwargs.items():
        params.pop(key, None)
        if value not in (None, ''):
            params[key] = value
    params.pop('page', None) if 'page' not in kwargs else None
    return params.urlencode()


@register.simple_tag(takes_context=True)
def query_without(context, key, value=None):
    """Remove one parameter (or one value of a multi-value parameter)."""
    params = context['request'].GET.copy()
    if value is None:
        params.pop(key, None)
    else:
        params.setlist(key, [v for v in params.getlist(key) if v != str(value)])
    params.pop('page', None)
    return params.urlencode()
