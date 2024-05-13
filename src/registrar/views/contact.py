from django.http import HttpResponseRedirect
from django.urls import reverse
from registrar.forms.contact import ContactForm
from registrar.models.contact import Contact
from registrar.templatetags.url_helpers import public_site_url
from registrar.views.utility.permission_views import ContactPermissionView
from django.views.generic.edit import FormMixin
from registrar.models.utility.generic_helper import to_database, from_database
from django.utils.safestring import mark_safe

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

    def post(self, request, *args, **kwargs):
        """Form submission posts to this view.

        This post method harmonizes using BaseContactView and FormMixin
        """
        # Set the current contact object in cache
        self._set_contact(request)

        form = self.get_form()

        # Get the current form and validate it
        if form.is_valid():
            if "redirect_to_home" not in self.session or not self.session["redirect_to_home"]:
                self.session["redirect_to_home"] = "contact_setup_submit_button" in request.POST
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def get_success_url(self):
        """Redirect to the nameservers page for the domain."""

        # TODO - some logic should exist that navigates them to the domain request page if 
        # they clicked it on get.gov
        # Add a notification that the update was successful
        if "redirect_to_home" in self.session and self.session["redirect_to_home"]:
            return reverse("home")
        else:
            # Redirect to the same page with a query parameter to confirm changes
            self.session["redirect_to_home"] = True
            return reverse("finish-contact-profile-setup", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
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

        if "redirect_to_home" in self.session and self.session["redirect_to_home"]:
            context['confirm_changes'] = True

        return context
    
    def _email_sublabel_text(self):
        """Returns the lengthy sublabel for the email field"""
        help_url = public_site_url('help/account-management/#get-help-with-login.gov')
        return mark_safe(
            "We recommend using your work email for your .gov account. "
            "If the wrong email is displayed below, you’ll need to update your Login.gov account "
            f'and log back in. <a class="usa-link" href={help_url}>Get help with your Login.gov account.</a>'
        )
