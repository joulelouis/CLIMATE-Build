"""
Common Template Filters for Climate Hazards Analysis

This module contains consolidated template filters shared across both
climate_hazards_analysis and climate_hazards_analysis_v2 modules.
"""

from django import template
import re

register = template.Library()


@register.filter(name="to_float")
def to_float(value, default_value=0.0):
    """
    Convert a value to float with comprehensive error handling.

    This is the consolidated version of the duplicate float filters from
    climate_hazards_analysis_v2/float_filters.py and
    climate_hazards_analysis_v2/templatetags/float_filters.py

    Args:
        value: Value to convert to float
        default_value (float): Default value if conversion fails

    Returns:
        float: Converted value or default_value
    """
    if value is None:
        return default_value

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        # Try direct conversion first
        try:
            return float(value)
        except (ValueError, TypeError):
            pass

        # Try to extract numeric value from string using regex
        match = re.search(r"-?\d+(?:\.\d+)?", value)
        if match:
            try:
                return float(match.group(0))
            except (ValueError, TypeError):
                pass

    return default_value


@register.filter(name="format_number")
def format_number(value, decimal_places=2):
    """
    Format a number with specified decimal places.

    Args:
        value: Number to format
        decimal_places (int): Number of decimal places

    Returns:
        str: Formatted number as string
    """
    try:
        if value is None or value == '':
            return 'N/A'

        num_value = float(value)
        if num_value == 0:
            return '0'

        format_str = f"{{:.{decimal_places}f}}"
        formatted = format_str.format(num_value)

        # Remove trailing zeros after decimal point
        if '.' in formatted:
            formatted = formatted.rstrip('0').rstrip('.')

        return formatted
    except (ValueError, TypeError):
        return str(value) if value is not None else 'N/A'


@register.filter(name="safe_percentage")
def safe_percentage(value, decimal_places=1):
    """
    Format a value as a percentage safely.

    Args:
        value: Value to format as percentage
        decimal_places (int): Number of decimal places

    Returns:
        str: Formatted percentage string
    """
    try:
        if value is None or value == '':
            return 'N/A'

        num_value = float(value)
        if num_value == 0:
            return '0%'

        format_str = f"{{:.{decimal_places}f}}%"
        formatted = format_str.format(num_value)

        # Remove trailing zeros after decimal point
        if '.' in formatted:
            formatted = formatted.rstrip('0').rstrip('.')

        return formatted
    except (ValueError, TypeError):
        return str(value) + '%' if value is not None else 'N/A'


@register.filter(name="get_item")
def get_item(dictionary, key, default=None):
    """
    Return the value for the given key in the dictionary.

    This consolidates the duplicate get_item filter from climate_hazards_analysis_v2.

    Args:
        dictionary (dict): Dictionary to get value from
        key: Key to look up
        default: Default value if key not found

    Returns:
        Value from dictionary or default
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key, default)
    return default


@register.filter(name="truncate_words")
def truncate_words(value, num_words=10, suffix="..."):
    """
    Truncate text to specified number of words.

    Args:
        value (str): Text to truncate
        num_words (int): Maximum number of words
        suffix (str): Suffix to add if truncated

    Returns:
        str: Truncated text
    """
    if not isinstance(value, str):
        return value

    words = value.split()
    if len(words) <= num_words:
        return value

    return ' '.join(words[:num_words]) + suffix


@register.filter(name="capitalize_words")
def capitalize_words(value):
    """
    Capitalize the first letter of each word in a string.

    Args:
        value (str): String to capitalize

    Returns:
        str: Capitalized string
    """
    if not isinstance(value, str):
        return value

    return ' '.join(word.capitalize() for word in value.split())