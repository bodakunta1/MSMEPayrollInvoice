from django.contrib import admin
from .models import SkillGroup

# Register your models here.

@admin.register(SkillGroup)
class SkillGroupAdmin(admin.ModelAdmin):
    list_display = ["name", "display_order", "is_active"]
    search_fields = ["name"]
    list_filter = ["is_active"]
    ordering = ["display_order", "name"]