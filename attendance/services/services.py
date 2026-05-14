from django.db.models import Q

from labour.models import LabourPOAssignment
from attendance.models import MusterEntry


def create_muster_entries_for_cycle(payroll_cycle):
    """
    Creates blank muster entries for all labourers assigned to the PO
    during the payroll cycle period.

    Returns:
        created_count, existing_count
    """

    assignments = (
        LabourPOAssignment.objects.filter(
            company=payroll_cycle.company,
            po=payroll_cycle.po,
            is_active=True,
            assignment_start_date__lte=payroll_cycle.period_end,
        )
        .filter(
            Q(assignment_end_date__isnull=True)
            | Q(assignment_end_date__gte=payroll_cycle.period_start)
        )
        .select_related("labourer", "skill_group", "po", "company")
    )

    created_count = 0
    existing_count = 0

    for assignment in assignments:
        _, created = MusterEntry.objects.get_or_create(
            company=payroll_cycle.company,
            payroll_cycle=payroll_cycle,
            labour_assignment=assignment,
        )

        if created:
            created_count += 1
        else:
            existing_count += 1

    return created_count, existing_count