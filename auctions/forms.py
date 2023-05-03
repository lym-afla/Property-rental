from django import forms
from .models import Listing, Auction_category, Bid
from django.core.exceptions import ValidationError

class NewListing(forms.ModelForm):
    
    # def __init__(self, *args, **kwargs):
    #     super().__init__(*args, **kwargs)
    #     self.fields['category'].choices = [('', '--------')] + [(cat.id, cat.category_name) for cat in Auction_category.objects.all()]

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
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Title for new listing'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Describe the new listing'}),
            'starting_bid': forms.NumberInput(attrs={'class': 'form-control', 'data-prefix': '$'}),
            'image_URL': forms.URLInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'})
        }
        
    def clean_starting_bid(self):
        starting_bid = self.cleaned_data['starting_bid']
        if starting_bid < 0:
            raise forms.ValidationError('Starting bid cannot be negative.')
        return starting_bid

class NewBid(forms.ModelForm):
    class Meta:
        model = Bid
        fields = ['price']
        labels = {
            'price': 'Enter Bid'
        }
        help_texts = {
            'price': 'Bid cannot be lower than the current listing price.'
        }
        widgets = {
            'price': forms.NumberInput(attrs={'class': 'form-control', 'data-prefix': '$'})
        }
        
    def clean_price(self):
        price = self.cleaned_data['price']

        if price < self.initial['price']:
            raise forms.ValidationError('Bid cannot be lower than the current listing price.')
                
        return price