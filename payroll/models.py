from django.db import models
from django.core.exceptions import ValidationError

# Create your models here.

from companies.models import Company
from contracts.models import PurchaseOrder
from musters.models import SkillGroup


class CalculationMethod(models.TextChoices):
    MANUAL = "manual", "Manual"
    FIXED_MONTHLY = "fixed_monthly", "Fixed Monthly"
    PER_DAY = "per_day", "Per Day"
    PER_HOUR = "per_hour", "Per Hour"
    PERCENTAGE = "percentage", "Percentage"


class PercentageBase(models.TextChoices):
    BASIC = "basic", "Basic Wage"
    BASIC_PLUS_ALLOWANCES = "basic_plus_allowances", "Basic + Allowances"
    GROSS = "gross", "Gross Wage"
    DAILY_RATE_WORKING_DAYS = "daily_rate_working_days", "Daily Rate × Working Days"
    COMPONENT = "component", "Specific Component"


class PayComponent(models.Model):
    """
    Master list of earning and deduction components.

    Examples:
    - Basic Wage
    - PF Allowance
    - ESI Allowance
    - JAC Allowance
    - Other Cash
    - Additional Allowance
    - PF Deduction
    - ESI Deduction
    - Other Advance
    - Festival Advance
    """

    class Category(models.TextChoices):
        EARNING = "earning", "Earning"
        DEDUCTION = "deduction", "Deduction"

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="pay_components",
    )

    name = models.CharField(max_length=100)
    code = models.CharField(
        max_length=50,
        help_text="Short internal code, example BASIC, PF_DED, ESI_DED.",
    )

    category = models.CharField(
        max_length=20,
        choices=Category.choices,
    )

    default_calculation_method = models.CharField(
        max_length=30,
        choices=CalculationMethod.choices,
        default=CalculationMethod.MANUAL,
    )

    is_statutory = models.BooleanField(
        default=False,
        help_text="Enable for statutory items like PF and ESI.",
    )

    show_on_payslip = models.BooleanField(default=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["company__name", "category", "display_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="unique_pay_component_code_per_company",
            ),
            models.UniqueConstraint(
                fields=["company", "name", "category"],
                name="unique_pay_component_name_category_per_company",
            ),
        ]

    def __str__(self):
        return f"{self.name}" # ({self.get_category_display()})"


