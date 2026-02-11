# -*- coding: utf-8 -*-
"""
Make debugging Django templates easier.
Example:
    {% load debugger_tags %}
    {{ object|ipdb }}

Copyright (c) 2007 Michael Trier

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

https://github.com/django-extensions/django-extensions/
"""

from django import template

register = template.Library()


@register.filter
def ipdb(obj):  # pragma: no cover
    """Interactive Python debugger filter."""
    __import__("ipdb").set_trace()
    return obj


@register.filter
def pdb(obj):
    """Python debugger filter."""
    __import__("pdb").set_trace()
    return obj


@register.filter
def wdb(obj):  # pragma: no cover
    """Web debugger filter."""
    __import__("wdb").set_trace()
    return obj
