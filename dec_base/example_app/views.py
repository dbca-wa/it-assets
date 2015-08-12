#Python3 compatibility
from __future__ import division, print_function, unicode_literals, absolute_import

from django.shortcuts import render_to_response
from django.template import RequestContext

def index_page(request):
    '''
    Index/home page for the example application.
    '''
    return render_to_response('example_app/index_page.html',
        {'pagetitle':'Index page'},
        context_instance=RequestContext(request))
