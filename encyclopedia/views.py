from django.shortcuts import render
import markdown2
from django.urls import reverse
from django.http import HttpResponseRedirect

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
    print(request.GET)
    if request.GET:
        search_list = []
        articles = util.list_entries()
        for line in articles:
            if request.GET.get('q') in line:
                search_list.append(line)
        return render(request, "encyclopedia/search.html", {
            "search": search_list
        })
    return HttpResponseRedirect(reverse("index"))