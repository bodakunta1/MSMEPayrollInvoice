from django.contrib import admin
from .models import Client

# Register your models here.

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ["name", "site_name", "company", "phone", "is_active"]
    search_fields = ["name", "site_name", "gst_number", "phone"]
    list_filter = ["company", "is_active"]