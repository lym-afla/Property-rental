from django.contrib import admin
from .models import User, Listing, Bid, Comment, Auction_category

# Register your models here.
admin.site.register(User)
admin.site.register(Listing)
admin.site.register(Bid)
admin.site.register(Comment)
# admin.site.register(Auction_category)