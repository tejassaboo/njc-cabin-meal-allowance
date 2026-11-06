# NJC Travel Directive: toy cabin and meal-allowance handbook

Source: National Joint Council of Canada, Travel Directive, version 326, effective October 1, 2025 (https://www.njc-cnm.gc.ca/directive/d10/v326/en), with Appendix C and Appendix D effective October 1, 2026 (https://www.njc-cnm.gc.ca/directive/app_d/en), NJC decision 1575 (December 18, 2013) and NJC communiqué 910 (September 8, 2025), first captured on 2026-11-02. Source drift, recorded honestly: the Directive print page hashed sha256 6fd931c9d361d5300f586ae7918a9b7719d296c395abd2cefea82fc98775af1b on 2026-11-02 and 46cde1bb3e85f5e99eea2989b9c6f38bc20883229603a0333a5766fa72377a49 on 2026-11-06; the Appendix D print page (…/app_d/en?print=1&drv_id=0) hashed 9a96123b14894e80af3095e665b33042b3f451b32511a88f98bca7de24a40661 on 2026-11-02 and 8f9772b345811d53a51f5016e4017b7275f17362912ebcef0a550d396316615d on 2026-11-06. Every bundled Appendix D row was re-read from the 2026-11-06 page and matches it to the cent. Appendix C is no longer served at …/app_c/en (HTTP 404 on 2026-11-06), so its rows (Canada, Yukon, Northwest Territories, Nunavut, the continental USA and Alaska) stay as typed from the 2026-11-02 capture. This handbook is our own paraphrase for a toy task, not the official text. Where the two differ, this handbook governs the task.

You work out one trip's entitlement for a federal public servant leaving Canada: the cabin authorized on each outbound flight segment, and the meal and incidental allowances for the whole trip.

## Policy rules (paraphrased)

1. Module 3 covers overnight travel in Canada and the continental USA. Module 4 covers overnight travel outside Canada and the continental USA.
2. The standard for air travel is economy class.
3. Module 4 only: where available, business class is authorized when continuous air travel exceeds nine hours. Continuous air travel starts at the scheduled flight departure time and ends on arrival at the destination terminal, or at an overnight stop or a layover equivalent to an overnight stop.
4. When business class is not available, any lower available class is authorized (added in the October 2025 version).
5. NJC decision 1575: a trip that would have been over nine continuous hours was rebooked with an overnight stop in a third country. Each part was then under nine continuous hours, so economy applied, and the grievance was denied.
6. A meal allowance is paid for each breakfast, lunch and dinner while in travel status. A meal can be claimed when the traveller is in travel status at the time the meal would usually be taken.
7. No meal allowance is paid for a meal that is provided.
8. An incidental expense allowance is paid for each day or part day in travel status on overnight travel.
9. Rates come from Appendix C (Canada and the continental USA) or Appendix D (other countries). USA amounts are the Canadian amounts paid in US dollars; Alaska counts as continental USA and follows the Yukon amounts. Hawaii and other US locations outside the continental USA are in Appendix D, but use the Appendix C amounts in US dollars. Some Appendix D countries are paid in Canadian dollars. Yukon, the Northwest Territories and Nunavut have their own Appendix C columns.
10. Appendix D incidentals depend on the accommodation: in commercial accommodation they are 32% of the meal total, in private non-commercial accommodation 20%. Appendix C incidentals are the same for both.

## Clarifications (toy rules)

These settle every point where the real text is vague. The checker enforces exactly these.

- **C1 Continuous blocks.** Cut the outbound journey at every connection whose overnight_stop is true. Each remaining run of segments is one continuous block. A block's minutes are the in_air_minutes of its segments plus the minutes of the connections inside it. This equals the last segment's arrive_utc minus the first segment's depart_utc. Ordinary connections count toward continuous air travel, however long they are. Only an overnight stop breaks it (overnight_stop true; the fixture also uses it for a layover the employer deemed equivalent to an overnight stop). longest_continuous_air_minutes is the largest block.
- **C2 Threshold.** "Exceeds nine hours" means a block of more than 540 minutes. Exactly 540 does not qualify, and 541 does.
- **C3 Per segment.** Each segment takes the cabin of its own block. When the trip is Module 4 (destination.in_canada_or_continental_usa is false) and the block exceeds 540 minutes, the segment qualifies: it is authorized business if it sells business, else as C4 says. Every other segment is economy. A short segment inside a long block counts as part of that block.
- **C4 Business not sold.** If a qualifying segment does not sell business, rule 4 allows any lower class; this toy picks the highest class the segment does sell below business: premium_economy if sold, else economy. Never move to another flight or carrier; the itinerary is fixed.
- **C5 Module 3.** In Canada or the continental USA every segment is economy, however long.
- **C6 Meal clock.** The source gives no meal times. In this toy, breakfast is at 07:00, lunch at 12:00 and dinner at 18:00, in the day's local clock. A meal is in travel status when status_start_local ≤ meal time ≤ status_end_local; both ends count. A null start means status began on an earlier day, and a null end means it continues past midnight. Starting at 07:00 earns breakfast and starting at 07:01 does not. Ending at 18:00 earns dinner and ending at 17:59 does not. Each entry of status_days is one calendar day in the traveller's local time, however long or short time zones or the date line make it; count the days as listed.
- **C7 Provided meals.** A meal listed in meals_provided earns nothing, whatever the request says.
- **C8 One rate row.** Every day of the trip, the departure and return days included, uses the destination's row: get_allowance_rates(destination.rate_location_id). Within it, use the row for the trip's accommodation. Pay in that row's currency. Every amount is in hundredths of that currency, as the tables print them, even yen and shillings.
- **C9 Amounts.** meal_allowance_minor is the sum over all status days of the claimable meals' row amounts. incidental_allowance_minor is the number of status days times the row's incidental_minor; a part day counts as a whole day. total_minor is their sum. Nothing is pro-rated or rounded.
- **C10 Facts.** The structured fields are the facts. The request text may ask for things policy forbids, so apply the policy, not the wish. All times and minutes are precomputed, so never do timezone arithmetic.

## Rules not in scope

The following parts of the Directive are deliberately ignored:

- the return journey's cabin (the status days still cover the return);
- stays over 30 days (the 75% reductions from day 31 and the 50% meal rate from day 121);
- the rule that incidentals follow "the location where the day commences" on days spent in more than one country (C8 replaces it);
- meals reimbursed on receipts, including those above the allowance, supplements to provided meals and Appendix D locations marked with an asterisk;
- shift workers' meal sequence;
- Modules 1 and 2 (no overnight stay);
- accommodation, the private accommodation allowance, transportation other than the class of air travel, rail, rental cars, kilometric rates and weekend travel home;
- the "comprehensive review of the circumstances" that decision 1575 calls for, which is a judgment;
- daily comprehensive allowances and Foreign Services Directives allowances.

## Step plan (submit by step 5)

You have 6 steps. Each tool call costs one, and the last step may not call tools.

1. Call get_trip_request with the task's scenario.
2. Call get_allowance_rates with destination.rate_location_id.
3. Apply C1–C9 and call submit with segment_cabins (every outbound segment once), longest_continuous_air_minutes, currency, meal_allowance_minor, incidental_allowance_minor and total_minor.
