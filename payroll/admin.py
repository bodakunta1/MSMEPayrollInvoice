from django.contrib import admin, messages
from attendance.services.services import create_muster_entries_for_cycle

# Register your models here.

from .models import (
    DeductionRule,
    JACRule,
    OvertimeRule,
    PayComponent,
    PayrollCycle,
    WageRule,
)


@admin.register(PayComponent)
class PayComponentAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "code",
        "company",
        "category",
        "default_calculation_method",
        "is_statutory",
        "show_on_payslip",
        "display_order",
        "is_active",
    ]

    search_fields = [
        "name",
        "code",
        "company__name",
    ]

    list_filter = [
        "company",
        "category",
        "default_calculation_method",
        "is_statutory",
        "show_on_payslip",
        "is_active",
    ]


@admin.register(WageRule)
class WageRuleAdmin(admin.ModelAdmin):
    list_display = [
        "company",
        "po",
        "skill_group",
        "component",
        "calculation_method",
        "amount",
        "percentage",
        "effective_from",
        "effective_to",
        "is_active",
    ]

    search_fields = [
        "company__name",
        "po__po_number",
        "skill_group__name",
        "component__name",
    ]

    list_filter = [
        "company",
        "po",
        "skill_group",
        "component",
        "calculation_method",
        "is_active",
    ]

    date_hierarchy = "effective_from"


@admin.register(DeductionRule)
class DeductionRuleAdmin(admin.ModelAdmin):
    list_display = [
        "company",
        "po",
        "skill_group",
        "component",
        "calculation_method",
        "amount",
        "percentage",
        "percentage_base",
        "monthly_cap",
        "effective_from",
        "effective_to",
        "is_active",
    ]

    search_fields = [
        "company__name",
        "po__po_number",
        "skill_group__name",
        "component__name",
    ]

    list_filter = [
        "company",
        "po",
        "skill_group",
        "component",
        "calculation_method",
        "percentage_base",
        "is_active",
    ]

    date_hierarchy = "effective_from"


@admin.register(OvertimeRule)
class OvertimeRuleAdmin(admin.ModelAdmin):
    list_display = [
        "company",
        "po",
        "skill_group",
        "rate_type",
        "rate",
        "effective_from",
        "effective_to",
        "is_active",
    ]

    search_fields = [
        "company__name",
        "po__po_number",
        "skill_group__name",
    ]

    list_filter = [
        "company",
        "po",
        "skill_group",
        "rate_type",
        "is_active",
    ]

    date_hierarchy = "effective_from"


@admin.register(JACRule)
class JACRuleAdmin(admin.ModelAdmin):
    list_display = [
        "company",
        "po",
        "skill_group",
        "calculation_method",
        "amount",
        "effective_from",
        "effective_to",
        "is_active",
    ]

    search_fields = [
        "company__name",
        "po__po_number",
        "skill_group__name",
    ]

    list_filter = [
        "company",
        "po",
        "skill_group",
        "calculation_method",
        "is_active",
    ]

    date_hierarchy = "effective_from"


@admin.register(PayrollCycle)
class PayrollCycleAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "company",
        "po",
        "period_start",
        "period_end",
        "pay_date",
        "status",
    ]

    search_fields = [
        "name",
        "company__name",
        "po__po_number",
    ]

    list_filter = [
        "company",
        "po",
        "status",
    ]

    date_hierarchy = "period_start"

    actions = [
        "create_muster_entries",
    ]

    @admin.action(description="Create muster entries for selected payroll cycles")
    def create_muster_entries(self, request, queryset):
        
        total_created = 0
        total_existing = 0

        for payroll_cycle in queryset:
            created_count, existing_count = create_muster_entries_for_cycle(
                payroll_cycle=payroll_cycle
            )
            total_created += created_count
            total_existing += existing_count

        self.message_user(
            request,
            (
                f"Muster entries created: {total_created}. "
                f"Already existing entries skipped: {total_existing}."
            ),
            level=messages.SUCCESS,
        )