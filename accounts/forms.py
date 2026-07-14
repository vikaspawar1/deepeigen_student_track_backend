"""
Django forms for handling user and profile data in the accounts app.
"""
from django import forms
from .models import Account, UserProfile

class UserForm(forms.ModelForm):
    """
    Form for updating basic student information (name, phone).
    """
    class Meta:
        model = Account
        fields = ('first_name', 'last_name', 'phone_number')

    def __init__(self, *args, **kwargs):
        """Initializes the form with Bootstrap styling for all fields."""
        super(UserForm, self).__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs['class'] = 'form-control form-control-lg'

class UserProfileForm(forms.ModelForm):
    """
    Form for updating extended student profile information (address, picture).
    """
    profile_picture = forms.ImageField(required=False, error_messages = {'invalid':("Image files only")}, widget=forms.FileInput)
    class Meta:
        model = UserProfile
        fields = ('address_line_1', 'address_line_2', 'city', 'state', 'profile_picture', 'country')

    def __init__(self, *args, **kwargs):
        """Initializes the form with Bootstrap styling for all fields."""
        super(UserProfileForm, self).__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs['class'] = 'form-control form-control-lg'