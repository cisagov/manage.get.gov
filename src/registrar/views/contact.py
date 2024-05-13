from enum import Enum
from urllib.parse import urlencode
from django.http import HttpResponseRedirect
from django.urls import reverse
from registrar.forms.contact import ContactForm
from registrar.models.contact import Contact
from registrar.templatetags.url_helpers import public_site_url
from registrar.views.utility.permission_views import ContactPermissionView
from django.views.generic.edit import FormMixin
from registrar.models.utility.generic_helper import to_database, from_database
from django.utils.safestring import mark_safe

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect

# TODO we can and probably should generalize this at this rate.
class BaseContactView(ContactPermissionView):

    def get(self, request, *args, **kwargs):
        self._set_contact(request)
        context = self.get_context_data(object=self.object)

        return self.render_to_response(context)

    # TODO - this deserves a small refactor
    def _set_contact(self, request):
        """
        get domain from session cache or from db and set
        to self.object
        set session to self for downstream functions to
        update session cache
        """
        self.session = request.session

        contact_pk = "contact:" + str(self.kwargs.get("pk"))
        cached_contact = self.session.get(contact_pk)

        if cached_contact:
            self.object = cached_contact
        else:
            self.object = self.get_object()

        self._update_session_with_contact()

    def _update_session_with_contact(self):
        """
        Set contact pk in the session cache
        """
        contact_pk = "contact:" + str(self.kwargs.get("pk"))
        self.session[contact_pk] = self.object


class ContactFormBaseView(BaseContactView, FormMixin):

    def post(self, request, *args, **kwargs):
        """Form submission posts to this view.

        This post method harmonizes using BaseContactView and FormMixin
        """
        # Set the current contact object in cache
        self._set_contact(request)

        form = self.get_form()

        # Get the current form and validate it
        return self.form_valid(form) if form.is_valid() else self.form_invalid(form)

    def form_invalid(self, form):
        # updates session cache with contact
        self._update_session_with_contact()

        # superclass has the redirect
        return super().form_invalid(form)


class ContactProfileSetupView(ContactFormBaseView):
    """This view forces the user into providing additional details that 
    we may have missed from Login.gov"""
    template_name = "finish_contact_setup.html"
    form_class = ContactForm
    model = Contact

    redirect_type = None
    class RedirectType:
        HOME = "home"
        BACK_TO_SELF = "back_to_self"
        DOMAIN_REQUEST = "domain_request"

    @method_decorator(csrf_protect)
    def dispatch(self, request, *args, **kwargs):
        # Default redirect type
        default_redirect = self.RedirectType.BACK_TO_SELF

        # Update redirect type based on the query parameter if present
        redirect_type = request.GET.get("redirect", default_redirect)

        # Store the redirect type in the session
        self.redirect_type = redirect_type

        return super().dispatch(request, *args, **kwargs)

    def get_redirect_url(self):
        match self.redirect_type:
            case self.RedirectType.HOME:
                return reverse("home")
            case self.RedirectType.BACK_TO_SELF:
                return reverse("finish-contact-profile-setup", kwargs={"pk": self.object.pk})
            case self.RedirectType.DOMAIN_REQUEST:
                # TODO
                return reverse("home")
            case _:
                return reverse("home")
    
    def get_success_url(self):
        """Redirect to the nameservers page for the domain."""
        redirect_url = self.get_redirect_url()
        return redirect_url

    def post(self, request, *args, **kwargs):
        """Form submission posts to this view.

        This post method harmonizes using BaseContactView and FormMixin
        """
                # Default redirect type
        default_redirect = self.RedirectType.BACK_TO_SELF

        # Update redirect type based on the query parameter if present
        redirect_type = request.GET.get("redirect", default_redirect)

        # Store the redirect type in the session
        self.redirect_type = redirect_type

        # Set the current contact object in cache
        self._set_contact(request)

        form = self.get_form()

        # Get the current form and validate it
        if form.is_valid():
            if 'contact_setup_save_button' in request.POST:
                # Logic for when the 'Save' button is clicked
                self.redirect_type = self.RedirectType.BACK_TO_SELF
                self.session["should_redirect_to_home"] = "redirect_to_home" in request.POST
            elif 'contact_setup_submit_button' in request.POST:
                # Logic for when the 'Save and continue' button is clicked
                if self.redirect_type != self.RedirectType.DOMAIN_REQUEST:
                    self.redirect_type = self.RedirectType.HOME
                else:
                    self.redirect_type = self.RedirectType.DOMAIN_REQUEST
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):

        if self.redirect_type == self.RedirectType.HOME:
            self.request.user.finished_setup = True
            self.request.user.save()
        
        to_database(form=form, obj=self.object)
        self._update_session_with_contact()

        return super().form_valid(form)
    
    def get_initial(self):
        """The initial value for the form (which is a formset here)."""
        db_object = from_database(form_class=self.form_class, obj=self.object)
        return db_object
    
    def get_context_data(self, **kwargs):
        
        context = super().get_context_data(**kwargs)
        context["email_sublabel_text"] = self._email_sublabel_text()

        if "should_redirect_to_home" in self.session:
            context["confirm_changes"] = True

        return context
    
    def _email_sublabel_text(self):
        """Returns the lengthy sublabel for the email field"""
        help_url = public_site_url('help/account-management/#get-help-with-login.gov')
        return mark_safe(
            "We recommend using your work email for your .gov account. "
            "If the wrong email is displayed below, you’ll need to update your Login.gov account "
            f'and log back in. <a class="usa-link" href={help_url}>Get help with your Login.gov account.</a>'
        )
