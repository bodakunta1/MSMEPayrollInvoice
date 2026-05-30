from django.db import models
from django.core.exceptions import ValidationError
from decimal import Decimal
from django.contrib.auth import get_user_model
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.db.models import QuerySet
    # PayrollLine is defined later in this module; the import is inside TYPE_CHECKING
    # so it won't execute at runtime but helps static type checkers.
    from .models import PayrollLine  # type: ignore

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
    

class PayrollRun(models.Model):
    """
    One payroll calculation run for one company + PO + payroll cycle.
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
        related_name="payroll_runs",
    )

    po = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name="payroll_runs",
    )

    payroll_cycle = models.OneToOneField(
        PayrollCycle,
        on_delete=models.CASCADE,
        related_name="payroll_run",
    )

    run_number = models.CharField(
        max_length=100,
        unique=True,
        blank=True,
        help_text="Auto-generated payroll run number.",
    )

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    total_labourers = models.PositiveIntegerField(default=0)

    total_basic_wage = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    total_jac_allowance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    total_other_cash = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    total_overtime = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    total_additional_allowance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    total_gross_wage = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    total_pf_deduction = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    total_esi_deduction = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    total_other_advance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    total_festival_advance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    total_deductions = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    total_net_pay = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    calculated_by = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calculated_payroll_runs",
    )

    calculated_at = models.DateTimeField(null=True, blank=True)

    remarks = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-payroll_cycle__period_start", "company__name", "po__po_number"]

    def __str__(self):
        return self.run_number or f"Payroll Run - {self.payroll_cycle.name}"

    if TYPE_CHECKING:
        # Reverse relation from PayrollLine defined below.
        lines: "QuerySet[PayrollLine]"

    def clean(self):
        errors = {}

        if self.company and self.po:
            if self.po.company != self.company:
                errors["po"] = "PO does not belong to selected company."

        if self.company and self.payroll_cycle:
            if self.payroll_cycle.company != self.company:
                errors["payroll_cycle"] = "Payroll cycle does not belong to selected company."

        if self.po and self.payroll_cycle:
            if self.payroll_cycle.po != self.po:
                errors["payroll_cycle"] = "Payroll cycle PO does not match selected PO."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.run_number and self.payroll_cycle:
            self.run_number = (
                f"PR-C{self.company}-PO{self.po}-"
                f"{self.payroll_cycle.period_start:%Y%m%d}-"
                f"{self.payroll_cycle.period_end:%Y%m%d}"
            )

        self.full_clean()
        return super().save(*args, **kwargs)


class PayrollLine(models.Model):
    """
    Calculated payroll for one labourer in one payroll run.
    """

    payroll_run = models.ForeignKey(
        PayrollRun,
        on_delete=models.CASCADE,
        related_name="lines",
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="payroll_lines",
    )

    payroll_cycle = models.ForeignKey(
        PayrollCycle,
        on_delete=models.CASCADE,
        related_name="payroll_lines",
    )

    labour_assignment = models.ForeignKey(
        "labour.LabourPOAssignment",
        on_delete=models.PROTECT,
        related_name="payroll_lines",
    )

    muster_entry = models.OneToOneField(
        "attendance.MusterEntry",
        on_delete=models.PROTECT,
        related_name="payroll_line",
    )

    labour_code = models.CharField(max_length=50)
    labourer_name = models.CharField(max_length=150)
    skill_group_name = models.CharField(max_length=100)

    working_days = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    basic_hours = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("0.00"))
    overtime_hours = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("0.00"))

    basic_wage = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    jac_allowance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    other_cash = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    overtime_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    additional_allowance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    gross_wage = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    pf_deduction = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    esi_deduction = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    other_advance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    festival_advance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    total_deductions = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    net_pay = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    calculation_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["labourer_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["payroll_run", "muster_entry"],
                name="unique_payroll_line_per_run_muster_entry",
            )
        ]

    def __str__(self):
        return f"{self.labourer_name} - {self.payroll_run.run_number}"


class PayrollLineComponent(models.Model):
    """
    Detailed component-wise breakup for each payroll line.
    Useful for Form XIX payslip and future Excel export.
    """

    class Category(models.TextChoices):
        EARNING = "earning", "Earning"
        DEDUCTION = "deduction", "Deduction"

    payroll_line = models.ForeignKey(
        PayrollLine,
        on_delete=models.CASCADE,
        related_name="components",
    )

    component = models.ForeignKey(
        PayComponent,
        on_delete=models.PROTECT,
        related_name="payroll_line_components",
    )

    category = models.CharField(
        max_length=20,
        choices=Category.choices,
    )

    amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    display_order = models.PositiveSmallIntegerField(default=0)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["payroll_line", "category", "display_order", "component__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["payroll_line", "component"],
                name="unique_component_per_payroll_line",
            )
        ]

    def __str__(self):
        return f"{self.payroll_line.labourer_name} - {self.component.name}: {self.amount}"
    

class WhatsAppPayslipLog(models.Model):
    """
    Tracks WhatsApp sending status for one payroll line / payslip.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        DELIVERED = "delivered", "Delivered"
        READ = "read", "Read"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    payroll_line = models.OneToOneField(
        PayrollLine,
        on_delete=models.CASCADE,
        related_name="whatsapp_log",
    )

    payroll_run = models.ForeignKey(
        PayrollRun,
        on_delete=models.CASCADE,
        related_name="whatsapp_logs",
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="whatsapp_payslip_logs",
    )

    labour_code = models.CharField(max_length=50)
    labourer_name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=20, blank=True)

    pdf_filename = models.CharField(max_length=255, blank=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    recipient_id = models.CharField(max_length=30, blank=True)
    webhook_status_raw = models.CharField(max_length=50, blank=True)
    conversation_id = models.CharField(max_length=100, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    failed_at = models.DateTimeField(null=True, blank=True)
    failure_code = models.CharField(max_length=50, blank=True)
    failure_title = models.CharField(max_length=255, blank=True)
    failure_details = models.TextField(blank=True)

    last_webhook_payload = models.JSONField(default=dict, blank=True)

    whatsapp_media_id = models.CharField(max_length=100, blank=True)
    whatsapp_message_id = models.CharField(max_length=100, blank=True)

    error_message = models.TextField(blank=True)

    sent_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "labourer_name"]

    def __str__(self):
        return f"{self.labourer_name} - {self.status}"
    

