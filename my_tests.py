
# Making django app work
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'commerce.settings')

import django
django.setup()
# ----------------------

from auctions.models import Listing, Auction_category

# Create your tests here.
a = [c for c in Auction_category.objects.all()]
print(a)
