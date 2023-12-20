from django import forms

class DataExportForm(forms.Form):
    start_date = forms.DateField(label='Start date', widget=forms.DateInput(attrs={'type': 'date'}))
    end_date = forms.DateField(label='End date', widget=forms.DateInput(attrs={'type': 'date'}))
