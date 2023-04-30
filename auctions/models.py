from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    pass

class Auction_category(models.Model):
    category_id = models.IntegerField(primary_key=True, default=0)
    category_name = models.CharField(max_length=25)

class Listing(models.Model):
    listing_id = models.IntegerField(primary_key=True)
    title = models.CharField(max_length=100, null=True)
    description = models.TextField(null=True)
    starting_bid = models.DecimalField(max_digits=7, decimal_places=2, null=True)
    image_URL = models.URLField(blank=True, null=True)
    
    category = models.IntegerField(max_length=50, blank=True, choices=((c.category_id, c.category_name) for c in Auction_category.objects.all()))
    
    # Link the listing to an owner Many-to-One relationship
    owner = models.ForeignKey(User, on_delete=models.CASCADE, default='')

# TODO
class Bid(models.Model):
    # bid_id = models.IntegerField(primary_key=True, default=0.00)
    pass

# TODO
class Comment(models.Model):
    # comment_id = models.IntegerField(primary_key=True, default=0)
    pass

