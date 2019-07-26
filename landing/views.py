from django.shortcuts import render, render_to_response
from django.views.generic import TemplateView


class LandingIndexView(TemplateView):
    template_name = 'landing/index.html'