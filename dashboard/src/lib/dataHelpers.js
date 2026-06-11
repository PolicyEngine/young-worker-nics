/**
 * Accessors for the young_worker_nics_results.json payload.
 *
 * Deliberately no fallbacks: if a field is missing the consumer throws
 * visibly rather than rendering placeholders.
 */

export function getStatic(data) {
  return data.reform.static;
}

export function getPassThroughScenarios(data) {
  return data.reform.pass_through;
}

export function getEmploymentScenarios(data) {
  return data.reform.employment;
}

export function getBaseline(data) {
  return data.baseline;
}

export function getNicsParameters(data) {
  return data.nics_parameters;
}

export function getCalculatorProfile(data, age, region, renter) {
  const key = `age${age}|${region}|rent${renter ? 1 : 0}`;
  const profile = data.person_calculator.profiles[key];
  if (!profile) {
    throw new Error(`profile ${key} missing from young_worker_nics_results.json`);
  }
  return profile;
}
