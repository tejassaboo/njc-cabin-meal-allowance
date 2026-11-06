"""Writes every bundled fixture under src/plugin/data/ from the hand-written specs below (development only).

The rates are copied by hand from NJC Travel Directive Appendix C and Appendix D, effective 2026-10-01 (days
1-30 rows, printed amounts in hundredths). The trips are fictional. Local times are converted to UTC with
zoneinfo here, once, so neither the tools nor the verifier ever do timezone arithmetic. Nothing is random:
the output is a pure function of this file, and a test checks the committed fixtures still match it.

Run:  uv run python -m plugin.tools_dev.generate
"""

import json
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from pathlib import Path
from zoneinfo import ZoneInfo

DATA = Path(__file__).resolve().parents[1] / "data"
EFFECTIVE = "2026-10-01"

AIRPORTS = {
    "YOW": ("Ottawa", "CA", "America/Toronto"),
    "YYZ": ("Toronto Pearson", "CA", "America/Toronto"),
    "YUL": ("Montreal Trudeau", "CA", "America/Toronto"),
    "YVR": ("Vancouver", "CA", "America/Vancouver"),
    "YXY": ("Whitehorse", "CA", "America/Whitehorse"),
    "LHR": ("London Heathrow", "GB", "Europe/London"),
    "CDG": ("Paris Charles de Gaulle", "FR", "Europe/Paris"),
    "NBO": ("Nairobi Jomo Kenyatta", "KE", "Africa/Nairobi"),
    "HND": ("Tokyo Haneda", "JP", "Asia/Tokyo"),
    "IAD": ("Washington Dulles", "US", "America/New_York"),
    "HNL": ("Honolulu", "US", "Pacific/Honolulu"),
    "ANC": ("Anchorage", "US", "America/Anchorage"),
    "SYD": ("Sydney Kingsford Smith", "AU", "Australia/Sydney"),
    "BER": ("Berlin Brandenburg", "DE", "Europe/Berlin"),
    "MEX": ("Mexico City", "MX", "America/Mexico_City"),
}

# id: (appendix, place, currency, breakfast, lunch, dinner, commercial incidental, private incidental)
RATES = {
    "C-CANADA": ("appendix_c", "Canada (Appendix C, Canada column)", "CAD", 2995, 3055, 6270, 2500, 2500),
    "C-YUKON": ("appendix_c", "Yukon (Appendix C)", "CAD", 2735, 3470, 8130, 2500, 2500),
    "C-NWT": ("appendix_c", "Northwest Territories (Appendix C)", "CAD", 2930, 3475, 7415, 2500, 2500),
    "C-NUNAVUT": ("appendix_c", "Nunavut (Appendix C)", "CAD", 3555, 4220, 10190, 2500, 2500),
    "C-USA": ("appendix_c", "United States of America, continental (Appendix C, Canada amounts in US funds)", "USD", 2995, 3055, 6270, 2500, 2500),
    "C-ALASKA": ("appendix_c", "Alaska (Appendix C, Yukon amounts in US funds)", "USD", 2735, 3470, 8130, 2500, 2500),
    "D-FR-PARIS": ("appendix_d", "France, Paris (Appendix D)", "EUR", 2490, 4520, 5260, 3926, 2454),
    "D-DE-BERLIN": ("appendix_d", "Germany, Berlin (Appendix D)", "EUR", 2865, 4435, 6045, 4270, 2669),
    "D-GB-LONDON": ("appendix_d", "United Kingdom, London (Appendix D)", "GBP", 2335, 4085, 4625, 3534, 2209),
    "D-KE-NAIROBI": ("appendix_d", "Kenya, Nairobi (Appendix D)", "KES", 203000, 412500, 518000, 362720, 226700),
    "D-JP-TOKYO": ("appendix_d", "Japan, Tokyo (Appendix D)", "JPY", 604000, 660000, 982000, 718720, 449200),
    "D-MX-MEXICO-CITY": ("appendix_d", "Mexico, Mexico City (Appendix D, paid in Canadian dollars)", "CAD", 3315, 6545, 8410, 5846, 3654),
    "D-AU-SYDNEY": ("appendix_d", "Australia, Sydney (Appendix D)", "AUD", 4480, 8500, 11615, 7870, 4919),
    "D-US-HAWAII": ("appendix_d", "Hawaii, outside the continental USA (Appendix D, Appendix C amounts in US funds)", "USD", 2995, 3055, 6270, 2500, 2500),
}

