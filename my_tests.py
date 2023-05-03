
# Making django app work
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'commerce.settings')

import django
django.setup()
# ----------------------

from auctions.models import Listing, Auction_category, User, Bid

# Create your tests here.
listing = Listing.objects.get(id=1)
# price = Bid.objects.filter(listing=listing)
# print(dir(listing.owner))
print(listing.owner.username, listing.owner.email, listing.owner.first_name, listing.owner.last_name)

# for i in listing.bid_set.all():
#     print(i.price, i.listing.id, i.id, i.bidder)

listing = Listing.objects.get(id=1)
# price = listing.bid_set.latest('created')
print(listing.bid_set.exists())
print(listing.bid_set.all().count())
