"""Custom views that allow for error view customization"""
from django.shortcuts import render

def custom_500_error_view(request, context=None):
    """Used to redirect 500 errors to a custom view"""
    if context is None:
        return render(request, "500.html", status=500)
    else:
        return render(request, "500.html", context=context, status=500)

def custom_401_error_view(request, context=None):
    """Used to redirect 401 errors to a custom view"""
    if context is None:
        return render(request, "401.html", status=401)
    else:
        return render(request, "401.html", context=context, status=401)
