from django.shortcuts import render
import markdown2
from django.urls import reverse
from django.http import HttpResponseRedirect, Http404
from django import forms
from django.utils.timezone import datetime
import random

from . import util


def index(request):
    return render(request, "encyclopedia/index.html", {
        "entries": util.list_entries()
    })

def entry(request, entry):
    if entry not in util.list_entries():
        raise Http404
    return render(request, "encyclopedia/entry.html", {
        "article": entry,
        "content": markdown2.markdown(util.get_entry(entry))
    })
    
def search(request):
    now = datetime.now()
    if request.GET:
        search_list = []
        articles = util.list_entries()
        for line in articles:
            if request.GET.get('q').lower() == line.lower():
                return render(request, "encyclopedia/entry.html", {
                    "article": line.lower(),
                    "content": markdown2.markdown(util.get_entry(line.lower()))
                })
            if request.GET.get('q').upper() in line.upper():
                search_list.append(line)
        return render(request, "encyclopedia/search.html", {
            "search": search_list
        })
    return HttpResponseRedirect(reverse("index"))

class NewEntry(forms.Form):
    title = forms.CharField(
        label="Title",
        widget=forms.TextInput(attrs={'placeholder': 'Title for new entry'})
        )
    content = forms.CharField(
        label="Content",
        widget=forms.Textarea(attrs={'placeholder': 'Content for new entry. Must be in markdown format'})
        )
    
    # Check for any data in both fields and title existing in titles
    def clean(self):
        cleaned_data = super().clean()
        title = cleaned_data.get('title')
        content = cleaned_data.get('content')
        if not title and not content:
            raise forms.ValidationError('You have to write something!')
        if title in util.list_entries():
            self.add_error('title', 'Please use unique title name')
            raise forms.ValidationError('Title already exists')
        
class EditEntry(NewEntry):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].widget = forms.HiddenInput()
    
    def clean(self):
        cleaned_data = super(NewEntry, self).clean()
        title = cleaned_data.get('title')
        content = cleaned_data.get('content')
        if not content:
            raise forms.ValidationError('You have to write something!')
        if title not in util.list_entries():
            raise forms.ValidationError('Title does not exist')

def add_page(request):
    # https://simpleisbetterthancomplex.com/article/2017/08/19/how-to-render-django-form-manually.html#accessing-the-form-fields-individually

    if request.method == 'POST':
        form = NewEntry(request.POST)
        if form.is_valid():
            util.save_entry(form.cleaned_data['title'],form.cleaned_data['content'])
            return HttpResponseRedirect(reverse("entry", args=[form.cleaned_data['title']]))
    else:
        form = NewEntry()    
    
    return render(request, "encyclopedia/add-entry.html", {
        "form": form
    })
    
def edit_page(request):
    if request.method == 'POST':
        form = EditEntry(request.POST)
        if form.is_valid():
            util.save_entry(form.cleaned_data['title'],form.cleaned_data['content'])
            return HttpResponseRedirect(reverse("entry", args=[form.cleaned_data['title']]))
    elif request.GET.get('e'):
        entry = request.GET['e']
        form = EditEntry(initial={'title': entry, 'content': util.get_entry(entry.lower())})
        # form.fields['title'].widget = forms.HiddenInput()
        return render(request, "encyclopedia/add-entry.html", {
            "form": form,
            "entry": entry
        })
    else:
        form = EditEntry()
    
    return render(request, "encyclopedia/add-entry.html", {
        "form": form
    })
    
def random_page(request):
    pages_list = util.list_entries()
    return HttpResponseRedirect(reverse("entry", args=[pages_list[random.randint(0, len(pages_list) - 1)]]))