"""
Generic fuzzy string matching utility for any string comparison needs

This util provides fuzzy string matching. It handles common variations
in naming conventions, such as:
- Abbreviations (e.g. "Department of" vs "Dept of")
- Punctuation (e.g. "U.S." vs "US")
- Word order (e.g. "John Smith" vs "Smith, John")
- Case insensitivity
- Common misspellings and typos
- Variants for person names and federal agency names
It can be configured with different matching strategies and thresholds
to suit specific use cases, and supports detailed match reporting.
It also supports batch processing of multiple target strings against a pool of candidates.
This utility is designed to be flexible and extensible for various fuzzy matching needs.
"""

import logging
from typing import Set, List, Dict, Optional, Callable, Tuple
from dataclasses import dataclass, field

from rapidfuzz import fuzz, process
from registrar.models.utility.generic_helper import normalize_string

logger = logging.getLogger(__name__)


@dataclass
class MatchingStrategy:
    """Configuration for a single fuzzy matching strategy."""

    scorer: Callable
    threshold: int
    name: str
    weight: float = 1.0  # For weighted scoring if needed


@dataclass
class MatchResult:
    """Result of a fuzzy matching operation."""

    matched_strings: Set[str]
    match_details: List[Tuple[str, float, str]] = field(default_factory=list)
    variants_used: Set[str] = field(default_factory=set)

    def get_best_matches(self, limit: int = 10) -> List[Tuple[str, float, str]]:
        """Get the top N matches sorted by score."""
        return sorted(self.match_details, key=lambda x: x[1], reverse=True)[:limit]


class StringVariantGenerator:
    """Base class for generating string variants."""

    def generate_variants(self, input_string: str) -> Set[str]:
        """Generate variants of the input string."""
        raise NotImplementedError("Subclasses must implement generate_variants")


class FederalAgencyVariantGenerator(StringVariantGenerator):
    """Generates variants specific to federal agency names."""

    # Common abbreviation mappings for federal agencies
    ABBREVIATION_MAPPINGS = [
        ("Department of", "Dept of", "Dept. of"),
        ("Administration", "Admin"),
        ("Agency", "Agcy"),
        ("United States", "US", "U.S."),
        ("Federal", "Fed"),
        ("National", "Nat'l", "Natl"),
    ]

    def generate_variants(self, agency_name: str) -> Set[str]:
        """Generate federal agency name variants."""
        variants = {normalize_string(agency_name)}

        variants.update(self._get_us_prefix_variants(agency_name))
        variants.update(self._get_the_prefix_variants(agency_name))
        variants.update(self._get_abbreviation_variants(agency_name))
        variants.update(self._get_punctuation_variants(agency_name))

        return variants

    def _get_us_prefix_variants(self, agency_name: str) -> Set[str]:
        """Generate U.S./US prefix variations."""
        variants = set()

        if agency_name.startswith("U.S. "):
            variants.add(normalize_string(agency_name[4:]))
            variants.add(normalize_string("US " + agency_name[4:]))
            variants.add(normalize_string("United States " + agency_name[4:]))
        elif agency_name.startswith("US "):
            variants.add(normalize_string(agency_name[3:]))
            variants.add(normalize_string("U.S. " + agency_name[3:]))
            variants.add(normalize_string("United States " + agency_name[3:]))
        elif agency_name.startswith("United States "):
            variants.add(normalize_string(agency_name[14:]))
            variants.add(normalize_string("U.S. " + agency_name[14:]))
            variants.add(normalize_string("US " + agency_name[14:]))
        else:
            variants.add(normalize_string("U.S. " + agency_name))
            variants.add(normalize_string("US " + agency_name))
            variants.add(normalize_string("United States " + agency_name))

        return variants

    def _get_the_prefix_variants(self, agency_name: str) -> Set[str]:
        """Generate 'The' prefix variations."""
        variants = set()

        if agency_name.startswith("The "):
            variants.add(normalize_string(agency_name[4:]))
        else:
            variants.add(normalize_string("The " + agency_name))

        return variants

    def _get_abbreviation_variants(self, agency_name: str) -> Set[str]:
        """Generate common abbreviation variants."""
        variants = set()

        for full_form, *abbreviations in self.ABBREVIATION_MAPPINGS:
            if full_form in agency_name:
                for abbrev in abbreviations:
                    variants.add(normalize_string(agency_name.replace(full_form, abbrev)))
            else:
                # Try reverse mapping (abbrev -> full form)
                for abbrev in abbreviations:
                    if abbrev in agency_name:
                        variants.add(normalize_string(agency_name.replace(abbrev, full_form)))

        return variants

    def _get_punctuation_variants(self, agency_name: str) -> Set[str]:
        """Generate punctuation variations."""
        variants = set()

        # Remove all punctuation
        no_punct = normalize_string(agency_name.replace(".", "").replace(",", "").replace("-", " "))
        variants.add(no_punct)

        # Common punctuation replacements
        variants.add(normalize_string(agency_name.replace("&", "and")))
        variants.add(normalize_string(agency_name.replace(" and ", " & ")))

        return variants

