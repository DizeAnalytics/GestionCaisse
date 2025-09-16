from django import template

register = template.Library()

@register.filter
def sub(value, arg):
    """
    Subtracts the arg from the value.
    Usage: {{ value|sub:arg }}
    """
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return value

@register.filter
def multiply(value, arg):
    """
    Multiplies the value by the arg.
    Usage: {{ value|multiply:arg }}
    """
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return value

@register.filter(name='mul')
def mul(value, arg):
    """
    Alias convivial pour multiply.
    Usage: {{ value|mul:arg }}
    """
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return value

@register.filter
def div(value, arg):
    """
    Divise value par arg en gérant les cas bord.
    Usage: {{ value|div:arg }}
    """
    try:
        numerator = float(value)
        denominator = float(arg)
        if denominator == 0:
            return 0
        return numerator / denominator
    except (ValueError, TypeError):
        return value