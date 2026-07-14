"""
Models for the custom playlist application.

Defines the structure for user-created playlists consisting of selected
lectures, payment tracking for these playlists, and related invoices.
"""
from django.db import models
from accounts.models import Account
from course.models import Video


class CustomPlaylist(models.Model):
    """!
    @brief Represents a user-defined collection of specific course lectures purchased as a bundle.
    @details Tracks the composite price, enrollment status, and assignment accessibility 
             for a personalized learning path.
    """
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('purchased', 'Purchased'),
        ('cancelled', 'Cancelled'),
    )

    user = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='custom_playlists')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_purchased = models.BooleanField(default=False)
    include_assignments = models.BooleanField(default=False)
    duration = models.IntegerField(default=1)  # Duration in months
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Razorpay or other payment integration fields can be added here
    payment_id = models.CharField(max_length=100, blank=True, null=True)
    order_id = models.CharField(max_length=100, blank=True, null=True) # Razorpay order id
    order_number = models.CharField(max_length=50, blank=True, null=True) # Internal order generation
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def end_date(self):
        from dateutil.relativedelta import relativedelta
        duration_months = self.duration or 1
        return self.created_at + relativedelta(months=duration_months)

    @property
    def is_expired(self):
        from django.utils.timezone import now
        return now() > self.end_date

    def __str__(self):
        return f"{self.title} ({self.user.email})"

class PlaylistLecture(models.Model):
    """!
    @brief Junction model mapping individual course videos/lectures to a specific CustomPlaylist.
    @details Ensures that users only access the specific lectures they have selected and paid for.
    """
    playlist = models.ForeignKey(CustomPlaylist, on_delete=models.CASCADE, related_name='playlist_lectures')
    lecture = models.ForeignKey(Video, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('playlist', 'lecture')
        ordering = ['added_at']

    def __str__(self):
        return f"{self.lecture.title} in {self.playlist.title}"


class Invoice(models.Model):
    """!
    @brief Specialized financial record for Custom Playlist transactions.
    @details Stores transaction IDs, generated serial numbers, and physical links to the 
             rendered PDF invoice for administrative and student auditing.
    """
    user = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='playlist_invoices')
    playlist = models.ForeignKey(CustomPlaylist, on_delete=models.CASCADE, related_name='invoices')
    purchase_type = models.CharField(max_length=100, default="Custom Playlist")
    playlist_name = models.CharField(max_length=255, default="")
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    payment_id = models.CharField(max_length=100)
    serial_no = models.CharField(max_length=500, blank=True, null=True)
    invoice_file = models.FileField(upload_to="Invoice_users/playlists/", blank=True)
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Invoice for {self.playlist_name} - {self.payment_id}"
