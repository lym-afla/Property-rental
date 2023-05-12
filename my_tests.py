
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

listing = Listing.objects.get(id=0)
# price = listing.bid_set.latest('created')
# print(listing.bid_set.exists())
# print(listing.bid_set.all().count())
# for x in listing.bid_set.all():
#     print(x.price)
# print(listing.bid_set.latest('created').price)

listings = Listing.objects.all()
for entry in listings:
    entry.price = entry.bid_set.latest('created').price if entry.bid_set.exists() else entry.starting_bid

for x in listings:
    try:
        # latest_bid = x.bid_set.latest('price')
        print(x.id, x.starting_bid, x.bid_set.latest('price').bidder)
    except Bid.DoesNotExist:
        print(x.id, x.starting_bid, 'No bids yet')
    
# u = User.objects.get(id=4)
# print(u, u.watchlist_listings())

# for x in u.watchlist_listings():
#     print(x)