class GenericFuzzyMatcher:
    """
    Generic fuzzy string matcher that can be configured for different use cases.

    This class provides flexible fuzzy matching with:
    - Configurable matching strategies
    - Pluggable variant generators
    - Detailed match reporting
    - Threshold customization per strategy
    """

    # Default matching strategies
    DEFAULT_STRATEGIES = [
        MatchingStrategy(fuzz.token_sort_ratio, 85, "token_sort"),
        MatchingStrategy(fuzz.token_set_ratio, 85, "token_set"),
        MatchingStrategy(fuzz.partial_ratio, 90, "partial"),
        MatchingStrategy(fuzz.ratio, 90, "exact"),
    ]

    def __init__(
        self,
        strategies: Optional[List[MatchingStrategy]] = None,
        variant_generator: Optional[StringVariantGenerator] = None,
        global_threshold: int = 85,
    ):
        """
        Initialize the generic fuzzy matcher.

        Args:
            strategies: List of matching strategies to use
            variant_generator: Generator for string variants
            global_threshold: Default threshold for strategies that don't specify one
        """
        self.strategies = strategies or self.DEFAULT_STRATEGIES
        self.variant_generator = variant_generator
        self.global_threshold = global_threshold

    def find_matches(
        self,
        target_string: str,
        candidate_strings: List[str],
        include_variants: bool = True,
        report_details: bool = False,
    ) -> MatchResult:
        """
        Find strings that closely match the target string.

        Args:
            target_string: The string to match against
            candidate_strings: List of strings to search through
            include_variants: Whether to include generated variants in matching
            report_details: Whether to include detailed match information

        Returns:
            MatchResult containing matched strings and optional details
        """
        if not target_string or not candidate_strings:
            return MatchResult(matched_strings=set())

        target_variants, variants_used = self._prepare_target_variants(target_string, include_variants)

        matched_strings: Set[str] = set()
        all_match_details: List[Tuple[str, float, str]] = []

        # Exact string matching
        self._perform_exact_matching(
            target_variants, candidate_strings, matched_strings, all_match_details, report_details
        )

        # Fuzzy matching
        self._perform_fuzzy_matching(
            target_variants, candidate_strings, matched_strings, all_match_details, report_details
        )

        return MatchResult(
            matched_strings=matched_strings,
            match_details=all_match_details if report_details else [],
            variants_used=variants_used,
        )

    def _prepare_target_variants(self, target_string: str, include_variants: bool) -> Tuple[Set[str], Set[str]]:
        """Prepare target string variants for matching."""
        normalized_target = normalize_string(target_string)
        target_variants = {normalized_target}
        variants_used = {normalized_target}

        if include_variants and self.variant_generator:
            generated_variants = self.variant_generator.generate_variants(target_string)
            target_variants.update(generated_variants)
            variants_used = target_variants.copy()

        return target_variants, variants_used

    def _perform_exact_matching(
        self,
        target_variants: Set[str],
        candidate_strings: List[str],
        matched_strings: Set[str],
        all_match_details: List[Tuple[str, float, str]],
        report_details: bool,
    ) -> None:
        """Perform exact string matching against target variants."""
        normalized_candidates = [normalize_string(candidate) for candidate in candidate_strings]

        for i, normalized_candidate in enumerate(normalized_candidates):
            if normalized_candidate in target_variants:
                matched_strings.add(candidate_strings[i])
                if report_details:
                    all_match_details.append((candidate_strings[i], 100.0, "exact_string_match"))

    def _perform_fuzzy_matching(
        self,
        target_variants: Set[str],
        candidate_strings: List[str],
        matched_strings: Set[str],
        all_match_details: List[Tuple[str, float, str]],
        report_details: bool,
    ) -> None:
        """Perform fuzzy matching using configured strategies."""
        for target_variant in target_variants:
            for strategy in self.strategies:
                self._apply_matching_strategy(
                    target_variant, candidate_strings, strategy, matched_strings, all_match_details, report_details
                )

    def _apply_matching_strategy(
        self,
        target_variant: str,
        candidate_strings: List[str],
        strategy: MatchingStrategy,
        matched_strings: Set[str],
        all_match_details: List[Tuple[str, float, str]],
        report_details: bool,
    ) -> None:
        """Apply a single matching strategy to find matches."""
        try:
            threshold = getattr(strategy, "threshold", self.global_threshold)
            matches = process.extract(
                target_variant,
                candidate_strings,
                scorer=strategy.scorer,
                score_cutoff=threshold,
                limit=None,
            )

            for match_string, score, _ in matches:
                # Only add if not already found by exact matching
                if match_string not in matched_strings:
                    matched_strings.add(match_string)

                if report_details:
                    self._add_match_detail(all_match_details, match_string, score, strategy.name)

        except Exception as e:
            logger.warning(f"Error in fuzzy matching with strategy {strategy.name}: {e}")

    def _add_match_detail(
        self,
        all_match_details: List[Tuple[str, float, str]],
        match_string: str,
        score: float,
        strategy_name: str,
    ) -> None:
        """Add match detail if it doesn't already exist."""
        existing_detail = next(
            (detail for detail in all_match_details if detail[0] == match_string and detail[2] == strategy_name),
            None,
        )
        if not existing_detail:
            all_match_details.append((match_string, score, strategy_name))

    def find_best_match(
        self, target_string: str, candidate_strings: List[str], include_variants: bool = True
    ) -> Optional[Tuple[str, float]]:
        """
        Find the single best match for the target string.

        Returns:
            Tuple of (best_match_string, score) or None if no matches found
        """
        result = self.find_matches(target_string, candidate_strings, include_variants, report_details=True)

        if not result.match_details:
            return None

        best_match = max(result.match_details, key=lambda x: x[1])
        return (best_match[0], best_match[1])

    def batch_find_matches(
        self, target_strings: List[str], candidate_strings: List[str], include_variants: bool = True
    ) -> Dict[str, MatchResult]:
        """
        Find matches for multiple target strings efficiently.

        Returns:
            Dictionary mapping each target string to its MatchResult
        """
        results = {}
        for target in target_strings:
            results[target] = self.find_matches(target, candidate_strings, include_variants, report_details=True)
        return results


