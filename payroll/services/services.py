from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from attendance.models import MusterEntry
from payroll.models import (
    CalculationMethod,
    DeductionRule,
    JACRule,
    OvertimeRule,
    PayComponent,
    PayrollCycle,
    PayrollLine,
    PayrollLineComponent,
    PayrollRun,
    PercentageBase,
    WageRule,
)


ZERO = Decimal("0.00")


def money(value):
    if value is None:
        value = ZERO

    if not isinstance(value, Decimal):
        value = Decimal(str(value))

    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def get_component(company, code):
    try:
        return PayComponent.objects.get(
            company=company,
            code=code,
            is_active=True,
        )
    except PayComponent.DoesNotExist:
        raise ValidationError(f"Missing active pay component: {code}")


def _date_in_rule_period(queryset, payroll_cycle):
    effective_date = payroll_cycle.period_start

    return queryset.filter(
        is_active=True,
        effective_from__lte=effective_date,
    ).filter(
        Q(effective_to__isnull=True) | Q(effective_to__gte=effective_date)
    )


def get_wage_rule(company, po, skill_group, component_code, payroll_cycle):
    component = get_component(company, component_code)

    base_qs = WageRule.objects.filter(
        company=company,
        skill_group=skill_group,
        component=component,
    )

    base_qs = _date_in_rule_period(base_qs, payroll_cycle)

    po_rule = base_qs.filter(po=po).order_by("-effective_from").first()
    if po_rule:
        return po_rule

    return base_qs.filter(po__isnull=True).order_by("-effective_from").first()


def get_deduction_rule(company, po, skill_group, component_code, payroll_cycle):
    component = get_component(company, component_code)

    base_qs = DeductionRule.objects.filter(
        company=company,
        skill_group=skill_group,
        component=component,
    )

    base_qs = _date_in_rule_period(base_qs, payroll_cycle)

    po_rule = base_qs.filter(po=po).order_by("-effective_from").first()
    if po_rule:
        return po_rule

    return base_qs.filter(po__isnull=True).order_by("-effective_from").first()


def get_overtime_rule(company, po, skill_group, payroll_cycle):
    base_qs = OvertimeRule.objects.filter(
        company=company,
        skill_group=skill_group,
    )

    base_qs = _date_in_rule_period(base_qs, payroll_cycle)

    po_rule = base_qs.filter(po=po).order_by("-effective_from").first()
    if po_rule:
        return po_rule

    return base_qs.filter(po__isnull=True).order_by("-effective_from").first()


def get_jac_rule(company, po, skill_group, payroll_cycle):
    base_qs = JACRule.objects.filter(company=company)
    base_qs = _date_in_rule_period(base_qs, payroll_cycle)

    # Priority order:
    # 1. PO + skill
    # 2. PO + all skills
    # 3. all POs + skill
    # 4. all POs + all skills
    candidates = [
        base_qs.filter(po=po, skill_group=skill_group),
        base_qs.filter(po=po, skill_group__isnull=True),
        base_qs.filter(po__isnull=True, skill_group=skill_group),
        base_qs.filter(po__isnull=True, skill_group__isnull=True),
    ]

    for qs in candidates:
        rule = qs.order_by("-effective_from").first()
        if rule:
            return rule

    return None


def calculate_rule_amount(rule, muster_entry, base_values=None):
    if not rule:
        return ZERO

    base_values = base_values or {}

    method = rule.calculation_method

    if method == CalculationMethod.MANUAL:
        return ZERO

    if method == CalculationMethod.FIXED_MONTHLY:
        return money(rule.amount)

    if method == CalculationMethod.PER_DAY:
        return money(rule.amount * muster_entry.working_days)

    if method == CalculationMethod.PER_HOUR:
        return money(rule.amount * muster_entry.basic_hours)

    if method == CalculationMethod.PERCENTAGE:
        base_amount = get_percentage_base_amount(rule, base_values)
        return money(base_amount * rule.percentage / Decimal("100"))

    return ZERO


