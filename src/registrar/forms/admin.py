from django import forms

class DataExportForm(forms.Form):
    # start_date = forms.DateField(label='Start date', widget=forms.DateInput(attrs={'type': 'date'}))
    # end_date = forms.DateField(label='End date', widget=forms.DateInput(attrs={'type': 'date'}))
    
    security_email = forms.EmailField(
        label="Security email (optional)",
        required=False,
        error_messages={
            "invalid": 'dsas',
        },
    )