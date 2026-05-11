from django.contrib import admin
from .models import PurchaseOrder, POLabourLimit

# Register your models here.

class POLabourLimitInline(admin.TabularInline):
    model = POLabourLimit
    extra = 1


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = [
        "po_number",
        "company",
        "client",
        "location",
        "contract_start_date",
        "contract_end_date",
        "total_labour_limit",
        "status",
    ]

    search_fields = [
        "po_number",
        "title",
        "work_description",
        "location",
        "department",
    ]

    list_filter = ["company", "client", "status", "location"]
    date_hierarchy = "contract_start_date"

    inlines = [POLabourLimitInline]