from django.contrib.auth import authenticate, login, logout
from django.db import IntegrityError
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django import forms

from .models import User


def index(request):
    return render(request, "auctions/index.html")


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

class NewListing(forms.Form):
    title = forms.CharField(
        label='Title',
        widget=forms.TextInput(attrs={'placeholder': 'Title for new listing'})
    )
    description = forms.CharField(
        label='Description',
        widget=forms.Textarea(attrs={'placeholder': 'Describe the new listing'})
    )
    starting_bid = forms.DecimalField(
        label='Starting bid',
        decimal_places=2
    )
    image_URL = forms.URLField(label='URL to listing image', required=False)
    CATEGORIES = (
        ('1', 'Fashion'),
        ('2', 'Toys'),
        ('3', 'Electronics'),
        ('4', 'Home')
    )
    category = forms.ChoiceField(choices=CATEGORIES)

def create_listing(request):
    if request.method("POST"):
        listing = NewListing(request.POST)
        if listing.is_valid():
            