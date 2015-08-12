# Python3 compatibility imports
from __future__ import division, print_function, unicode_literals, absolute_import

# Django imports
from django.shortcuts import render_to_response
from django.template import RequestContext

def home(request):
    '''
    Homepage for the DEC Sample Project.
    Demonstrates a full-width application home page.
    '''
    return render_to_response('dec_base/home.html',
        {'pagetitle':'Home page', 'head_title':'HOME'},
        context_instance=RequestContext(request))

def sidebar(request):
    '''
    Demonstrates a page with a sidebar.
    '''
    return render_to_response('dec_base/sidebar.html',
        {'pagetitle':'Sidebar page', 'head_title':'SIDEBAR'},
        context_instance=RequestContext(request))
