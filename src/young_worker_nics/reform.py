"""PolicyEngine UK structural reform: young-worker employer NICs exemption.

Extends the employer Class 1 NICs zero rate to all employees aged
``REFORM_AGE_LOWER``-``REFORM_AGE_UPPER`` (18-24, inclusive): for people in
that age range, employer NICs are zeroed on earnings between the Secondary
Threshold and the Upper Secondary Threshold, with the full employer rate
still applying above the UST. PolicyEngine does not model the under-21 /
apprentice USTs separately, so the UST is read as the Upper Earnings Limit,
with which it is aligned in law.

Under-21s (category M, since April 2015) and apprentices under 25
(category H, since April 2016) are already zero-rated in law, but the
PolicyEngine baseline charges them full employer NICs. The revenue effect of
this reform against the PolicyEngine baseline therefore covers the whole
18-24 population; the pipeline restricts to the 21-24 marginal population
separately.

The replacement formula replicates the baseline ``ni_class_1_employer``
exactly — including the employer-pension-contributions branch gated on
``gov.contrib.policyengine.employer_ni.exempt_employer_pension_contributions``
and the single employer rate above the (weekly, annualised) Secondary
Threshold — and subtracts the relieved band for people in the age range. All
statutory values come from the parameter tree; only the age bounds are
imported from :mod:`young_worker_nics.sources`.

Use with the managed bundle::

    from policyengine.tax_benefit_models.uk import managed_microsimulation
    from young_worker_nics.reform import YOUNG_WORKER_EXEMPTION

    reformed = managed_microsimulation(reform=YOUNG_WORKER_EXEMPTION)
"""

from __future__ import annotations

# The policyengine bundle does not re-export the model API, so defining a
# Variable override requires these direct imports. Both packages are
# exact-pinned by policyengine[uk], the project's only simulation dependency.
from policyengine_core.reforms import Reform
from policyengine_uk.model_api import GBP, WEEKS_IN_YEAR, YEAR, Person, Variable, max_, min_

from .sources import REFORM_AGE_LOWER, REFORM_AGE_UPPER


def create_reform(age_lower: int, age_upper: int) -> type[Reform]:
    """Build the reform for a given (inclusive) eligible age range."""

    class ni_class_1_employer(Variable):
        value_type = float
        entity = Person
        label = "NI Class 1 employer-side contributions"
        definition_period = YEAR
        unit = GBP
        defined_for = "ni_liable"
        reference = "https://www.legislation.gov.uk/ukpga/1992/4/section/9"

        def formula(person, period, parameters):
            class_1 = parameters(period).gov.hmrc.national_insurance.class_1
            earnings = person("ni_class_1_income", period)
            if not parameters(
                period
            ).gov.contrib.policyengine.employer_ni.exempt_employer_pension_contributions:
                added_pension_contributions = person("employer_pension_contributions", period)
                taxed_earnings = earnings + added_pension_contributions
            else:
                taxed_earnings = earnings
            secondary_threshold = class_1.thresholds.secondary_threshold * WEEKS_IN_YEAR
            main_earnings = max_(
                taxed_earnings - secondary_threshold,
                0,
            )
            baseline_liability = class_1.rates.employer * main_earnings

            # Reform: zero rate between the Secondary Threshold and the Upper
            # Secondary Threshold (aligned with the Upper Earnings Limit) for
            # employees in the eligible age range; full rate above the UST.
            upper_secondary_threshold = class_1.thresholds.upper_earnings_limit * WEEKS_IN_YEAR
            age = person("age", period)
            eligible = (age >= age_lower) & (age <= age_upper)
            relieved_band = max_(
                min_(taxed_earnings, upper_secondary_threshold) - secondary_threshold,
                0,
            )
            relieved_amount = class_1.rates.employer * relieved_band
            return baseline_liability - eligible * relieved_amount

    class young_worker_employer_nics_exemption(Reform):
        """Shaped for policyengine_uk's Scenario.from_reform convention.

        That path requires a core-`Reform` subclass (for its isinstance
        check) but instantiates it with ZERO arguments and then calls
        ``apply(tax_benefit_system)`` — unlike core's
        ``Reform.__init__(baseline)`` / ``apply(self)`` signature — so both
        methods are overridden to match the caller.
        """

        name = f"Employer NICs zero rate for employees aged {age_lower}-{age_upper}"
        country_id = "uk"

        def __init__(self):
            # Deliberately does not call super().__init__: policyengine_uk
            # passes the tax-benefit system to apply() instead.
            pass

        def apply(self, tax_benefit_system):
            tax_benefit_system.update_variable(ni_class_1_employer)

    return young_worker_employer_nics_exemption


YOUNG_WORKER_EXEMPTION = create_reform(REFORM_AGE_LOWER, REFORM_AGE_UPPER)
