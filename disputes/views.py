from django.shortcuts import render


def index(request):
	"""Placeholder index view for disputes.

	This keeps the `disputes:index` namespace available while teammates
	develop the actual dispute management UI.
	"""
	return render(request, 'disputes/index.html')

