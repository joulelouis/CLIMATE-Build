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