from django.db import models
from django.core.validators import RegexValidator

# Create your models here.

gst_validator = RegexValidator(
    regex=r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$",
    message="Enter a valid GST number.",
)

pan_validator = RegexValidator(
    regex=r"^[A-Z]{5}[0-9]{4}[A-Z]$",
    message="Enter a valid PAN number.",
)

ifsc_validator = RegexValidator(
    regex=r"^[A-Z]{4}0[A-Z0-9]{6}$",
    message="Enter a valid IFSC code.",
)


class Company(models.Model):
    """
    Contractor/company master.
    Example: M/S BOBBY ERECTORS
    """

    name = models.CharField(max_length=150)
    legal_name = models.CharField(max_length=200, blank=True)

    logo = models.ImageField(upload_to="company_logos/", blank=True, null=True)

    address = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)

    gst_number = models.CharField(
        max_length=15,
        blank=True,
        validators=[gst_validator],
    )
    pan_number = models.CharField(
        max_length=10,
        blank=True,
        validators=[pan_validator],
    )

    pf_registration_number = models.CharField(max_length=50, blank=True)
    esi_registration_number = models.CharField(max_length=50, blank=True)

    bank_name = models.CharField(max_length=150, blank=True)
    bank_account_number = models.CharField(max_length=50, blank=True)
    bank_ifsc_code = models.CharField(
        max_length=11,
        blank=True,
        validators=[ifsc_validator],
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Companies"

    def __str__(self):
        return self.name