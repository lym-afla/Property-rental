from django.contrib.auth.models import AbstractUser
from django.db import models
from django.dispatch import receiver
from django.db.models.signals import post_save


class User(AbstractUser):
    
    def watchlist_listings(self):
        return [ x.listing for x in Watchlist.objects.filter(user=self) ]

class Auction_category(models.Model):
    id = models.AutoField(primary_key=True)
    category_name = models.CharField(max_length=25)

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
                                 choices=((c.id, c.category_name) for c in Auction_category.objects.all())
                                 )
    
    # Link the listing to an owner Many-to-One relationship
    owner = models.ForeignKey(User, on_delete=models.CASCADE, default=None)


class Bid(models.Model):
    id = models.AutoField(primary_key=True)
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, default=None)
    price = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    bidder = models.ForeignKey(User, on_delete=models.CASCADE, default=None, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    
# This function will be called when a new listing is created. Create a new bid for the new listing
# @receiver(post_save, sender=Listing)
# def create_bid(sender, instance, created, **kwargs):
#     if created:
#         bid = Bid.objects.create(listing=instance, price=instance.starting_bid, bidder=instance.owner)
#         bid.save()

# TODO
class Comment(models.Model):
    # comment_id = models.IntegerField(primary_key=True, default=0)
    pass


class Watchlist(models.Model):
    id = models.AutoField(primary_key=True)
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)