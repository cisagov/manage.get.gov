"""Test template tags."""

from django.conf import settings
from django.test import TestCase
from django.template import Context, Template


class TestTemplateTags(TestCase):
    def _render_template(self, string, context=None):
        """Helper method to render a template given as a string.

        Originally from https://stackoverflow.com/a/1690879
        """
        context = context or {}
        context = Context(context)
        return Template(string).render(context)

    def test_public_site_url(self):
        result = self._render_template(
            "{% load url_helpers %}{% public_site_url 'directory/page' %}"
        )
        self.assertTrue(result.startswith(settings.GETGOV_PUBLIC_SITE_URL))
        self.assertTrue(result.endswith("/directory/page"))

    def test_public_site_url_leading_slash(self):
        result = self._render_template(
            "{% load url_helpers %}{% public_site_url '/directory/page' %}"
        )
        self.assertTrue(result.startswith(settings.GETGOV_PUBLIC_SITE_URL))
        # slash-slash host slash directory slash page
        self.assertEqual(result.count("/"), 4)


class CustomFiltersTestCase(TestCase):
    def test_extract_value_filter(self):
        from registrar.templatetags.custom_filters import extract_value

        html_input = (
            '<input type="checkbox" name="_selected_action" value="123" '
            'id="label_123" class="action-select">'
        )
        result = extract_value(html_input)
        self.assertEqual(result, "123")

        html_input = (
            '<input type="checkbox" name="_selected_action" value="abc" '
            'id="label_123" class="action-select">'
        )
        result = extract_value(html_input)
        self.assertEqual(result, "abc")

    def test_extract_a_text_filter(self):
        from registrar.templatetags.custom_filters import extract_a_text

        input_text = '<a href="#">Link Text</a>'
        result = extract_a_text(input_text)
        self.assertEqual(result, "Link Text")

        input_text = '<a href="/example">Another Link</a>'
        result = extract_a_text(input_text)
        self.assertEqual(result, "Another Link")
