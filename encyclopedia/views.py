from django.shortcuts import render
import markdown2
from django.urls import reverse
from django.http import HttpResponseRedirect
from django import forms

from . import util


def index(request):
    return render(request, "encyclopedia/index.html", {
        "entries": util.list_entries()
    })

def entry(request, entry):
    return render(request, "encyclopedia/entry.html", {
        "article": entry,
        "content": markdown2.markdown(util.get_entry(entry))
    })
    
def search(request):
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
        widget=forms.Textarea(attrs={'placeholder': 'Content for new entry'})
        )
    
    def clean(self):
        cleaned_data = super(NewEntry, self).clean()
        title = cleaned_data.get('title')
        content = cleaned_data.get('content')
        if not title and not content:
            raise forms.ValidationError('You have to write something!')

def add_page(request):
    # https://simpleisbetterthancomplex.com/article/2017/08/19/how-to-render-django-form-manually.html#accessing-the-form-fields-individually

    if request.method == 'POST':
        form = NewEntry(request.POST)
        if form.is_valid():
            pass
    else:
        form = NewEntry()    
    
    return render(request, "encyclopedia/add-entry.html", {
        "form": form
    })