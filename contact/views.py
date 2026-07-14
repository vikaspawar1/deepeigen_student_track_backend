from django.shortcuts import render
from django.shortcuts import redirect
from django.conf import settings

# Create your views here.
def contact(request):
    """!
    @brief Renders the platform contact informational page.
    @details Provides multiple channels for user support, including email and telephonic 
             contact information, and populates SEO metadata.
    """
    data = {
        'fixed_header' : True,
        'title': 'Contact | Deep Eigen',
        'description': "If your have any queries about our services, send an email to contact@deepeigen.com and we'll do our best to reply within 24 hours Alternatively simply pickup the phone and give us a call.",
        'canonical_url' : request.build_absolute_uri(request.path)
    }
    return render(request, 'contact/contact.html', data)
    