"""
Tests for validating the permissions system consistency.

These tests ensure that:
1. All URLs have permissions defined in the centralized mapping
2. All views with permission decorators are in the mapping
3. The permissions in the decorators match those in the mapping
"""

from django.test import TestCase
from django.urls import reverse, NoReverseMatch
from registrar.models.user_domain_role import UserDomainRole
from registrar.permissions import URL_PERMISSIONS, verify_all_urls_have_permissions, validate_permissions
from registrar.tests.common import MockDbForIndividualTests


class TestPermissionsMapping(TestCase):
    """Test the centralized permissions mapping for completeness and consistency."""

    def test_all_urls_have_permissions(self):
        """Verify that all URL patterns in the application have permissions defined in the mapping."""
        missing_urls = verify_all_urls_have_permissions()
        
        # Format URLs for better readability in case of failure
        if missing_urls:
            formatted_urls = "\n".join([f"  - {url}" for url in missing_urls])
            self.fail(
                f"The following URL patterns are missing from URL_PERMISSIONS mapping:\n{formatted_urls}\n"
                f"Please add them to the URL_PERMISSIONS dictionary in registrar/permissions.py"
            )

    def test_permission_decorator_consistency(self):
        """
        Test that all views have consistent permission rules between 
        the centralized mapping and view decorators.
        """
        issues = validate_permissions()
        
        error_messages = []
        
        if issues['missing_in_mapping']:
            urls = "\n".join([f"  - {name} (at {path})" for name, path in issues['missing_in_mapping']])
            error_messages.append(
                f"The following URLs have permission decorators but are missing from the mapping:\n{urls}\n"
                "Add these URLs to the URL_PERMISSIONS dictionary in registrar/permissions.py"
            )
        
        if issues['missing_decorator']:
            urls = "\n".join([f"  - {name} (at {path})" for name, path in issues['missing_decorator']])
            error_messages.append(
                f"The following URLs are in the mapping but missing @grant_access decorators:\n{urls}\n"
                "Add appropriate @grant_access decorators to these views"
            )
        
        if issues['permission_mismatch']:
            mismatches = []
            for name, path, view_perms, mapping_perms in issues['permission_mismatch']:
                view_perms_str = ", ".join(sorted(str(p) for p in view_perms))
                mapping_perms_str = ", ".join(sorted(str(p) for p in mapping_perms))
                mismatches.append(
                    f"  - {name} (at {path}):\n"
                    f"    Decorator: [{view_perms_str}]\n"
                    f"    Mapping:   [{mapping_perms_str}]"
                )
            
            error_messages.append(
                f"The following URLs have mismatched permissions between decorators and mapping:\n"
                f"{chr(10).join(mismatches)}\n"
                "Update either the decorator or the mapping to ensure consistency"
            )
        
        if error_messages:
            self.fail("\n\n".join(error_messages))


class TestPermissionSystemForURLs(MockDbForIndividualTests):
    """Test actual permissions for key URLs with test data"""
    
    def test_domain_manager_can_access_domain_pages(self):
        """Domain managers should be able to access domain management pages"""
        # Create a user-domain relationship to make the user a domain manager
        UserDomainRole.objects.create(user=self.user, domain=self.domain_1)
        
        # Login as the user
        self.client.force_login(self.user)
        
        # Test access to domain detail page
        response = self.client.get(reverse('domain', kwargs={'domain_pk': self.domain_1.id}))
        self.assertEqual(response.status_code, 200)
        
        # Test access to domain DNS page
        response = self.client.get(reverse('domain-dns', kwargs={'domain_pk': self.domain_1.id}))
        self.assertEqual(response.status_code, 200)
    
    def test_non_domain_manager_cannot_access_domain_pages(self):
        """Non-domain managers should not be able to access domain management pages"""
        # Login as a user who is not a domain manager
        self.client.force_login(self.user)
        
        # Test access to domain detail page
        response = self.client.get(reverse('domain', kwargs={'domain_pk': self.domain_1.id}))
        self.assertEqual(response.status_code, 403)
        
        # Test access to domain DNS page
        response = self.client.get(reverse('domain-dns', kwargs={'domain_pk': self.domain_1.id}))
        self.assertEqual(response.status_code, 403)
    
    def test_staff_can_access_analytics(self):
        """Staff users should be able to access analytics pages"""
        # Login as a staff user
        self.client.force_login(self.custom_staffuser)
        
        # Test access to analytics page
        response = self.client.get(reverse('analytics'))
        self.assertEqual(response.status_code, 200)
    
    def test_non_staff_cannot_access_analytics(self):
        """Non-staff users should not be able to access analytics pages"""
        # Login as a non-staff user
        self.client.force_login(self.user)
        
        # Test access to analytics page
        response = self.client.get(reverse('analytics'))
        self.assertEqual(response.status_code, 403)
