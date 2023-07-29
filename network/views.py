import json
from django.contrib.auth import authenticate, login, logout
from django.db import IntegrityError
from django.http import Http404, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.core import serializers
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from .models import User, Post, Comment

posts_load_limit = 10

def index(request):
    
    section = request.GET.get('section', 'all-posts')
    
    return render(request, "network/index.html", {'section': section})


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
            return render(request, "network/login.html", {
                "message": "Invalid username and/or password."
            })
    else:
        return render(request, "network/login.html")


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
            return render(request, "network/register.html", {
                "message": "Passwords must match."
            })

        # Attempt to create new user
        try:
            user = User.objects.create_user(username, email, password)
            user.save()
        except IntegrityError:
            return render(request, "network/register.html", {
                "message": "Username already taken."
            })
        login(request, user)
        return HttpResponseRedirect(reverse("index"))
    else:
        return render(request, "network/register.html")

@csrf_exempt
@login_required
def new_post(request):
    
    if request.method != 'POST':
        return JsonResponse({"error": "POST method required"}, status=400)
    
    content = json.loads(request.body).get('content')
    post = Post(
            user=request.user,
            content=content,
    )
    post.save()
    
    return JsonResponse({"message": "Post created successfully."}, status=201)

def user_profile(request, username):
    
    try:
        user = get_object_or_404(User, username=username)
        
        return render(request, 'network/profile.html', {
            'followers': user.followers.count(),
            'following': user.following.count(),
            'posts_count': user.posts.count(),
            'posts': user.posts.order_by("-timestamp")[:posts_load_limit],
            'user': request.user,
            'profile_user': user
        })
    except User.DoesNotExist:
        return Http404("User does not exist")
    
@login_required
def follow_user(request, username):
    
    if request.method != 'POST':
        return JsonResponse({"error": "POST request required."}, status=400)
    
    target_user = User.objects.get(username=username)

    if request.user == target_user:
        return JsonResponse({"error": "You cannot follow/unfollow yourself."}, status=400)

    if target_user in request.user.following.all():
        # If the user is already following, remove them from the following list
        request.user.following.remove(target_user)
        return JsonResponse({
            "message": "Unfollowed successfully.",
            "is_following": False,
            "followers_count": target_user.followers.count()
            })
    else:
        # If the user is not following, add them to the following list
        request.user.following.add(target_user)
        return JsonResponse({
            "message": "Followed successfully.",
            "is_following": True,
            "followers_count": target_user.followers.count()
            })
        
def get_posts(request, filter):
    
    if filter == 'all-posts':
        posts = Post.objects
    elif filter == 'following':
        if request.user.is_authenticated:
            posts = Post.objects.filter(user__in=request.user.following.all())
        else:
            return JsonResponse({"error": "User not logged in"})
    else:
        return JsonResponse({"error": "Invalid filter."}, status=400)

    posts = posts.order_by('-timestamp')
    
    # Pagination
    page = request.GET.get('page')
    paginator = Paginator(posts, posts_load_limit)
    try:
        posts = paginator.page(page)
    except PageNotAnInteger:
        posts = paginator.page(1)
    except EmptyPage:
        posts = paginator.page(paginator.num_pages)
    
    has_next_page = posts.has_next()
    has_previous_page = posts.has_previous()
    
    seriazlied_posts = [post.serialize() for post in posts]

    return JsonResponse({
        "posts": seriazlied_posts,
        "has_next_page": has_next_page,
        "has_previous_page": has_previous_page
        }, safe=False, status=200)