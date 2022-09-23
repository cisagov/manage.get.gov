from django import forms

from .models import UserProfile

class EditProfileForm(forms.ModelForm):
    display_name = forms.CharField(widget=forms.TextInput(attrs={'class': 'usa-input'}), label="Display Name")

    class Meta:
        model = UserProfile
        fields = ['display_name']
