from django.shortcuts import render

def home(request):
    """!
    @brief Renders the primary landing page of the Deep Eigen platform.
    @details Populates SEO metadata and canonical URLs for the homepage.
    """
    data = {
        'fixed_header' : True,
        'title': 'Deep Eigen',
        'description': 'Deep Eigen is an education platform provding access to graduate level courses related to artificial intelligence and autonomous driving, with an aim to provide quality contents at a level similar to the top-universities around the world.',
        'canonical_url' : request.build_absolute_uri(request.path)
    }
    return render(request, 'home.html', data)

def faqs(request):
    """!
    @brief Renders the Frequently Asked Questions (FAQ) page.
    @details Provides structured answers to common platform and course-related queries.
    """
    data = {
        'title': 'Frequently Asked Questions | Deep Eigen',
        'description': 'List of Frequently Asked Questions.',
        'canonical_url' : request.build_absolute_uri(request.path)
    }
    return render(request, 'faqs.html', data)

def terms(request):
    """!
    @brief Renders the platform's Terms of Service and legal agreements.
    @details Essential for user enrollment and enrollment compliance.
    """
    data = {
        'title': 'Terms of Service | Deep Eigen',
        'description': 'Terms of Service for Deep Eigen Courses Enrollment.',
        'canonical_url' : request.build_absolute_uri(request.path)
    }
    return render(request, 'terms.html', data)

# Privacy Policy
def privacypolicy(request):
    """!
    @brief Renders the standard corporate Privacy Policy.
    @details Outlines data handling practices for the platform.
    """
    data= {
        'title': 'Privacy Policy | Deep Eigen',
        'description': 'Deep Eigen Privacy Policy',
        'canonical_url' : request.build_absolute_uri(request.path)
    }
    return render(request, 'privacypolicy.html', data)

def privacypolicygdpr(request):
    """!
    @brief Renders the European Union GDPR-compliant Privacy Policy.
    @details Specifically tailored for EU data protection requirements.
    """
    data= {
        'title': 'Privacy Policy GDPR | Deep Eigen',
        'description': 'Deep Eigen Privacy Policy GDPR',
        'canonical_url' : request.build_absolute_uri(request.path)

    }
    return render(request, 'privacypolicygdpr.html', data)

def careers(request):
    """!
    @brief Renders the recruitment and careers informational page.
    @details Showcases opportunities for academic and professional roles within Deep Eigen.
    """
    data = {
        'title': 'Deep Eigen Careers',
        'description': 'Join our team at Deep Eigen, Explore careers for Masters, undergrads and MBA.',
        'canonical_url' : request.build_absolute_uri(request.path)
    }
    return render(request, 'careers.html', data)

# Maintenance Mode
def maintenance(request):
    """!
    @brief Renders the static maintenance notification splash screen.
    @details Served globally when the platform is in maintenance mode.
    """
    data = {
        'title': 'Maintenance | Deep Eigen ',
        'description': 'Deep Eigen Maintenance Mode',
        'canonical_url' : request.build_absolute_uri(request.path)
    }
    return render(request, 'maintenance.html', data)

def robots_seo(request):
    """!
    @brief Serves the robots.txt file to guide search engine crawlers.
    @details Directs bot behavior and indexing priorities.
    """
    return render(request, 'robots.txt', content_type='text')

def html_sitemap(request):
    """!
    @brief Renders a human-readable directory of important platform links.
    @details Facilitates navigation for users and accessibility tools.
    """
    data = {
        'title': 'Sitemap | Deep Eigen ',
        'description': 'Sitemap is a list of all the Important pages of Deep Eigen',
        'canonical_url' : request.build_absolute_uri(request.path)
    }
    return render(request, 'sitemap.html', data)

def xml_sitemap(request):
    """!
    @brief Serves the machine-readable XML sitemap for search engines.
    @details Enhances platform discoverability via standard sitemap protocols.
    """
    return render(request, 'sitemap.xml', content_type='text/xml')


