from django import forms
from .models import Listing, Bid, Comment

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
        widgets = {
            'price': forms.NumberInput(attrs={'class': 'form-control', 'data-prefix': '$'})
        }
        
    def clean_price(self):
        cleaned_data = super().clean()
        price = cleaned_data['price']
        listing = self.initial.get('listing')
        latest_bid = Bid.objects.filter(listing=listing).latest('created') if listing.bid_set.exists() else None
        starting_bid = listing.starting_bid

        if latest_bid and price <= latest_bid.price:
            raise forms.ValidationError('Bid must be higher than the latest bid.')

        if not latest_bid and price < starting_bid:
            raise forms.ValidationError('Bid must be higher than or equal to the starting bid.')
                
        return price
    
class NewComment(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['comment']
        labels = {
            'comment': 'Comment'
        }
        widgets = {
            'comment': forms.Textarea(attrs={'class': 'form-control'})
        }