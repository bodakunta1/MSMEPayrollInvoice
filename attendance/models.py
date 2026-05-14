from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from companies.models import Company
from labour.models import LabourPOAssignment
from payroll.models import PayrollCycle

# Create your models here.

class MusterEntry(models.Model):
    """
    Monthly muster entry for one labourer under one PO payroll cycle.

    This stores raw monthly input:
    - working days
    - basic hours
    - overtime hours
    - manual earnings
    - manual deductions

    Payroll calculation will use this data in Phase 4.
    """

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="muster_entries",
    )

    payroll_cycle = models.ForeignKey(
        PayrollCycle,
        on_delete=models.CASCADE,
        related_name="muster_entries",
    )

    labour_assignment = models.ForeignKey(
        LabourPOAssignment,
        on_delete=models.PROTECT,
        related_name="muster_entries",
    )

    working_days = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Number of days worked in this payroll period.",
    )

    basic_hours = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Basic/normal working hours from muster card.",
    )

    overtime_hours = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="OT hours from muster card.",
    )

    other_cash = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Work-related reimbursement paid to labourer.",
    )

    additional_allowance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Fuel/canteen/day/week allowance.",
    )

    other_advance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Mid-month salary advance deduction.",
    )

    festival_advance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Festival advance deduction.",
    )

    remarks = models.TextField(blank=True)

    is_verified = models.BooleanField(
        default=False,
        help_text="Mark after checking against physical muster card.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            "payroll_cycle__period_start",
            "labour_assignment__labourer__full_name",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["payroll_cycle", "labour_assignment"],
                name="unique_muster_entry_per_cycle_assignment",
            )
        ]

    def __str__(self):
        labourer = self.labour_assignment.labourer.full_name
        return f"{labourer} - {self.payroll_cycle.name}"

    @property
    def labourer(self):
        return self.labour_assignment.labourer

    @property
    def skill_group(self):
        return self.labour_assignment.skill_group

    @property
    def po(self):
        return self.payroll_cycle.po

    @property
    def total_manual_earnings(self):
        return self.other_cash + self.additional_allowance

    @property
    def total_manual_deductions(self):
        return self.other_advance + self.festival_advance

    def clean(self):
        errors = {}

        if self.company and self.payroll_cycle:
            if self.payroll_cycle.company != self.company:
                errors["payroll_cycle"] = "Payroll cycle does not belong to selected company."

        if self.company and self.labour_assignment:
            if self.labour_assignment.company != self.company:
                errors["labour_assignment"] = "Labour assignment does not belong to selected company."

        if self.payroll_cycle and self.labour_assignment:
            if self.labour_assignment.po != self.payroll_cycle.po:
                errors["labour_assignment"] = (
                    "Labour assignment PO does not match payroll cycle PO."
                )

            assignment_start = self.labour_assignment.assignment_start_date
            assignment_end = self.labour_assignment.assignment_end_date

            if assignment_start and assignment_start > self.payroll_cycle.period_end:
                errors["labour_assignment"] = (
                    "Labour assignment starts after this payroll period."
                )

            if assignment_end and assignment_end < self.payroll_cycle.period_start:
                errors["labour_assignment"] = (
                    "Labour assignment ended before this payroll period."
                )

            total_period_days = (
                self.payroll_cycle.period_end - self.payroll_cycle.period_start
            ).days + 1

            if self.working_days > total_period_days:
                errors["working_days"] = (
                    f"Working days cannot exceed payroll period days: {total_period_days}."
                )

            if self.payroll_cycle.status in [
                PayrollCycle.Status.APPROVED,
                PayrollCycle.Status.LOCKED,
            ]:
                errors["payroll_cycle"] = (
                    "Cannot edit muster entry after payroll cycle is approved or locked."
                )

        if self.basic_hours < 0:
            errors["basic_hours"] = "Basic hours cannot be negative."

        if self.overtime_hours < 0:
            errors["overtime_hours"] = "Overtime hours cannot be negative."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)