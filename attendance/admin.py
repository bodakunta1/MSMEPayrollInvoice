from django.contrib import admin
from .models import MusterEntry

# Register your models here.

@admin.register(MusterEntry)
class MusterEntryAdmin(admin.ModelAdmin):
    list_display = [
        "payroll_cycle",
        "labourer_name",
        "skill_group_name",
        "working_days",
        "basic_hours",
        "overtime_hours",
        "other_cash",
        "additional_allowance",
        "other_advance",
        "festival_advance",
        "is_verified",
    ]

    list_editable = [
        "working_days",
        "basic_hours",
        "overtime_hours",
        "other_cash",
        "additional_allowance",
        "other_advance",
        "festival_advance",
        "is_verified",
    ]

    search_fields = [
        "payroll_cycle__name",
        "labour_assignment__labourer__full_name",
        "labour_assignment__labourer__labour_code",
        "labour_assignment__po__po_number",
    ]

    list_filter = [
        "company",
        "payroll_cycle",
        "labour_assignment__skill_group",
        "is_verified",
    ]

    readonly_fields = [
        "labourer_name",
        "skill_group_name",
        "po_number",
        "total_manual_earnings",
        "total_manual_deductions",
    ]

    fieldsets = (
        (
            "Muster Reference",
            {
                "fields": (
                    "company",
                    "payroll_cycle",
                    "labour_assignment",
                    "labourer_name",
                    "skill_group_name",
                    "po_number",
                )
            },
        ),
        (
            "Attendance / Hours",
            {
                "fields": (
                    "working_days",
                    "basic_hours",
                    "overtime_hours",
                )
            },
        ),
        (
            "Manual Earnings",
            {
                "fields": (
                    "other_cash",
                    "additional_allowance",
                    "total_manual_earnings",
                )
            },
        ),
        (
            "Manual Deductions",
            {
                "fields": (
                    "other_advance",
                    "festival_advance",
                    "total_manual_deductions",
                )
            },
        ),
        (
            "Verification",
            {
                "fields": (
                    "is_verified",
                    "remarks",
                )
            },
        ),
    )

    @admin.display(description="Labourer", ordering="labour_assignment__labourer__full_name")
    def labourer_name(self, obj):
        return obj.labour_assignment.labourer.full_name

    @admin.display(description="Skill Group", ordering="labour_assignment__skill_group__name")
    def skill_group_name(self, obj):
        return obj.labour_assignment.skill_group.name

    @admin.display(description="PO Number", ordering="payroll_cycle__po__po_number")
    def po_number(self, obj):
        return obj.payroll_cycle.po.po_number