TRAVELLERS = {
    "N101": ("Élise Tremblay", "Policy analyst, multilateral affairs"),
    "N102": ("Marc Bélanger", "Survey statistician"),
    "N103": ("Nadia Haddad", "Crop scientist"),
    "N104": ("Samuel Otieno-Clarke", "Hydrologist"),
    "N105": ("Keiko Sato", "Fisheries trade officer"),
    "N106": ("Priya Raman", "Labour-market economist"),
    "N107": ("Owen MacLeod", "Oceanographer"),
    "N108": ("Louise Gagnon", "Northern infrastructure engineer"),
    "N109": ("Hana Whitford", "Marine ecologist"),
    "N110": ("Tomasz Nowak", "Metrology scientist"),
    "N111": ("Rafael Dubois", "Port logistics planner"),
    "N112": ("Ana Lucía Ferreira", "Demographer"),
}

E, P, B = "economy", "premium_economy", "business"

# Each segment: (flight, origin, destination, depart_local, in_air_minutes, cabins_sold, overnight_stop_after).
# Each day: (date, status_start_local or None, status_end_local or None, meals_provided).
SCENARIOS = {
    "paris-assembly": {
        "traveller_id": "N101",
        "request_text": (
            "I'm off to the intergovernmental assembly in Paris. I'm working the morning and heading out just after noon on "
            "the 6th. Toronto to Montreal plus the overnight to Paris is exactly nine hours, which is the business-class "
            "limit, so business both legs please. They serve dinner on the Paris flight but I'd rather eat at the airport, "
            "so please include dinner on the 6th. On the 9th I'm home at 17:59, close enough to claim dinner."
        ),
        "destination": ("Paris", "FR", False, "D-FR-PARIS"),
        "accommodation": "commercial",
        "segments": [
            ("MA 412", "YYZ", "YUL", "2026-12-06T17:45", 75, [E, B], False),
            ("AK 870", "YUL", "CDG", "2026-12-06T20:00", 405, [E, P, B], False),
        ],
        "days": [
            ("2026-12-06", "12:01", None, ["dinner"]),
            ("2026-12-07", None, None, ["breakfast"]),
            ("2026-12-08", None, None, ["lunch"]),
            ("2026-12-09", None, "17:59", ["lunch"]),
        ],
    },
    "london-secondment": {
        "traveller_id": "N102",
        "request_text": (
            "Four days at the UK statistics office. I'm staying with my sister in Croydon, which saves you a hotel, so "
            "please pay me the hotel-rate incidentals. The Ottawa-Toronto hop is barely an hour and the Heathrow flight is "
            "just under seven hours, so I suppose that's economy; I won't argue. I'm home at 18:00 sharp on the 13th."
        ),
        "destination": ("London", "GB", False, "D-GB-LONDON"),
        "accommodation": "private_non_commercial",
        "segments": [
            ("BW 218", "YOW", "YYZ", "2027-01-10T16:05", 65, [E, B], False),
            ("BW 856", "YYZ", "LHR", "2027-01-10T18:10", 416, [E, P, B], False),
        ],
        "days": [
            ("2027-01-10", "14:30", None, []),
            ("2027-01-11", None, None, ["breakfast"]),
            ("2027-01-12", None, None, []),
            ("2027-01-13", None, "18:00", ["lunch"]),
        ],
    },
    "nairobi-crop-institute": {
        "traveller_id": "N103",
        "request_text": (
            "Heading to the crop research institute in Nairobi. It's over fifteen hours of flying in total, and a colleague "
            "flew business on this exact route last year, so business please. The department booked me a night in London on "
            "the way. I land home at noon on the 12th, so count lunch."
        ),
        "destination": ("Nairobi", "KE", False, "D-KE-NAIROBI"),
        "accommodation": "commercial",
        "segments": [
            ("MA 880", "YOW", "LHR", "2027-02-07T19:30", 410, [E, P, B], True),
            ("SV 101", "LHR", "NBO", "2027-02-09T10:15", 505, [E, B], False),
        ],
        "days": [
            ("2027-02-07", "17:00", None, ["dinner"]),
            ("2027-02-08", None, None, ["breakfast"]),
            ("2027-02-09", None, None, ["lunch", "dinner"]),
            ("2027-02-10", None, None, ["lunch"]),
            ("2027-02-11", None, None, []),
            ("2027-02-12", None, "12:00", ["breakfast"]),
        ],
    },
    "nairobi-water-workshop": {
        "traveller_id": "N104",
        "request_text": (
            "Water-monitoring workshop in Nairobi. My manager says the five-hour wait at Heathrow splits the journey into two "
            "short flights, so we're booking economy; can you confirm the allowances? I leave home at 18:00 on the 1st, and "
            "I'm back at 06:59 on the 5th, in time for breakfast with the kids."
        ),
        "destination": ("Nairobi", "KE", False, "D-KE-NAIROBI"),
        "accommodation": "commercial",
        "segments": [
            ("MA 884", "YYZ", "LHR", "2027-03-01T21:40", 400, [E, P, B], False),
            ("SV 103", "LHR", "NBO", "2027-03-02T14:20", 505, [E, B], False),
        ],
        "days": [
            ("2027-03-01", "18:00", None, []),
            ("2027-03-02", None, None, ["breakfast", "dinner"]),
            ("2027-03-03", None, None, []),
            ("2027-03-04", None, None, []),
            ("2027-03-05", None, "06:59", []),
        ],
    },
    "tokyo-trade-talks": {
        "traveller_id": "N105",
        "request_text": (
            "Trade talks in Tokyo. Sakura Pacific doesn't sell business on the Toronto-Tokyo flight, so I guess the rules put "
            "me in economy the whole way; or could you just book business on another carrier? The reception dinner on the "
            "14th is lavish, but I'd like the dinner allowance anyway. I leave home at 07:00 on the 12th."
        ),
        "destination": ("Tokyo", "JP", False, "D-JP-TOKYO"),
        "accommodation": "commercial",
        "segments": [
            ("MA 404", "YOW", "YYZ", "2027-04-12T10:00", 70, [E, B], False),
            ("SP 12", "YYZ", "HND", "2027-04-12T12:40", 790, [E, P], False),
        ],
        "days": [
            ("2027-04-12", "07:00", None, ["dinner"]),
            ("2027-04-13", None, None, ["breakfast", "lunch"]),
            ("2027-04-14", None, None, ["dinner"]),
            ("2027-04-15", None, "18:30", ["dinner"]),
        ],
    },
    "washington-conference": {
        "traveller_id": "N106",
        "request_text": (
            "Labour statistics conference in Washington. Business class please, it's a painfully early flight. Since it's the "
            "States I assume you'll pay the allowances in Canadian dollars at the US government per diem. I'm home at 11:59 "
            "on the 6th, so please add lunch that day."
        ),
        "destination": ("Washington", "US", True, "C-USA"),
        "accommodation": "commercial",
        "segments": [
            ("MA 7341", "YOW", "IAD", "2027-05-04T07:15", 100, [E, B], False),
        ],
        "days": [
            ("2027-05-04", "05:45", None, ["dinner"]),
            ("2027-05-05", None, None, ["lunch"]),
            ("2027-05-06", None, "11:59", []),
        ],
    },
    "honolulu-science-meeting": {
        "traveller_id": "N107",
        "request_text": (
            "Pacific fisheries science meeting in Honolulu. It's just the United States, so I assume economy and the regular "
            "US allowances apply, even though it's over twelve hours from Ottawa with the Vancouver change."
        ),
        "destination": ("Honolulu", "US", False, "D-US-HAWAII"),
        "accommodation": "commercial",
        "segments": [
            ("BW 155", "YOW", "YVR", "2027-06-14T08:00", 305, [E, B], False),
            ("BW 1806", "YVR", "HNL", "2027-06-14T11:20", 360, [E, P, B], False),
        ],
        "days": [
            ("2027-06-14", "06:30", None, ["lunch"]),
            ("2027-06-15", None, None, []),
            ("2027-06-16", None, None, ["breakfast"]),
            ("2027-06-17", None, None, []),
            ("2027-06-18", None, "15:00", ["breakfast"]),
        ],
    },
    "whitehorse-site-review": {
        "traveller_id": "N108",
        "request_text": (
            "Bridge site review in Whitehorse. Door to door it's more than nine hours with the drive to the airport, so "
            "business please. Just use the normal Canada meal rates, the Yukon ones are basically the same. The hotel "
            "breakfast is included on the last day, but I'd like the allowance anyway."
        ),
        "destination": ("Whitehorse", "CA", True, "C-YUKON"),
        "accommodation": "commercial",
        "segments": [
            ("MA 301", "YOW", "YVR", "2027-07-20T07:30", 300, [E, B], False),
            ("MA 8231", "YVR", "YXY", "2027-07-20T10:45", 135, [E], False),
        ],
        "days": [
            ("2027-07-20", "05:30", None, []),
            ("2027-07-21", None, None, ["lunch"]),
            ("2027-07-22", None, "23:15", ["breakfast"]),
        ],
    },
    "sydney-reef-symposium": {
        "traveller_id": "N109",
        "request_text": (
            "Reef symposium in Sydney. The department booked me a night in Vancouver on the way out precisely so the "
            "journey is split into shorter parts, and I'm told that decision 1575 then means economy throughout; I'd "
            "rather you double-check. I was in the air for most of the 3rd, so I don't expect anything for that day. "
            "I'm home at 18:01 on the 6th, just too late for dinner I suppose."
        ),
        "destination": ("Sydney", "AU", False, "D-AU-SYDNEY"),
        "accommodation": "commercial",
        "segments": [
            ("MA 115", "YYZ", "YVR", "2027-09-01T17:30", 300, [E, B], True),
            ("SP 820", "YVR", "HNL", "2027-09-02T09:30", 360, [E, P, B], False),
            ("SP 61", "HNL", "SYD", "2027-09-02T14:05", 600, [E, P, B], False),
        ],
        "days": [
            ("2027-09-01", "15:00", None, []),
            ("2027-09-02", None, None, ["breakfast"]),
            ("2027-09-03", None, None, ["breakfast", "lunch"]),
            ("2027-09-04", None, None, []),
            ("2027-09-05", None, None, ["dinner"]),
            ("2027-09-06", None, "18:01", ["breakfast"]),
        ],
    },
    "berlin-standards-meeting": {
        "traveller_id": "N110",
        "request_text": (
            "Standards meeting in Berlin. The Berlin flight is seven hours and the hop to Montreal under an hour, so "
            "nowhere near nine hours of flying, and Linden Air only sells economy on the long leg anyway, so economy "
            "throughout I expect. I left home at 07:01 on the 18th, which is breakfast time in anyone's book, and I'm "
            "home at 07:00 sharp on the 22nd, too early to count anything."
        ),
        "destination": ("Berlin", "DE", False, "D-DE-BERLIN"),
        "accommodation": "commercial",
        "segments": [
            ("MA 420", "YOW", "YUL", "2027-10-18T15:35", 55, [E, B], False),
            ("LN 702", "YUL", "BER", "2027-10-18T17:35", 421, [E], False),
        ],
        "days": [
            ("2027-10-18", "07:01", None, ["dinner"]),
            ("2027-10-19", None, None, ["breakfast"]),
            ("2027-10-20", None, None, ["lunch"]),
            ("2027-10-21", None, None, []),
            ("2027-10-22", None, "07:00", []),
        ],
    },
    "anchorage-port-study": {
        "traveller_id": "N111",
        "request_text": (
            "Port logistics study in Anchorage. Alaska isn't the lower 48, so this is international travel: business "
            "class on the ten-hour journey please, and the foreign allowance in US dollars. The Vancouver stop is over "
            "an hour and a half, I know, but the flying adds up. I'm home at exactly midnight going into the 12th, so "
            "there's nothing to claim for that day."
        ),
        "destination": ("Anchorage", "US", True, "C-ALASKA"),
        "accommodation": "commercial",
        "segments": [
            ("MA 305", "YOW", "YVR", "2027-08-09T08:10", 305, [E, B], False),
            ("BW 2410", "YVR", "ANC", "2027-08-09T12:00", 210, [E, B], False),
        ],
        "days": [
            ("2027-08-09", "06:00", None, ["lunch"]),
            ("2027-08-10", None, None, []),
            ("2027-08-11", None, None, ["dinner"]),
            ("2027-08-12", None, "00:00", []),
        ],
    },
    "mexico-city-census-exchange": {
        "traveller_id": "N112",
        "request_text": (
            "Census methods exchange in Mexico City. I'm staying with a colleague's family in Coyoacán. Please pay the "
            "allowances in pesos, since Appendix D is for foreign countries, and at the hotel rate for incidentals. I "
            "set off at 18:01 on the 16th, so dinner that night should count, and I'm back at 12:01 on the 20th, which "
            "is past lunch, so don't bother with that."
        ),
        "destination": ("Mexico City", "MX", False, "D-MX-MEXICO-CITY"),
        "accommodation": "private_non_commercial",
        "segments": [
            ("AK 905", "YYZ", "MEX", "2027-11-16T20:15", 345, [E, P, B], False),
        ],
        "days": [
            ("2027-11-16", "18:01", None, []),
            ("2027-11-17", None, None, ["dinner"]),
            ("2027-11-18", None, None, ["lunch"]),
            ("2027-11-19", None, None, []),
            ("2027-11-20", None, "12:01", ["breakfast"]),
        ],
    },
}