def get_percentage_base_amount(rule, base_values):
    percentage_base = rule.percentage_base

    if percentage_base == PercentageBase.BASIC:
        return base_values.get("basic_wage", ZERO)

    if percentage_base == PercentageBase.BASIC_PLUS_ALLOWANCES:
        return (
            base_values.get("basic_wage", ZERO)
            + base_values.get("jac_allowance", ZERO)
            + base_values.get("other_cash", ZERO)
            + base_values.get("additional_allowance", ZERO)
        )

    if percentage_base == PercentageBase.GROSS:
        return base_values.get("gross_wage", ZERO)

    if percentage_base == PercentageBase.DAILY_RATE_WORKING_DAYS:
        return base_values.get("basic_wage", ZERO)

    if percentage_base == PercentageBase.COMPONENT:
        component_amounts = base_values.get("component_amounts", {})
        if rule.base_component_id:
            return component_amounts.get(rule.base_component_id, ZERO)

    return ZERO


def calculate_deduction(rule, muster_entry, base_values):
    amount = calculate_rule_amount(rule, muster_entry, base_values)

    if rule and rule.monthly_cap is not None:
        amount = min(amount, rule.monthly_cap)

    return money(amount)


def calculate_overtime_amount(rule, muster_entry):
    if not rule:
        return ZERO

    if muster_entry.overtime_hours <= 0:
        return ZERO

    if rule.rate_type == OvertimeRule.RateType.PER_HOUR:
        return money(rule.rate * muster_entry.overtime_hours)

    if rule.rate_type == OvertimeRule.RateType.FIXED_AMOUNT:
        return money(rule.rate)

    return ZERO


def create_component_line(payroll_line, component_code, category, amount, notes=""):
    component = get_component(payroll_line.company, component_code)

    return PayrollLineComponent.objects.create(
        payroll_line=payroll_line,
        component=component,
        category=category,
        amount=money(amount),
        display_order=component.display_order,
        notes=notes,
    )


