from django.contrib import admin
from .models import Company

# Register your models here.

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ["name", "gst_number", "phone", "email", "is_active"]
    search_fields = ["name", "legal_name", "gst_number", "pan_number"]
    list_filter = ["is_active"]