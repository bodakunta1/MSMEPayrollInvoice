from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.apps import apps

# Create your models here.

class PurchaseOrder(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        CLOSED = "closed", "Closed"
        EXPIRED = "expired", "Expired"

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="purchase_orders",
    )

    client = models.ForeignKey(
        "clients.Client",
        on_delete=models.PROTECT,
        related_name="purchase_orders",
    )

    po_number = models.CharField(max_length=100)
    title = models.CharField(max_length=255, blank=True)
    work_description = models.TextField(blank=True)

    location = models.CharField(max_length=150, blank=True)
    department = models.CharField(max_length=150, blank=True)

    contract_start_date = models.DateField()
    contract_end_date = models.DateField()

    total_labour_limit = models.PositiveIntegerField(
        help_text="Maximum total active labourers allowed under this PO."
    )

    po_value = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )

    po_document = models.FileField(
        upload_to="po_documents/",
        blank=True,
        null=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    remarks = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-contract_start_date", "po_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "po_number"],
                name="unique_po_number_per_company",
            )
        ]

    def __str__(self):
        return f"{self.po_number} - {self.company.name}"

    def clean(self):
        errors = {}

        if (
            self.contract_start_date
            and self.contract_end_date
            and self.contract_end_date < self.contract_start_date
        ):
            errors["contract_end_date"] = "Contract end date cannot be before start date."

        if self.client_id and self.company_id:
            if self.client.company_id != self.company_id:
                errors["client"] = "Selected client does not belong to this company."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE

    def get_total_active_assignments(self):

        LabourPOAssignment = apps.get_model("labour", "LabourPOAssignment")

        return LabourPOAssignment.objects.filter(
            po=self,
            is_active=True,
        ).count()

    def get_active_assignments_for_skill(self, skill_group):

        LabourPOAssignment = apps.get_model("labour", "LabourPOAssignment")

        return LabourPOAssignment.objects.filter(
            po=self,
            skill_group=skill_group,
            is_active=True,
        ).count()

    def get_skill_limit(self, skill_group):
        limit_obj = self.skill_limits.filter(skill_group=skill_group).first()
        return limit_obj.limit if limit_obj else None


class POLabourLimit(models.Model):
    """
    Optional skill-wise manpower limit for each PO.

    Example:
    PO total limit = 90
    Skilled = 40
    Unskilled = 25
    Supervisor = 5
    """

    po = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name="skill_limits",
    )

    skill_group = models.ForeignKey(
        "masters.SkillGroup",
        on_delete=models.PROTECT,
        related_name="po_limits",
    )

    limit = models.PositiveIntegerField()

    class Meta:
        ordering = ["po", "skill_group__display_order"]
        constraints = [
            models.UniqueConstraint(
                fields=["po", "skill_group"],
                name="unique_skill_limit_per_po",
            )
        ]

    def __str__(self):
        return f"{self.po.po_number} - {self.skill_group.name}: {self.limit}"

    def clean(self):
        errors = {}

        if self.po_id and self.limit:
            existing_total = (
                POLabourLimit.objects.filter(po=self.po)
                .exclude(pk=self.pk)
                .aggregate(total=Sum("limit"))
                .get("total")
                or 0
            )

            new_total = existing_total + self.limit

            if new_total > self.po.total_labour_limit:
                errors["limit"] = (
                    "Total of all skill-wise limits cannot exceed "
                    "the PO total labour limit."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)