from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Return the value for the given key in the dictionary.

    DEPRECATED: This function is now available in climate_hazards_analysis.templatetags.common_filters
    Consider using the consolidated version instead.
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None


@register.filter
def replace(value, arg):
    """Replace all occurrences of a substring within a string.

    Usage: {{ value|replace:"old,new" }} or {{ value|replace:"old,new" }}
    """
    if isinstance(value, str) and isinstance(arg, str):
        # Handle comma-separated arguments: "old,new"
        if ',' in arg:
            old, new = arg.split(',', 1)
            return value.replace(old, new)
        else:
            return value
    return value