def stamp(moment, utc):
    return moment.strftime("%Y-%m-%dT%H:%MZ" if utc else "%Y-%m-%dT%H:%M")


def segments_of(spec):
    built = []
    for index, (flight, origin, destination, depart_local, minutes, cabins, overnight) in enumerate(spec):
        depart = datetime.strptime(depart_local, "%Y-%m-%dT%H:%M").replace(tzinfo=ZoneInfo(AIRPORTS[origin][2]))
        arrive = depart + timedelta(minutes=minutes)
        built.append({
            "segment_id": f"S{index + 1}",
            "flight": flight,
            "origin": origin,
            "destination": destination,
            "depart_local": depart_local,
            "arrive_local": stamp(arrive.astimezone(ZoneInfo(AIRPORTS[destination][2])), False),
            "depart_utc": stamp(depart.astimezone(UTC), True),
            "arrive_utc": stamp(arrive.astimezone(UTC), True),
            "in_air_minutes": minutes,
            "cabins_sold": cabins,
            "connection_after": overnight,  # replaced below once the next departure is known
        })
    for this, following in pairwise(built):
        gap = datetime.strptime(following["depart_utc"], "%Y-%m-%dT%H:%MZ") - datetime.strptime(this["arrive_utc"], "%Y-%m-%dT%H:%MZ")
        this["connection_after"] = {"minutes": int(gap.total_seconds() // 60), "overnight_stop": this["connection_after"]}
    built[-1]["connection_after"] = None
    return built


def scenario_file(scenario_id, spec):
    city, country, domestic, rate_id = spec["destination"]
    return {
        "scenario": scenario_id,
        "request_text": spec["request_text"],
        "traveller_id": spec["traveller_id"],
        "destination": {"city": city, "country": country, "in_canada_or_continental_usa": domestic, "rate_location_id": rate_id},
        "accommodation": spec["accommodation"],
        "outbound": segments_of(spec["segments"]),
        "status_days": [
            {"date": date, "status_start_local": start, "status_end_local": end, "meals_provided": meals}
            for date, start, end, meals in spec["days"]
        ],
    }


def rates_file():
    def row(accommodation, breakfast, lunch, dinner, incidental):
        return {
            "accommodation": accommodation,
            "breakfast_minor": breakfast,
            "lunch_minor": lunch,
            "dinner_minor": dinner,
            "meal_total_minor": breakfast + lunch + dinner,
            "incidental_minor": incidental,
        }

    return {
        rate_id: {
            "appendix": appendix,
            "place": place,
            "currency": currency,
            "effective_date": EFFECTIVE,
            "rows": [row("commercial", b, lunch, d, commercial), row("private_non_commercial", b, lunch, d, private)],
        }
        for rate_id, (appendix, place, currency, b, lunch, d, commercial, private) in RATES.items()
    }


def files():
    """published path under data/ -> its JSON text."""
    out = {
        "rates.json": rates_file(),
        "travellers.json": {key: {"traveller_id": key, "name": name, "role": role} for key, (name, role) in TRAVELLERS.items()},
        "airports.json": {code: {"code": code, "city": city, "country": country, "tz": tz} for code, (city, country, tz) in AIRPORTS.items()},
    }
    for scenario_id, spec in SCENARIOS.items():
        out[f"scenarios/{scenario_id}.json"] = scenario_file(scenario_id, spec)
    return {path: json.dumps(value, indent=1, ensure_ascii=False) + "\n" for path, value in out.items()}


def main():
    for path, text in files().items():
        (DATA / path).write_text(text, encoding="utf-8")
        print(f"wrote data/{path}")


if __name__ == "__main__":
    main()
