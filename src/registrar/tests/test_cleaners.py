from django.test import SimpleTestCase
from registrar.cleaners import clean_txt_content


class TestDnsCleaners(SimpleTestCase):

    def test_clean_txt_content(self):
        content = "  Take my white space away.    "
        expected_content = "Take my white space away."
        cleaned_content = clean_txt_content(content)

        self.assertEqual(expected_content, cleaned_content)