class FuzzyMatchingTestRunner:
    """Utility for testing and reporting fuzzy matching results."""

    def __init__(self, matcher: GenericFuzzyMatcher):
        self.matcher = matcher

    def generate_test_report(
        self, target_strings: List[str], candidate_strings: List[str], max_display: int = 10
    ) -> str:
        """
        Generate a comprehensive test report for fuzzy matching.

        Args:
            target_strings: Strings to match against
            candidate_strings: Pool of candidates to search
            max_display: Maximum matches to display per target

        Returns:
            Formatted report string
        """
        report_lines = []
        report_lines.append("=" * 70)
        report_lines.append("               FUZZY MATCHING TEST REPORT")
        report_lines.append("=" * 70)

        for target in target_strings:
            result = self.matcher.find_matches(target, candidate_strings, include_variants=True, report_details=True)

            report_lines.append(f"\nTarget: '{target}'")
            report_lines.append("-" * 50)

            if result.variants_used:
                report_lines.append(f"Variants tested: {len(result.variants_used)}")
                sample_variants = list(result.variants_used)[:5]
                report_lines.append(f"Sample variants: {sample_variants}")

            best_matches = result.get_best_matches(max_display)
            report_lines.append(f"\nTop matches found: {len(best_matches)}")

            for match_string, score, strategy in best_matches:
                report_lines.append(f"  • {match_string} (score: {score:.1f}, strategy: {strategy})")

            if len(result.matched_strings) > max_display:
                remaining = len(result.matched_strings) - max_display
                report_lines.append(f"  ... and {remaining} more matches")

        return "\n".join(report_lines)


# Factory functions for common use cases
def create_federal_agency_matcher(threshold: int = 85) -> GenericFuzzyMatcher:
    """Create a fuzzy matcher optimized for federal agency names."""
    # Use default strategies but override their thresholds
    return GenericFuzzyMatcher(variant_generator=FederalAgencyVariantGenerator(), global_threshold=threshold)


def create_person_name_matcher(threshold: int = 90) -> GenericFuzzyMatcher:
    """Create a fuzzy matcher optimized for person names.
    Excluding partial_ratio from default strategies as it may not be suitable for names.
    """
    strategies = [
        MatchingStrategy(fuzz.token_sort_ratio, threshold, "token_sort"),
        MatchingStrategy(fuzz.token_set_ratio, threshold, "token_set"),
        MatchingStrategy(fuzz.ratio, threshold, "exact"),
    ]
    return GenericFuzzyMatcher(
        strategies=strategies, variant_generator=PersonNameVariantGenerator(), global_threshold=threshold
    )


def create_basic_string_matcher(threshold: int = 85) -> GenericFuzzyMatcher:
    """Create a basic fuzzy matcher without variant generation."""
    return GenericFuzzyMatcher(global_threshold=threshold)
