from django.db import models

# Create your models here.
class Team(models.Model):
    category_choices = (
        ('academic_advisory_board', 'academic_advisory_board'),
        ('core_team', 'core_team'),
        ('core_team_and_TA', 'core_team_and_TA'),
    )

    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    role = models.CharField(max_length=500)

    # new field (05_Aug_2025)
    job_role = models.CharField(max_length=500, null=True, blank=True)
    
    linkedin_link = models.CharField(max_length=255)
    photo = models.ImageField(upload_to='teams')
    category = models.CharField(choices=category_choices, max_length=255, default='core_team')
    created_date = models.DateTimeField(auto_now_add=True)

    REQUIRED_FIELDS = ['first_name', 'last_name', 'role']

    def __str__(self):
        return self.first_name