class WageRule(models.Model):
    """
    Skill-group based earning rule.

    Use this for:
    - Basic Wage
    - PF Allowance
    - ESI Allowance
    - Additional Allowance
    - Other earning components

    JAC and OT have separate models because they need special handling.
    """

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="wage_rules",
    )

    component = models.ForeignKey(
        PayComponent,
        on_delete=models.PROTECT,
        related_name="wage_rules",
    )

    skill_group = models.ForeignKey(
        SkillGroup,
        on_delete=models.PROTECT,
        related_name="wage_rules",
    )

    po = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name="wage_rules",
        null=True,
        blank=True,
        help_text="Optional. Leave blank if this rule applies to all POs for this company.",
    )

    calculation_method = models.CharField(
        max_length=30,
        choices=CalculationMethod.choices,
        default=CalculationMethod.PER_DAY,
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Used for fixed, per-day, or per-hour calculation.",
    )

    percentage = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Used only when calculation method is percentage.",
    )

    percentage_base = models.CharField(
        max_length=50,
        choices=PercentageBase.choices,
        blank=True,
    )

    base_component = models.ForeignKey(
        PayComponent,
        on_delete=models.PROTECT,
        related_name="percentage_based_wage_rules",
        null=True,
        blank=True,
        help_text="Required only if percentage base is Specific Component.",
    )

    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    remarks = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            "company__name",
            "skill_group__display_order",
            "component__display_order",
            "-effective_from",
        ]

    def __str__(self):
        return f"{self.company.name} - {self.skill_group.name} - {self.component.name}"

    def clean(self):
        errors = {}

        if self.component:
            if self.component.category != PayComponent.Category.EARNING:
                errors["component"] = "Wage rule component must be an earning component."

            if self.company and self.component.company != self.company:
                errors["component"] = "Component does not belong to selected company."

        if self.po and self.company:
            if self.po.company != self.company:
                errors["po"] = "PO does not belong to selected company."

        if self.effective_from and self.effective_to:
            if self.effective_to < self.effective_from:
                errors["effective_to"] = "Effective to date cannot be before effective from date."

        if self.calculation_method in [
            CalculationMethod.FIXED_MONTHLY,
            CalculationMethod.PER_DAY,
            CalculationMethod.PER_HOUR,
        ]:
            if self.amount is None:
                errors["amount"] = "Amount is required for fixed, per-day, or per-hour calculation."

        if self.calculation_method == CalculationMethod.PERCENTAGE:
            if self.percentage is None:
                errors["percentage"] = "Percentage is required for percentage calculation."

            if not self.percentage_base:
                errors["percentage_base"] = "Percentage base is required."

            if self.percentage_base == PercentageBase.COMPONENT and not self.base_component:
                errors["base_component"] = "Base component is required for Specific Component percentage base."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class DeductionRule(models.Model):
    """
    Skill-group based deduction rule.

    Use this for:
    - PF deduction
    - ESI deduction
    - Any other deduction that depends on skill group

    Manual deductions like Other Advance and Festival Advance can also have components,
    but actual monthly values will be entered during muster/payroll entry.
    """

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="deduction_rules",
    )

    component = models.ForeignKey(
        PayComponent,
        on_delete=models.PROTECT,
        related_name="deduction_rules",
    )

    skill_group = models.ForeignKey(
        SkillGroup,
        on_delete=models.PROTECT,
        related_name="deduction_rules",
    )

    po = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name="deduction_rules",
        null=True,
        blank=True,
        help_text="Optional. Leave blank if this rule applies to all POs for this company.",
    )

    calculation_method = models.CharField(
        max_length=30,
        choices=CalculationMethod.choices,
        default=CalculationMethod.PERCENTAGE,
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Used for fixed, per-day, or per-hour deduction.",
    )

    percentage = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Example: 12 for PF 12%, 0.75 for ESI 0.75%.",
    )

    percentage_base = models.CharField(
        max_length=50,
        choices=PercentageBase.choices,
        blank=True,
    )

    base_component = models.ForeignKey(
        PayComponent,
        on_delete=models.PROTECT,
        related_name="percentage_based_deduction_rules",
        null=True,
        blank=True,
    )

    monthly_cap = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Optional. Example: PF cap 1800 if applicable.",
    )

    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    remarks = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            "company__name",
            "skill_group__display_order",
            "component__display_order",
            "-effective_from",
        ]

    def __str__(self):
        return f"{self.company.name} - {self.skill_group.name} - {self.component.name}"

    def clean(self):
        errors = {}

        if self.component:
            if self.component.category != PayComponent.Category.DEDUCTION:
                errors["component"] = "Deduction rule component must be a deduction component."

            if self.company and self.component.company != self.company:
                errors["component"] = "Component does not belong to selected company."

        if self.po and self.company:
            if self.po.company != self.company:
                errors["po"] = "PO does not belong to selected company."

        if self.effective_from and self.effective_to:
            if self.effective_to < self.effective_from:
                errors["effective_to"] = "Effective to date cannot be before effective from date."

        if self.calculation_method in [
            CalculationMethod.FIXED_MONTHLY,
            CalculationMethod.PER_DAY,
            CalculationMethod.PER_HOUR,
        ]:
            if self.amount is None:
                errors["amount"] = "Amount is required for fixed, per-day, or per-hour deduction."

        if self.calculation_method == CalculationMethod.PERCENTAGE:
            if self.percentage is None:
                errors["percentage"] = "Percentage is required for percentage deduction."

            if not self.percentage_base:
                errors["percentage_base"] = "Percentage base is required."

            if self.percentage_base == PercentageBase.COMPONENT and not self.base_component:
                errors["base_component"] = "Base component is required for Specific Component percentage base."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class OvertimeRule(models.Model):
    """
    Skill-group based OT rule.

    OT is fixed per skill group and changes every few years.
    """

    class RateType(models.TextChoices):
        PER_HOUR = "per_hour", "Per Hour"
        FIXED_AMOUNT = "fixed_amount", "Fixed Amount"

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="overtime_rules",
    )

    skill_group = models.ForeignKey(
        SkillGroup,
        on_delete=models.PROTECT,
        related_name="overtime_rules",
    )

    po = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name="overtime_rules",
        null=True,
        blank=True,
        help_text="Optional. Use only if this OT rate is PO-specific.",
    )

    rate_type = models.CharField(
        max_length=30,
        choices=RateType.choices,
        default=RateType.PER_HOUR,
    )

    rate = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="OT amount. Usually per hour.",
    )

    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    remarks = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["company__name", "skill_group__display_order", "-effective_from"]

    def __str__(self):
        return f"{self.company.name} - {self.skill_group.name} OT - {self.rate}"

    def clean(self):
        errors = {}

        if self.po and self.company:
            if self.po.company != self.company:
                errors["po"] = "PO does not belong to selected company."

        if self.effective_from and self.effective_to:
            if self.effective_to < self.effective_from:
                errors["effective_to"] = "Effective to date cannot be before effective from date."

        if self.rate is not None and self.rate < 0:
            errors["rate"] = "OT rate cannot be negative."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class JACRule(models.Model):
    """
    JAC allowance rule.

    This rule is used only if LabourPOAssignment.jac_eligible = True.
    """

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="jac_rules",
    )

    skill_group = models.ForeignKey(
        SkillGroup,
        on_delete=models.PROTECT,
        related_name="jac_rules",
        null=True,
        blank=True,
        help_text="Optional. Leave blank if JAC amount is same for all skill groups.",
    )

    po = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name="jac_rules",
        null=True,
        blank=True,
        help_text="Optional. Use only if JAC rule is PO-specific.",
    )

    calculation_method = models.CharField(
        max_length=30,
        choices=CalculationMethod.choices,
        default=CalculationMethod.PER_DAY,
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )

    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    remarks = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["company__name", "-effective_from"]

    def __str__(self):
        skill = self.skill_group.name if self.skill_group else "All Skills"
        po_number = self.po.po_number if self.po else "All POs"
        return f"{self.company.name} - JAC - {skill} - {po_number}"

    def clean(self):
        errors = {}

        if self.po and self.company:
            if self.po.company != self.company:
                errors["po"] = "PO does not belong to selected company."

        if self.effective_from and self.effective_to:
            if self.effective_to < self.effective_from:
                errors["effective_to"] = "Effective to date cannot be before effective from date."

        if self.calculation_method != CalculationMethod.MANUAL and self.amount is None:
            errors["amount"] = "Amount is required unless calculation method is Manual."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class PayrollCycle(models.Model):
    """
    Payroll period.

    Your regular cycle:
    25th previous month to 24th current month.

    Example:
    May 2026 payroll = 25-Apr-2026 to 24-May-2026.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        CALCULATED = "calculated", "Calculated"
        APPROVED = "approved", "Approved"
        LOCKED = "locked", "Locked"
        CANCELLED = "cancelled", "Cancelled"

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="payroll_cycles",
    )

    po = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name="payroll_cycles",
    )

    name = models.CharField(
        max_length=100,
        help_text="Example: May 2026 Payroll",
    )

    period_start = models.DateField()
    period_end = models.DateField()

    pay_date = models.DateField(null=True, blank=True)

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    remarks = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-period_start", "company__name", "po__po_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "po", "period_start", "period_end"],
                name="unique_payroll_cycle_per_company_po_period",
            )
        ]

    def __str__(self):
        return f"{self.name} - {self.po.po_number}"

    def clean(self):
        errors = {}

        if self.company and self.po:
            if self.po.company != self.company:
                errors["po"] = "PO does not belong to selected company."

        if self.period_start and self.period_end:
            if self.period_end < self.period_start:
                errors["period_end"] = "Period end date cannot be before period start date."

        if self.po and self.period_start and self.period_end:
            if self.period_start < self.po.contract_start_date:
                errors["period_start"] = "Payroll period cannot start before PO start date."

            if self.period_end > self.po.contract_end_date:
                errors["period_end"] = "Payroll period cannot end after PO end date."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)