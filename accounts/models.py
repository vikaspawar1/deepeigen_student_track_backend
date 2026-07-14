"""!
@file accounts/models.py
@brief Module defining the authentication and user profile models for the Deepeigen platform.

This module contains the custom user model (Account), its manager (MyAccountManager),
and supplementary profile and company data models.
"""

from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from datetime import datetime

class MyAccountManager(BaseUserManager):
    """!
    @brief Custom manager for the Account model to handle user and superuser creation.
    """
    def create_user(self, first_name, last_name, username, email, password=None, phone_number=None, profession=None, country=None):
        """!
        @brief Create and save a regular user with the given details.

        @param first_name (str) User's first name.
        @param last_name (str) User's last name.
        @param username (str) Unique username.
        @param email (str) Unique email address.
        @param password (str, optional) User's password.
        @param phone_number (str, optional) User's contact number.
        @param profession (str, optional) User's profession.
        @param country (str, optional) User's country of residence.

        @return Account The created user instance.

        @exception ValueError If email or username is not provided.
        """
        if not email:
            raise ValueError('User must have an email address')

        if not username:
            raise ValueError('User must have an username')

        user = self.model(
            email = self.normalize_email(email),
            username = username,
            first_name = first_name,
            last_name = last_name,
            phone_number=phone_number,
            profession=profession,
            country=country
        )

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, first_name, last_name, email, username, password, phone_number=None):
        """!
        @brief Create and save a superuser with the given details.

        @param first_name (str) User's first name.
        @param last_name (str) User's last name.
        @param email (str) Unique email address.
        @param username (str) Unique username.
        @param password (str) User's password.
        @param phone_number (str, optional) User's contact number.

        @return Account The created superuser instance with elevated permissions.
        """
        user = self.create_user(
            email = self.normalize_email(email),
            username = username,
            password = password,
            first_name = first_name,
            last_name = last_name,
            phone_number = phone_number
        )
        user.is_admin = True
        user.is_active = True
        user.is_staff = True
        user.is_superadmin = True
        user.save(using=self._db)
        return user


class Account(AbstractBaseUser):
    """!
    @brief Custom user model representing a student or admin on the platform.
    @note Uses email as the primary authentication field.
    """
    first_name      = models.CharField(max_length=50)
    last_name       = models.CharField(max_length=50)
    username        = models.CharField(max_length=50, unique=True)
    email           = models.EmailField(max_length=50, unique=True)
    phone_number    = models.CharField(max_length=25, null=True)
    profession      = models.CharField(max_length=100, null=True)
    country         = models.CharField(max_length=100, null=True, default='')
    courses_enrolled = models.IntegerField(default=0, null=True)
    
    # Required for Django authentication
    date_joined     = models.DateTimeField(auto_now_add=True)
    last_login      = models.DateTimeField(auto_now_add=True)
    is_admin        = models.BooleanField(default=False)
    is_staff        = models.BooleanField(default=False)
    is_active       = models.BooleanField(default=False)
    is_superadmin   = models.BooleanField(default=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    objects = MyAccountManager()

    def full_name(self):
        """!
        @brief Returns the user's full name.
        @return str Concatenated first and last name.
        """
        return f'{self.first_name} {self.last_name}'

    def __str__(self):
        """!
        @brief Returns the string representation of the account.
        @return str The user's email address.
        """
        return self.email

    def has_perm(self, perm, obj=None):
        """!
        @brief Check if user has a specific permission.
        @note Admins have all permissions.
        @param perm (str) The permission name.
        @param obj (object, optional) The object to check permissions against.
        @return bool True if permitted, False otherwise.
        """
        return self.is_admin

    def has_module_perms(self, add_label):
        """!
        @brief Check if user has permissions for a specific app module.
        @param add_label (str) The module label.
        @return bool True as default for active accounts.
        """
        return True


class UserProfile(models.Model):
    """!
    @brief Extended profile information for an Account instance.
    @details Includes address and profile picture information.
    """
    user = models.OneToOneField(Account, on_delete=models.CASCADE)
    address_line_1 = models.CharField(blank=True, max_length=200)
    address_line_2 = models.CharField(blank=True, max_length=200)
    profile_picture = models.ImageField(blank=True, upload_to='userprofile')
    city = models.CharField(blank=True, max_length=50)
    state = models.CharField(blank=True, max_length=50)
    country = models.CharField(blank=True, max_length=50, default='')
    postal_code = models.CharField(blank=True, max_length=20, default='')

    def __str__(self):
        """!
        @brief Returns the string representation of the profile.
        @return str The user's first name.
        """
        return self.user.first_name

    def full_address(self):
        """!
        @brief Returns the concatenated full address of the user.
        @return str Concatenated address lines 1 and 2.
        """
        return f'{self.address_line_1} {self.address_line_2}'
    

class company(models.Model):
    """!
    @brief Model storing company-wide information used for invoicing and branding.
    """
    name = models.CharField(max_length=50,default="Deep Eigen Pvt. Ltd")
    address = models.CharField(max_length=150,default="Bhopal, Madhya Pradesh, India")
    phone = models.CharField(max_length=50,default="+91 8210303336")
    pan = models.CharField(max_length=50 ,default="AAICD5934H")
    CIN = models.CharField(max_length=50, default=" U80900MP2021PTC056553")
    date = models.DateField(datetime(year=12, month=12, day=30))
    global_id=models.IntegerField(default=1)