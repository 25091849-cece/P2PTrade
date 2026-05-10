from django.shortcuts import render


def index(request):
	"""Placeholder index view for the marketplace app.

	Replace with real UI when the marketplace module is implemented.
	"""
	return render(request, 'marketplace/index.html')

