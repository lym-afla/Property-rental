from django.contrib.auth import authenticate, login, logout
from django.db import IntegrityError
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .models import User, Listing, Watchlist, Comment, Auction_category
from .forms import NewListing, NewBid, NewComment


def index(request):
    try:
        user_watchlist = request.user.watchlist_listings()
    except:
        user_watchlist = []
    
    if 'link' in request.GET and request.GET["link"]:
        link = request.GET["link"]
        if link == "Watchlist":
            listings = user_watchlist
        # else: if link is 'one of category' then listings are all listings in that category
        else:
            # check if link is a category name
            try:
                category = Auction_category.objects.get(category_name=link)
                listings = Listing.objects.filter(category=category)
            except Auction_category.DoesNotExist:
                listings = Listing.objects.all()
    else:
        listings = Listing.objects.all()
    
    for entry in listings:
        entry.price = entry.bid_set.latest('created').price if entry.bid_set.exists() else entry.starting_bid
    
    return render(request, "auctions/index.html", {
        'listings': listings,
        "user_watchlist": user_watchlist,
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
    
def show_listing(request, listing_id, form=None):
    listing = Listing.objects.get(id=listing_id)
    
    if listing.bid_set.all().exists():
        price = listing.bid_set.latest('created').price
    else:
        price = listing.starting_bid
    bids = listing.bid_set.all().count()
    
    if form is None:
        initial_form_data = {'price': price}
        form = NewBid(initial=initial_form_data)
    else:
        price = form.cleaned_data['price']
    
    if request.method == "POST":
        form = NewBid(request.POST, initial=initial_form_data)
        if listing.owner != request.user:
            if form.is_valid():
                bid = form.save(commit=False)
                bid.listing = listing
                bid.bidder = request.user
                bid.save()
                price = bid.price
                bids += 1
                form = NewBid(initial={'price': price})
                messages.success(request, "You bid has been accepted.")
        else:
            messages.error(request, "You cannot bid your own listing.")
            return HttpResponseRedirect(reverse("show_listing", args=(listing.id,)))    
    
    try:
        user_watchlist = request.user.watchlist_listings()
    except:
        user_watchlist = []
        
    highest_bidder = listing.highest_bidder()
    
    if listing.active == False and request.user == highest_bidder:
        messages.success(request, "You have won this auction.")
        
    try:
        comments = Comment.objects.filter(listing=listing).order_by('-created')
    except:
        comments = []
    
    return render(request, "auctions/show-listing.html", {
        'listing': listing,
        'price': price,
        'bids': bids,
        'form': form,
        'user_watchlist': user_watchlist,
        'highest_bidder': highest_bidder,
        'comments': comments
    })
    
@login_required
def edit_watchlist(request, listing_id):
    listing = Listing.objects.get(id=listing_id)
    if request.method == "POST":
        if request.POST.get('Add'):
            if listing.owner != request.user:
                if Watchlist.objects.filter(listing=listing, user=request.user).exists():
                    messages.error(request, "You already added this listing to your watchlist.")
                    return HttpResponseRedirect(reverse("show_listing", args=[listing.id]))
                watchlist = Watchlist(listing=listing, user=request.user)
                watchlist.save()
                return HttpResponseRedirect(reverse("show_listing", args=(listing.id,)))
            else:
                messages.error(request, "You cannot add your own listing to your watchlist.")
                return HttpResponseRedirect(reverse("show_listing", args=(listing.id,)))
        elif request.POST.get('Remove'):
            if listing.owner != request.user:
                if Watchlist.objects.filter(listing=listing, user=request.user).exists():
                    watchlist = Watchlist.objects.get(listing=listing, user=request.user)
                    watchlist.delete()
            return HttpResponseRedirect(reverse("show_listing", args=(listing.id,)))
        else:
            return HttpResponseRedirect(reverse("show_listing", args=(listing.id,)))
    else:
        print('Not POST')
        return HttpResponseRedirect(reverse("show_listing", args=(listing.id,)))
    
@login_required 
def close_listing(request, listing_id):
    if request.method == "POST":
        listing = Listing.objects.get(id=listing_id)
        if listing.owner == request.user:
            listing.active = False
            listing.save()
    return HttpResponseRedirect(reverse("show_listing", args=(listing.id,)))

@login_required
def add_comment(request, listing_id):
    listing = Listing.objects.get(id=listing_id)
    if request.method == "POST":
        form = NewComment(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.listing = listing
            comment.user = request.user
            comment.save()
            return HttpResponseRedirect(reverse("show_listing", args=(listing.id,)))
    else:
        form = NewComment()
    
    return render(request, "auctions/add-comment.html", {
        'listing': listing,
        'form': form
    })