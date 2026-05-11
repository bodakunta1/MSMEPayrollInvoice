from django.db import models
from django.core.validators import RegexValidator

# Create your models here.

gst_validator = RegexValidator(
    regex=r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$",
    message="Enter a valid GST number.",
)


class Client(models.Model):
    """
    Client/customer master.
    Example: NTPC Ramagundam.
    """

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="clients",
    )

    name = models.CharField(max_length=150)
    site_name = models.CharField(max_length=150, blank=True)

    address = models.TextField(blank=True)
    gst_number = models.CharField(
        max_length=15,
        blank=True,
        validators=[gst_validator],
    )

    contact_person = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["company__name", "name", "site_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "name", "site_name"],
                name="unique_client_site_per_company",
            )
        ]

    def __str__(self):
        if self.site_name:
            return f"{self.name} - {self.site_name}"
        return self.name