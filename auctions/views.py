from django.contrib.auth import authenticate, login, logout
from django.db import IntegrityError
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.contrib.auth.decorators import login_required

from .models import User, Listing, Bid
from .forms import NewListing, NewBid


def index(request):
    listings = Listing.objects.all()
    for entry in listings:
        entry.price = entry.bid_set.latest('created').price if entry.bid_set.exists() else entry.starting_bid
    return render(request, "auctions/index.html", {
        'listings': listings
    })


def login_view(request):
    if request.method == "POST":

        # Attempt to sign user in
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)

        # Check if authentication successful
        if user is not None:
            login(request, user)
            return HttpResponseRedirect(reverse("index"))
        else:
            return render(request, "auctions/login.html", {
                "message": "Invalid username and/or password."
            })
    else:
        return render(request, "auctions/login.html")


def logout_view(request):
    logout(request)
    return HttpResponseRedirect(reverse("index"))


def register(request):
    if request.method == "POST":
        username = request.POST["username"]
        email = request.POST["email"]

        # Ensure password matches confirmation
        password = request.POST["password"]
        confirmation = request.POST["confirmation"]
        if password != confirmation:
            return render(request, "auctions/register.html", {
                "message": "Passwords must match."
            })

        # Attempt to create new user
        try:
            user = User.objects.create_user(username, email, password)
            user.save()
        except IntegrityError:
            return render(request, "auctions/register.html", {
                "message": "Username already taken."
            })
        login(request, user)
        return HttpResponseRedirect(reverse("index"))
    else:
        return render(request, "auctions/register.html")

@login_required
def create_listing(request):
    if request.method == "POST":
        form = NewListing(request.POST)
        if form.is_valid():
            # Creates instance of the model associated with the form, but it doesn't save it to the database yet.
            # This is to modify before saving to database. In this case add owner id
            listing = form.save(commit=False)
            listing.owner = request.user
            listing.save()
            return HttpResponseRedirect(reverse("index"))
    else:
        form = NewListing()
    
    return render(request, "auctions/new-listing.html", {
        'form': form
    })
    
def show_listing(request, listing_id):
    listing = Listing.objects.get(id=listing_id)
    if listing.bid_set.all().exists():
        price = listing.bid_set.latest('created').price
    else:
        price = listing.starting_bid
    bids = listing.bid_set.all().count()
    initial_form_data = {'price': price}
    
    # Get new Bid
    if request.method == "POST":
        form = NewBid(request.POST, initial=initial_form_data)
        if form.is_valid():
            bid = form.save(commit=False)
            bid.listing = listing
            bid.owner = request.user
            bid.save()
            price = bid.price
            bids += 1
    else:
        
        form = NewBid(initial=initial_form_data)
        
    return render(request, "auctions/show-listing.html", {
        'listing': listing,
        'price': price,
        'bids': bids,
        'form': form
    })