from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    
    def watchlist_listings(self):
        return [ x.listing for x in Watchlist.objects.filter(user=self) ]
        
class Auction_category(models.Model):
    id = models.AutoField(primary_key=True)
    category_name = models.CharField(max_length=25)
    
    def __str__(self):
        return self.category_name
    
class Listing(models.Model):
    id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=100, null=True)
    description = models.TextField(null=True)
    starting_bid = models.DecimalField(max_digits=7, decimal_places=2, null=True)
    image_URL = models.URLField(blank=True, null=True)
    
    category = models.ForeignKey(Auction_category,
                                 on_delete=models.CASCADE,
                                 blank=True,
                                 null=True,
                                 )
    
    # Link the listing to an owner Many-to-One relationship
    owner = models.ForeignKey(User, on_delete=models.CASCADE, default=None)
    active = models.BooleanField(default=True)

    def highest_bidder(self):
        try:
            return self.bid_set.latest('price').bidder
        except Bid.DoesNotExist:
            return 'No bidders yet'
        
    def __str__(self):
        return "{} | {}".format(self.title, self.category)
    
class Bid(models.Model):
    id = models.AutoField(primary_key=True)
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, default=None)
    price = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    bidder = models.ForeignKey(User, on_delete=models.CASCADE, default=None, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return "{} | {} | {}".format(self.listing.title, self.price, self.bidder)
    
class Comment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, null=True)
    comment = models.TextField(null=True)
    created = models.DateTimeField(auto_now_add=True, null=True)

    def __str__(self):
        return "{} | {} | {}".format(self.id, self.user, self.listing.title)

class Watchlist(models.Model):
    id = models.AutoField(primary_key=True)
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)