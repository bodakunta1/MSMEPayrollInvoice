from django.db import models

# Create your models here.

class SkillGroup(models.Model):
    """
    Skill/designation master.

    Current required values:
    - Unskilled
    - SemiSkilled
    - Skilled
    - Supervisor
    - Safety Supervisor
    """

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    display_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name
    