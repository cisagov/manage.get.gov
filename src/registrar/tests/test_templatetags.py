"""Test template tags."""

from django.conf import settings
from django.test import TestCase
from django.template import Context, Template
from registrar.templatetags.custom_filters import (
    extract_value,
    extract_a_text,
    find_index,
    slice_after,
    contains_checkbox,
)


class TestTemplateTags(TestCase):
    def _render_template(self, string, context=None):
        """Helper method to render a template given as a string.

        Originally from https://stackoverflow.com/a/1690879
        """
        context = context or {}
        context = Context(context)
        return Template(string).render(context)

    def test_public_site_url(self):
        result = self._render_template("{% load url_helpers %}{% public_site_url 'directory/page' %}")
        self.assertTrue(result.startswith(settings.GETGOV_PUBLIC_SITE_URL))
        self.assertTrue(result.endswith("/directory/page"))

    def test_public_site_url_leading_slash(self):
        result = self._render_template("{% load url_helpers %}{% public_site_url '/directory/page' %}")
        self.assertTrue(result.startswith(settings.GETGOV_PUBLIC_SITE_URL))
        # slash-slash host slash directory slash page
        self.assertEqual(result.count("/"), 4)


class CustomFiltersTestCase(TestCase):
    def test_extract_value_filter(self):
        html_input = '<input type="checkbox" name="_selected_action" value="123" id="label_123" class="action-select">'
        result = extract_value(html_input)
        self.assertEqual(result, "123")

        html_input = '<input type="checkbox" name="_selected_action" value="abc" id="label_123" class="action-select">'
        result = extract_value(html_input)
        self.assertEqual(result, "abc")

    def test_extract_a_text_filter(self):
        input_text = '<a href="#">Link Text</a>'
        result = extract_a_text(input_text)
        self.assertEqual(result, "Link Text")

        input_text = '<a href="/example">Another Link</a>'
        result = extract_a_text(input_text)
        self.assertEqual(result, "Another Link")

    def test_find_index(self):
        haystack = "Hello, World!"
        needle = "lo"
        result = find_index(haystack, needle)
        self.assertEqual(result, 3)

        needle = "XYZ"
        result = find_index(haystack, needle)
        self.assertEqual(result, -1)

    def test_slice_after(self):
        value = "Hello, World!"
        substring = "lo"
        result = slice_after(value, substring)
        self.assertEqual(result, ", World!")

        substring = "XYZ"
        result = slice_after(value, substring)
        self.assertEqual(result, value)  # Should return the original value if substring not found

    def test_contains_checkbox_with_checkbox(self):
        # Test the filter when HTML list contains a checkbox
        html_list = [
            '<input type="checkbox" name="_selected_action">',
            "<div>Some other HTML content</div>",
        ]
        result = contains_checkbox(html_list)
        self.assertTrue(result)  # Expecting True

    def test_contains_checkbox_without_checkbox(self):
        # Test the filter when HTML list does not contain a checkbox
        html_list = [
            "<div>Some HTML content without checkbox</div>",
            "<p>More HTML content</p>",
        ]
        result = contains_checkbox(html_list)
        self.assertFalse(result)  # Expecting False