def calculate_single_muster_entry(payroll_run, muster_entry):
    company = muster_entry.company
    payroll_cycle = muster_entry.payroll_cycle
    po = payroll_cycle.po
    assignment = muster_entry.labour_assignment
    labourer = assignment.labourer
    skill_group = assignment.skill_group

    notes = []

    basic_rule = get_wage_rule(
        company=company,
        po=po,
        skill_group=skill_group,
        component_code="BASIC",
        payroll_cycle=payroll_cycle,
    )

    if not basic_rule:
        raise ValidationError(
            f"Missing Basic Wage rule for {skill_group.name}."
        )

    basic_wage = calculate_rule_amount(basic_rule, muster_entry)

    other_cash = money(muster_entry.other_cash)
    additional_allowance = money(muster_entry.additional_allowance)

    overtime_rule = get_overtime_rule(
        company=company,
        po=po,
        skill_group=skill_group,
        payroll_cycle=payroll_cycle,
    )

    overtime_amount = calculate_overtime_amount(overtime_rule, muster_entry)

    if muster_entry.overtime_hours > 0 and not overtime_rule:
        notes.append(f"OT hours entered but no OT rule found for {skill_group.name}.")

    jac_allowance = ZERO

    if assignment.jac_eligible:
        jac_rule = get_jac_rule(
            company=company,
            po=po,
            skill_group=skill_group,
            payroll_cycle=payroll_cycle,
        )

        if jac_rule:
            jac_allowance = calculate_rule_amount(jac_rule, muster_entry)
        else:
            notes.append("JAC eligible but no JAC rule found.")

    gross_wage = money(
        basic_wage
        + jac_allowance
        + other_cash
        + overtime_amount
        + additional_allowance
    )

    component_amounts = {}

    basic_component = get_component(company, "BASIC")
    component_amounts[basic_component] = basic_wage

    try:
        jac_component = get_component(company, "JAC")
        component_amounts[jac_component] = jac_allowance
    except ValidationError:
        pass

    base_values = {
        "basic_wage": basic_wage,
        "jac_allowance": jac_allowance,
        "other_cash": other_cash,
        "overtime_amount": overtime_amount,
        "additional_allowance": additional_allowance,
        "gross_wage": gross_wage,
        "component_amounts": component_amounts,
    }

    pf_rule = get_deduction_rule(
        company=company,
        po=po,
        skill_group=skill_group,
        component_code="PF_DED",
        payroll_cycle=payroll_cycle,
    )

    esi_rule = get_deduction_rule(
        company=company,
        po=po,
        skill_group=skill_group,
        component_code="ESI_DED",
        payroll_cycle=payroll_cycle,
    )

    pf_deduction = calculate_deduction(pf_rule, muster_entry, base_values)
    esi_deduction = calculate_deduction(esi_rule, muster_entry, base_values)

    if not pf_rule:
        notes.append(f"No PF deduction rule found for {skill_group.name}.")

    if not esi_rule:
        notes.append(f"No ESI deduction rule found for {skill_group.name}.")

    other_advance = money(muster_entry.other_advance)
    festival_advance = money(muster_entry.festival_advance)

    total_deductions = money(
        pf_deduction
        + esi_deduction
        + other_advance
        + festival_advance
    )

    net_pay = money(gross_wage - total_deductions)

    payroll_line = PayrollLine.objects.create(
        payroll_run=payroll_run,
        company=company,
        payroll_cycle=payroll_cycle,
        labour_assignment=assignment,
        muster_entry=muster_entry,

        labour_code=labourer.labour_code,
        labourer_name=labourer.full_name,
        skill_group_name=skill_group.name,

        working_days=muster_entry.working_days,
        basic_hours=muster_entry.basic_hours,
        overtime_hours=muster_entry.overtime_hours,

        basic_wage=basic_wage,
        jac_allowance=jac_allowance,
        other_cash=other_cash,
        overtime_amount=overtime_amount,
        additional_allowance=additional_allowance,

        gross_wage=gross_wage,

        pf_deduction=pf_deduction,
        esi_deduction=esi_deduction,
        other_advance=other_advance,
        festival_advance=festival_advance,

        total_deductions=total_deductions,
        net_pay=net_pay,

        calculation_notes="\n".join(notes),
    )

    create_component_line(
        payroll_line,
        basic_component,
        PayrollLineComponent.Category.EARNING,
        basic_wage,
        notes="Basic wage calculated from wage rule.",
    )

    create_component_line(
        payroll_line,
        jac_component,
        PayrollLineComponent.Category.EARNING,
        jac_allowance,
        notes="Applied only if labour assignment is JAC eligible.",
    )

    create_component_line(
        payroll_line,
        get_component(company, "OTHER_CASH"),
        PayrollLineComponent.Category.EARNING,
        other_cash,
        notes="Manual reimbursement from muster entry.",
    )

    create_component_line(
        payroll_line,
        get_component(company, "OVERTIME"),
        PayrollLineComponent.Category.EARNING,
        overtime_amount,
        notes="OT calculated from OT rule.",
    )

    create_component_line(
        payroll_line,
        get_component(company, "ADDL_ALLOW"),
        PayrollLineComponent.Category.EARNING,
        additional_allowance,
        notes="Manual additional allowance from muster entry.",
    )

    create_component_line(
        payroll_line,
        get_component(company, "PF_DED"),
        PayrollLineComponent.Category.DEDUCTION,
        pf_deduction,
        notes="PF deduction calculated from deduction rule.",
    )

    create_component_line(
        payroll_line,
        get_component(company, "ESI_DED"),
        PayrollLineComponent.Category.DEDUCTION,
        esi_deduction,
        notes="ESI deduction calculated from deduction rule.",
    )

    create_component_line(
        payroll_line,
        get_component(company, "OTHER_ADV"),
        PayrollLineComponent.Category.DEDUCTION,
        other_advance,
        notes="Manual other advance from muster entry.",
    )

    create_component_line(
        payroll_line,
        get_component(company, "FEST_ADV"),
        PayrollLineComponent.Category.DEDUCTION,
        festival_advance,
        notes="Manual festival advance from muster entry.",
    )

    return payroll_line


