from django.test import TestCase
from registrar.models import User, FederalAgency
from registrar.management.commands.utility.fuzzy_string_matcher import (
    create_federal_agency_matcher,
    create_basic_string_matcher,
    MatchResult,
    FederalAgencyVariantGenerator,
    GenericFuzzyMatcher,
    MatchingStrategy,
)
from rapidfuzz import fuzz


class TestFuzzyStringMatcher(TestCase):

    def setUp(self):
        self.user = User.objects.create(username="testuser")
        self.federal_agency = FederalAgency.objects.create(agency="Test Federal Agency")

    def tearDown(self):
        FederalAgency.objects.all().delete()
        User.objects.all().delete()

    def test_federal_agency_matcher_creation(self):
        """Test creating a federal agency matcher with different thresholds"""
        matcher = create_federal_agency_matcher(threshold=85)

        self.assertIsInstance(matcher, GenericFuzzyMatcher)
        self.assertIsInstance(matcher.variant_generator, FederalAgencyVariantGenerator)
        self.assertEqual(matcher.global_threshold, 85)

    def test_basic_string_matcher_creation(self):
        """Test creating a basic string matcher without variants"""
        matcher = create_basic_string_matcher(threshold=75)

        self.assertIsInstance(matcher, GenericFuzzyMatcher)
        self.assertIsNone(matcher.variant_generator)
        self.assertEqual(matcher.global_threshold, 75)

    def test_federal_agency_exact_match(self):
        """Test exact matching for federal agencies"""
        matcher = create_federal_agency_matcher(threshold=85)

        candidates = [
            "Department of Defense",
            "Department of Agriculture",
            "Federal Bureau of Investigation",
            "Central Intelligence Agency",
        ]

        result = matcher.find_matches("Department of Defense", candidates)

        self.assertIsInstance(result, MatchResult)
        self.assertIn("Department of Defense", result.matched_strings)
        self.assertGreater(len(result.matched_strings), 0)

    def test_federal_agency_abbreviation_matching(self):
        """Test that federal agency abbreviations are matched correctly"""
        matcher = create_federal_agency_matcher(threshold=80)

        candidates = ["Department of Defense", "Dept of Defense", "DoD", "Department of Agriculture"]

        # Should match both full name and abbreviations
        result = matcher.find_matches("Department of Defense", candidates)

        # Should find multiple matches due to variant generation
        self.assertGreater(len(result.matched_strings), 1)
        self.assertIn("Department of Defense", result.matched_strings)

    def test_federal_agency_us_prefix_variants(self):
        """Test U.S. prefix variant generation"""
        generator = FederalAgencyVariantGenerator()

        variants = generator.generate_variants("U.S. Department of Defense")

        # Should include variants without U.S. prefix
        variant_strings = [v.lower() for v in variants]
        self.assertTrue(any("department of defense" in v for v in variant_strings))
        self.assertTrue(any("us department of defense" in v for v in variant_strings))

    def test_match_result_functionality(self):
        """Test MatchResult class functionality"""
        matcher = create_federal_agency_matcher(threshold=80)

        candidates = ["Department of Defense", "Dept of Defense", "Defense Department", "Department of Agriculture"]

        result = matcher.find_matches("Department of Defense", candidates, report_details=True)

        # Test MatchResult methods
        self.assertIsInstance(result.matched_strings, set)
        self.assertIsInstance(result.match_details, list)
        self.assertIsInstance(result.variants_used, set)

        # Test get_best_matches
        best_matches = result.get_best_matches(limit=2)
        self.assertLessEqual(len(best_matches), 2)

        # Each match detail should be a 3-tuple
        for match_string, score, strategy_name in result.match_details:
            self.assertIsInstance(match_string, str)
            self.assertIsInstance(score, (int, float))
            self.assertIsInstance(strategy_name, str)

    def test_find_best_match(self):
        """Test finding the single best match"""
        matcher = create_federal_agency_matcher(threshold=80)

        candidates = ["Department of Defense", "Department of Agriculture", "Dept of Defense"]

        best_match = matcher.find_best_match("Department of Defense", candidates)

        self.assertIsNotNone(best_match)
        match_string, score = best_match
        self.assertEqual(match_string, "Department of Defense")
        self.assertGreater(score, 95)  # Should be very high for exact match

    def test_batch_matching(self):
        """Test batch processing of multiple targets"""
        matcher = create_federal_agency_matcher(threshold=80)

        targets = ["Department of Defense", "FBI", "CIA"]
        candidates = [
            "Department of Defense",
            "Federal Bureau of Investigation",
            "Central Intelligence Agency",
            "Department of Agriculture",
        ]

        results = matcher.batch_find_matches(targets, candidates)

        self.assertEqual(len(results), 3)
        for target in targets:
            self.assertIn(target, results)
            self.assertIsInstance(results[target], MatchResult)

    def test_no_matches_scenario(self):
        """Test behavior when no matches are found"""
        matcher = create_federal_agency_matcher(threshold=95)  # Very high threshold

        candidates = ["Completely Different Agency"]

        result = matcher.find_matches("Department of Defense", candidates)

        self.assertEqual(len(result.matched_strings), 0)
        self.assertEqual(len(result.match_details), 0)

    def test_matching_with_variants_disabled(self):
        """Test matching with variant generation disabled"""
        matcher = create_federal_agency_matcher(threshold=85)

        candidates = ["Department of Defense", "Dept of Defense"]

        # With variants disabled, should only match exact or very similar strings
        result = matcher.find_matches("DoD", candidates, include_variants=False)

        # Might not find matches since variants are disabled
        self.assertIsInstance(result, MatchResult)

    def test_custom_matching_strategies(self):
        """Test creating matcher with custom strategies"""
        custom_strategies = [
            MatchingStrategy(fuzz.ratio, 90, "exact_ratio"),
            MatchingStrategy(fuzz.partial_ratio, 85, "partial_ratio"),
        ]

        matcher = GenericFuzzyMatcher(
            strategies=custom_strategies, variant_generator=FederalAgencyVariantGenerator(), global_threshold=80
        )

        candidates = ["Department of Defense", "Dept of Defense"]
        result = matcher.find_matches("Department of Defense", candidates, report_details=True)

        # Check that our custom strategies were used
        strategy_names = [detail[2] for detail in result.match_details]
        self.assertTrue(any("exact_ratio" in name for name in strategy_names))

    def test_rapidfuzz_integration(self):
        """Test that rapidfuzz integration works correctly (this was the original bug)"""
        from rapidfuzz import process, fuzz

        query = "Test Federal Agency"
        choices = ["Test Federal Agency", "Another Agency", "Test Federal Agency Subunit"]

        # This should return 3-tuples and not cause ValueError
        matches = process.extract(query, choices, scorer=fuzz.token_sort_ratio, score_cutoff=85, limit=None)

        # Verify the format
        self.assertIsInstance(matches, list)
        if matches:
            first_match = matches[0]
            self.assertEqual(len(first_match), 3)

            # Should be able to unpack as 3-tuple
            match_string, score, index = first_match
            self.assertIsInstance(match_string, str)
            self.assertIsInstance(score, (int, float))
            self.assertIsInstance(index, int)

    def test_create_federal_portfolio_integration(self):
        """Test the exact scenario used in create_federal_portfolio command"""
        matcher = create_federal_agency_matcher(threshold=85)

        # Simulate real data from create_federal_portfolio
        target_agency_name = "Test Federal Agency"
        all_org_names = ["Test Federal Agency", "Testorg", "Test Federal Agency Division", "Another Organization"]

        result = matcher.find_matches(target_agency_name, all_org_names)

        self.assertIsInstance(result, MatchResult)
        self.assertIn("Test Federal Agency", result.matched_strings)
        self.assertGreater(len(result.matched_strings), 0)

    def test_empty_input_handling(self):
        """Test handling of empty inputs"""
        matcher = create_federal_agency_matcher(threshold=85)

        # Empty candidates list
        result = matcher.find_matches("Test Agency", [])
        self.assertEqual(len(result.matched_strings), 0)

        # Empty target string
        result = matcher.find_matches("", ["Test Agency"])
        self.assertIsInstance(result, MatchResult)

    def test_special_characters_handling(self):
        """Test handling of special characters and punctuation"""
        matcher = create_federal_agency_matcher(threshold=80)

        candidates = ["U.S. Department of Defense", "Department of Veterans Affairs", "Health & Human Services"]

        # Should handle punctuation variants
        result = matcher.find_matches("US Department of Defense", candidates)
        self.assertGreater(len(result.matched_strings), 0)
