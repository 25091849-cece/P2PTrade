from django.shortcuts import render


def index(request):
	"""Placeholder index view for the wallets app.

	Teams can replace this with their own UI. Keeping a simple view here
	registers the `wallets` namespace so templates can safely reverse
	`wallets:index`.
	"""
	return render(request, 'wallets/index.html')