@transaction.atomic
def calculate_payroll_for_cycle(payroll_cycle, calculated_by=None, recalculate=True):
    if payroll_cycle.status == PayrollCycle.Status.LOCKED:
        raise ValidationError("Cannot calculate payroll for a locked payroll cycle.")

    if payroll_cycle.status == PayrollCycle.Status.APPROVED:
        raise ValidationError("Cannot recalculate an approved payroll cycle.")

    muster_entries = (
        MusterEntry.objects.filter(
            company=payroll_cycle.company,
            payroll_cycle=payroll_cycle,
        )
        .select_related(
            "company",
            "payroll_cycle",
            "payroll_cycle__po",
            "labour_assignment",
            "labour_assignment__labourer",
            "labour_assignment__skill_group",
        )
        .order_by("labour_assignment__labourer__full_name")
    )

    if not muster_entries.exists():
        raise ValidationError(
            "No muster entries found. Create muster entries before calculating payroll."
        )

    payroll_run, created = PayrollRun.objects.get_or_create(
        company=payroll_cycle.company,
        po=payroll_cycle.po,
        payroll_cycle=payroll_cycle,
        defaults={
            "status": PayrollRun.Status.DRAFT,
            "calculated_by": calculated_by,
        },
    )

    if payroll_run.status == PayrollRun.Status.LOCKED:
        raise ValidationError("Cannot recalculate a locked payroll run.")

    if payroll_run.status == PayrollRun.Status.APPROVED:
        raise ValidationError("Cannot recalculate an approved payroll run.")

    if recalculate:
        payroll_run.lines.all().delete()

    for muster_entry in muster_entries:
        calculate_single_muster_entry(
            payroll_run=payroll_run,
            muster_entry=muster_entry,
        )

    totals = payroll_run.lines.aggregate(
        total_basic_wage=Sum("basic_wage"),
        total_jac_allowance=Sum("jac_allowance"),
        total_other_cash=Sum("other_cash"),
        total_overtime=Sum("overtime_amount"),
        total_additional_allowance=Sum("additional_allowance"),
        total_gross_wage=Sum("gross_wage"),
        total_pf_deduction=Sum("pf_deduction"),
        total_esi_deduction=Sum("esi_deduction"),
        total_other_advance=Sum("other_advance"),
        total_festival_advance=Sum("festival_advance"),
        total_deductions=Sum("total_deductions"),
        total_net_pay=Sum("net_pay"),
    )

    payroll_run.total_labourers = payroll_run.lines.count()
    payroll_run.total_basic_wage = money(totals["total_basic_wage"])
    payroll_run.total_jac_allowance = money(totals["total_jac_allowance"])
    payroll_run.total_other_cash = money(totals["total_other_cash"])
    payroll_run.total_overtime = money(totals["total_overtime"])
    payroll_run.total_additional_allowance = money(totals["total_additional_allowance"])
    payroll_run.total_gross_wage = money(totals["total_gross_wage"])
    payroll_run.total_pf_deduction = money(totals["total_pf_deduction"])
    payroll_run.total_esi_deduction = money(totals["total_esi_deduction"])
    payroll_run.total_other_advance = money(totals["total_other_advance"])
    payroll_run.total_festival_advance = money(totals["total_festival_advance"])
    payroll_run.total_deductions = money(totals["total_deductions"])
    payroll_run.total_net_pay = money(totals["total_net_pay"])

    payroll_run.status = PayrollRun.Status.CALCULATED
    payroll_run.calculated_by = calculated_by
    payroll_run.calculated_at = timezone.now()
    payroll_run.save()

    payroll_cycle.status = PayrollCycle.Status.CALCULATED
    payroll_cycle.save(update_fields=["status", "updated_at"])

    return payroll_run