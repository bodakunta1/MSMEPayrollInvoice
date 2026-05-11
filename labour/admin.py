from django.contrib import admin
from .models import Labour, LabourPOAssignment

# Register your models here.

class LabourPOAssignmentInline(admin.TabularInline):
    model = LabourPOAssignment
    extra = 0
    fields = [
        "po",
        "skill_group",
        "assignment_start_date",
        "assignment_end_date",
        "jac_eligible",
        "is_active",
    ]


@admin.register(Labour)
class LabourAdmin(admin.ModelAdmin):
    list_display = [
        "labour_code",
        "full_name",
        "company",
        "default_skill_group",
        "mobile_number",
        "masked_aadhaar",
        "is_active",
    ]

    search_fields = [
        "labour_code",
        "full_name",
        "father_name",
        "mobile_number",
        "whatsapp_number",
        "aadhaar_number",
        "uan_number",
        "esi_number",
    ]

    list_filter = [
        "company",
        "default_skill_group",
        "is_active",
    ]

    readonly_fields = ["masked_aadhaar"]
    inlines = [LabourPOAssignmentInline]


@admin.register(LabourPOAssignment)
class LabourPOAssignmentAdmin(admin.ModelAdmin):
    list_display = [
        "labourer",
        "company",
        "po",
        "skill_group",
        "assignment_start_date",
        "assignment_end_date",
        "jac_eligible",
        "is_active",
    ]

    search_fields = [
        "labourer__full_name",
        "labourer__labour_code",
        "po__po_number",
    ]

    list_filter = [
        "company",
        "po",
        "skill_group",
        "jac_eligible",
        "is_active",
    ]