from django import forms
from .models import Listing

class NewListing(forms.ModelForm):
    class Meta:
        model = Listing
        fields = ['title',
                  'description',
                  'starting_bid',
                  'image_URL',
                  'category'
                  ]
        labels = {
            'title': 'Title',
            'description': 'Description',
            'starting_bid': 'Starting bid',
            'image_URL': 'URL to listing image',
        }
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Title for new listing'}),
            'description': forms.Textarea(attrs={'placeholder': 'Describe the new listing'})
        }
