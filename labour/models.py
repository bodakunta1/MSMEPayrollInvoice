from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db.models import Q

# Create your models here.

aadhaar_validator = RegexValidator(
    regex=r"^\d{12}$",
    message="Aadhaar number must contain exactly 12 digits.",
)

ifsc_validator = RegexValidator(
    regex=r"^[A-Z]{4}0[A-Z0-9]{6}$",
    message="Enter a valid IFSC code.",
)

uan_validator = RegexValidator(
    regex=r"^\d{12}$",
    message="UAN must contain exactly 12 digits.",
)


class Labour(models.Model):
    class Gender(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"
        OTHER = "other", "Other"

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="labourers",
    )

    labour_code = models.CharField(
        max_length=50,
        help_text="Internal labour code or employee number.",
    )

    full_name = models.CharField(max_length=150)
    father_name = models.CharField(max_length=150, blank=True)

    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(
        max_length=20,
        choices=Gender.choices,
        blank=True,
    )

    mobile_number = models.CharField(max_length=20, blank=True)
    whatsapp_number = models.CharField(max_length=20, blank=True)

    aadhaar_number = models.CharField(
        max_length=12,
        blank=True,
        validators=[aadhaar_validator],
        help_text="Required for PF/ESI records. Do not print this on payslips.",
    )

    uan_number = models.CharField(
        max_length=12,
        blank=True,
        validators=[uan_validator],
        help_text="PF UAN number.",
    )

    esi_number = models.CharField(
        max_length=50,
        blank=True,
        help_text="ESI insurance number.",
    )

    bank_account_number = models.CharField(max_length=50, blank=True)
    bank_ifsc_code = models.CharField(
        max_length=11,
        blank=True,
        validators=[ifsc_validator],
    )
    bank_name = models.CharField(max_length=150, blank=True)

    address = models.TextField(blank=True)

    photo = models.ImageField(
        upload_to="labour_photos/",
        blank=True,
        null=True,
    )

    default_skill_group = models.ForeignKey(
        "masters.SkillGroup",
        on_delete=models.PROTECT,
        related_name="default_labourers",
    )

    joining_date = models.DateField(null=True, blank=True)
    exit_date = models.DateField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    remarks = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["company__name", "full_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "labour_code"],
                name="unique_labour_code_per_company",
            ),
            models.UniqueConstraint(
                fields=["company", "aadhaar_number"],
                condition=~Q(aadhaar_number=""),
                name="unique_aadhaar_per_company_when_present",
            ),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.labour_code})"

    def clean(self):
        errors = {}

        if self.joining_date and self.exit_date:
            if self.exit_date < self.joining_date:
                errors["exit_date"] = "Exit date cannot be before joining date."

        if errors:
            raise ValidationError(errors)

    @property
    def masked_aadhaar(self):
        if not self.aadhaar_number:
            return ""
        return f"XXXX-XXXX-{self.aadhaar_number[-4:]}"


class LabourPOAssignment(models.Model):
    """
    Connects labourers to a specific PO.

    This is the important control table:
    - PO-wise active labour count
    - Skill-wise PO count
    - JAC eligibility
    - Labour transfer history
    """

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="labour_assignments",
    )

    po = models.ForeignKey(
        "contracts.PurchaseOrder",
        on_delete=models.CASCADE,
        related_name="labour_assignments",
    )

    labourer = models.ForeignKey(
        Labour,
        on_delete=models.CASCADE,
        related_name="po_assignments",
    )

    skill_group = models.ForeignKey(
        "masters.SkillGroup",
        on_delete=models.PROTECT,
        related_name="po_assignments",
    )

    assignment_start_date = models.DateField()
    assignment_end_date = models.DateField(null=True, blank=True)

    jac_eligible = models.BooleanField(
        default=False,
        help_text="Enable only if this labourer is eligible for JAC allowance.",
    )

    is_active = models.BooleanField(default=True)
    remarks = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["po__po_number", "labourer__full_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "labourer"],
                condition=Q(is_active=True),
                name="unique_active_po_assignment_per_labourer_company",
            )
        ]

    def __str__(self):
        return f"{self.labourer.full_name} → {self.po.po_number}"

    def clean(self):
        errors = {}

        if self.company_id and self.labourer_id:
            if self.labourer.company_id != self.company_id:
                errors["labourer"] = "Labourer does not belong to this company."

        if self.company_id and self.po_id:
            if self.po.company_id != self.company_id:
                errors["po"] = "PO does not belong to this company."

        if self.assignment_start_date and self.assignment_end_date:
            if self.assignment_end_date < self.assignment_start_date:
                errors["assignment_end_date"] = (
                    "Assignment end date cannot be before start date."
                )

        if self.po_id and self.assignment_start_date:
            if self.assignment_start_date < self.po.contract_start_date:
                errors["assignment_start_date"] = (
                    "Assignment start date cannot be before PO start date."
                )

            if self.assignment_start_date > self.po.contract_end_date:
                errors["assignment_start_date"] = (
                    "Assignment start date cannot be after PO end date."
                )

        if self.po_id and self.assignment_end_date:
            if self.assignment_end_date > self.po.contract_end_date:
                errors["assignment_end_date"] = (
                    "Assignment end date cannot be after PO end date."
                )

        if self.is_active and self.company_id and self.labourer_id:
            active_assignment_exists = (
                LabourPOAssignment.objects.filter(
                    company=self.company,
                    labourer=self.labourer,
                    is_active=True,
                )
                .exclude(pk=self.pk)
                .exists()
            )

            if active_assignment_exists:
                errors["labourer"] = (
                    "This labourer already has an active PO assignment. "
                    "Deactivate the old assignment before assigning a new PO."
                )

        if self.is_active and self.po_id and self.skill_group_id:
            active_total = (
                LabourPOAssignment.objects.filter(
                    po=self.po,
                    is_active=True,
                )
                .exclude(pk=self.pk)
                .count()
            )

            if active_total + 1 > self.po.total_labour_limit:
                errors["po"] = (
                    "Cannot assign labourer. PO total labour allotment limit exceeded."
                )

            skill_limit = self.po.get_skill_limit(self.skill_group)

            if skill_limit is not None:
                active_skill_total = (
                    LabourPOAssignment.objects.filter(
                        po=self.po,
                        skill_group=self.skill_group,
                        is_active=True,
                    )
                    .exclude(pk=self.pk)
                    .count()
                )

                if active_skill_total + 1 > skill_limit:
                    errors["skill_group"] = (
                        f"Cannot assign labourer. {self.skill_group.name} "
                        f"limit exceeded for this PO."
                    )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)