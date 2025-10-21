from django import forms
from .models import Asset


class AssetForm(forms.ModelForm):
    """
    Form for creating and updating asset information.
    Used in the polygon drawing workflow modal.
    """

    # Common archetype choices for assets
    ARCHETYPE_CHOICES = [
        ('', 'Select archetype...'),
        ('default archetype', 'Default Archetype'),
        ('commercial building', 'Commercial Building'),
        ('residential building', 'Residential Building'),
        ('industrial facility', 'Industrial Facility'),
        ('infrastructure', 'Infrastructure'),
        ('transportation', 'Transportation'),
        ('utility', 'Utility'),
        ('public service', 'Public Service'),
        ('agriculture', 'Agriculture'),
        ('natural resource', 'Natural Resource'),
        ('other', 'Other'),
    ]

    archetype = forms.ChoiceField(
        choices=ARCHETYPE_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'required': True
        })
    )

    class Meta:
        model = Asset
        fields = ['name', 'archetype']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter asset name',
                'required': True,
                'maxlength': 255
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Set field labels
        self.fields['name'].label = 'Asset Name'
        self.fields['archetype'].label = 'Asset Archetype'

        # Add required field indicators
        self.fields['name'].widget.attrs.update({'aria-required': 'true'})
        self.fields['archetype'].widget.attrs.update({'aria-required': 'true'})

    def clean_name(self):
        """Validate the asset name."""
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise forms.ValidationError('Asset name is required.')
        if len(name) < 2:
            raise forms.ValidationError('Asset name must be at least 2 characters long.')
        return name

    def clean_archetype(self):
        """Validate the asset archetype."""
        archetype = self.cleaned_data.get('archetype', '').strip()
        if not archetype:
            raise forms.ValidationError('Please select an asset archetype.')
        return archetype or 'default archetype'