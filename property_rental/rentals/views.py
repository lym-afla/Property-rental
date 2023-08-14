from django.shortcuts import render, redirect
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from .forms import CustomUserCreationForm

# @login_required
def index(request):
    
    if request.user.is_authenticated:
        months = ['J', 'F', 'M', 'A', 'M']
        rows = [
            {'name': 'Rent', 'cells': [{'color': 'green'}, {'color': 'green'}, {'color': 'green'}, {'color': 'red'}, {'color': 'red'}]},
            {'name': 'Tax', 'cells': [{'color': 'green'}, {'color': 'green'}, {'color': 'green'}, {'color': 'green'}, {'color': 'red'}]},
            {'name': 'Capex', 'cells': [{'color': 'green'}, {'color': 'green'}, {'color': 'green'}, {'color': 'green'}, {'color': 'green'}]},
            {'name': 'Management', 'cells': [{'color': 'green'}, {'color': 'green'}, {'color': 'red'}, {'color': 'red'}, {'color': 'red'}]},
            {'name': 'Electricity', 'cells': [{'color': 'green'}, {'color': 'green'}, {'color': 'green'}, {'color': 'red'}, {'color': 'red'}]},
            {'name': 'Utilities', 'cells': [{'color': 'green'}, {'color': 'green'}, {'color': 'green'}, {'color': 'red'}, {'color': 'red'}]},
            {'name': 'Internet', 'cells': [{'color': 'green'}, {'color': 'green'}, {'color': 'green'}, {'color': 'green'}, {'color': 'green'}]},
        ]
        return render(request, 'rentals/index.html', {
            'months': months,
            'rows': rows,
        })
    else:
        return redirect('rentals:login')
    
def register(request):
    
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('rentals:register')
    else:
        form = CustomUserCreationForm()
        
    return render(request, 'rentals/register.html', {'form': form})

def login_view(request):
    
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('rentals:index')
    else:
        form = AuthenticationForm()
        
    return render(request, 'rentals/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('rentals:login')