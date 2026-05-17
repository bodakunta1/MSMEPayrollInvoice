from django.contrib import admin, messages
from attendance.services.services import create_muster_entries_for_cycle
from payroll.services.services import calculate_payroll_for_cycle
from django.core.exceptions import ValidationError

# Register your models here.

from .models import (
    DeductionRule,
    JACRule,
    OvertimeRule,
    PayComponent,
    PayrollCycle,
    WageRule,
    PayrollLine,
    PayrollLineComponent,
    PayrollRun,
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
        "generate_payroll",
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
        
    @admin.action(description="Generate / recalculate payroll for selected payroll cycles")
    def generate_payroll(self, request, queryset):

        success_count = 0

        for payroll_cycle in queryset:
            try:
                calculate_payroll_for_cycle(
                    payroll_cycle=payroll_cycle,
                    calculated_by=request.user,
                    recalculate=True,
                )
                success_count += 1
            except ValidationError as error:
                self.message_user(
                    request,
                    f"{payroll_cycle.name}: {error}",
                    level=messages.ERROR,
                )

        if success_count:
            self.message_user(
                request,
                f"Payroll generated successfully for {success_count} cycle(s).",
                level=messages.SUCCESS,
            )
    

@admin.register(PayrollRun)
class PayrollRunAdmin(admin.ModelAdmin):
    list_display = [
        "run_number",
        "company",
        "po",
        "payroll_cycle",
        "status",
        "total_labourers",
        "total_gross_wage",
        "total_deductions",
        "total_net_pay",
        "calculated_at",
    ]

    search_fields = [
        "run_number",
        "company__name",
        "po__po_number",
        "payroll_cycle__name",
    ]

    list_filter = [
        "company",
        "po",
        "status",
    ]

    readonly_fields = [
        "run_number",
        "total_labourers",
        "total_basic_wage",
        "total_jac_allowance",
        "total_other_cash",
        "total_overtime",
        "total_additional_allowance",
        "total_gross_wage",
        "total_pf_deduction",
        "total_esi_deduction",
        "total_other_advance",
        "total_festival_advance",
        "total_deductions",
        "total_net_pay",
        "calculated_by",
        "calculated_at",
    ]


@admin.register(PayrollLine)
class PayrollLineAdmin(admin.ModelAdmin):
    list_display = [
        "payroll_run",
        "labour_code",
        "labourer_name",
        "skill_group_name",
        "working_days",
        "basic_wage",
        "jac_allowance",
        "other_cash",
        "overtime_amount",
        "additional_allowance",
        "gross_wage",
        "pf_deduction",
        "esi_deduction",
        "other_advance",
        "festival_advance",
        "total_deductions",
        "net_pay",
    ]

    search_fields = [
        "payroll_run__run_number",
        "labour_code",
        "labourer_name",
        "skill_group_name",
    ]

    list_filter = [
        "company",
        "payroll_cycle",
        "skill_group_name",
    ]

    readonly_fields = [
        "payroll_run",
        "company",
        "payroll_cycle",
        "labour_assignment",
        "muster_entry",
        "labour_code",
        "labourer_name",
        "skill_group_name",
        "working_days",
        "basic_hours",
        "overtime_hours",
        "basic_wage",
        "jac_allowance",
        "other_cash",
        "overtime_amount",
        "additional_allowance",
        "gross_wage",
        "pf_deduction",
        "esi_deduction",
        "other_advance",
        "festival_advance",
        "total_deductions",
        "net_pay",
        "calculation_notes",
    ]


@admin.register(PayrollLineComponent)
class PayrollLineComponentAdmin(admin.ModelAdmin):
    list_display = [
        "payroll_line",
        "component",
        "category",
        "amount",
        "display_order",
    ]

    search_fields = [
        "payroll_line__labourer_name",
        "payroll_line__payroll_run__run_number",
        "component__name",
        "component__code",
    ]

    list_filter = [
        "category",
        "component",
    ]