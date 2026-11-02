"""Each tool's and task's typed input and output (see nanoagent.plugin.v0001.contract): declarations only."""

from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from slimconfig import Output


class Tool(Enum):
    GET_TRIP_REQUEST = "get_trip_request"
    GET_ALLOWANCE_RATES = "get_allowance_rates"
    COMPUTE_NJC_ENTITLEMENT = "compute_njc_entitlement"


class Task(Enum):
    NJC_TRIP_ENTITLEMENT = "njc-trip-entitlement"


class NjcScenario(Enum):
    """One trip per member; its facts are bundled with the plugin."""

    PARIS_ASSEMBLY = "paris-assembly"
    LONDON_SECONDMENT = "london-secondment"
    NAIROBI_OVERNIGHT_HEATHROW = "nairobi-overnight-heathrow"
    NAIROBI_DAYTIME_WAIT = "nairobi-daytime-wait"
    TOKYO_NO_BUSINESS = "tokyo-no-business"
    WASHINGTON_CONFERENCE = "washington-conference"
    HONOLULU_SCIENCE_MEETING = "honolulu-science-meeting"
    WHITEHORSE_SITE_REVIEW = "whitehorse-site-review"


class NjcCabin(Enum):
    """The cabins a ticket may be sold and authorized in, lowest first (first class is never authorized)."""

    ECONOMY = "economy"
    PREMIUM_ECONOMY = "premium_economy"
    BUSINESS = "business"


class Meal(Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"


class Accommodation(Enum):
    """Where the traveller sleeps at the destination: it picks the allowance row (handbook C8)."""

    COMMERCIAL = "commercial"
    PRIVATE_NON_COMMERCIAL = "private_non_commercial"


class Appendix(Enum):
    """The NJC allowance table a rate row comes from."""

    APPENDIX_C = "appendix_c"
    APPENDIX_D = "appendix_d"


class Currency(Enum):
    """ISO 4217 codes. Every amount in this plugin is in hundredths of its currency, as the tables print it."""

    CAD = "CAD"
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    JPY = "JPY"
    KES = "KES"
    AUD = "AUD"
    MXN = "MXN"


@dataclass
class ScenarioInput(Output):
    scenario: Annotated[NjcScenario, "Which trip to work, e.g. paris-assembly"]


@dataclass
class Traveller(Output):
    traveller_id: Annotated[str, "Traveller id, e.g. N104"]
    name: Annotated[str, "The traveller's full name (descriptive only)"]
    role: Annotated[str, "The traveller's job (descriptive only)"]


@dataclass
class Destination(Output):
    city: Annotated[str, "Destination city (descriptive only)"]
    country: Annotated[str, "ISO 3166-1 alpha-2 country code of the destination, e.g. KE"]
    in_canada_or_continental_usa: Annotated[
        bool, "True when the destination is in Canada or the 48 contiguous US states and DC; false elsewhere, Hawaii included"
    ]
    rate_location_id: Annotated[str, "The allowance-table row to use, e.g. D-KE-NAIROBI; pass it to get_allowance_rates"]


@dataclass
class Connection(Output):
    minutes: Annotated[int, "Minutes from this segment's scheduled arrival to the next segment's scheduled departure"]
    overnight_stop: Annotated[
        bool,
        "True when the traveller stops overnight at this connection point (an overnight stop, or a layover the employer "
        "has deemed equivalent to one); false for an ordinary connection, however long",
    ]


@dataclass
class Segment(Output):
    segment_id: Annotated[str, "Segment id, e.g. S1"]
    flight: Annotated[str, "Flight number as sold, e.g. MA 412 (descriptive only)"]
    origin: Annotated[str, "Three-letter IATA code of the departure airport"]
    destination: Annotated[str, "Three-letter IATA code of the arrival airport"]
    depart_local: Annotated[str, "Scheduled departure, YYYY-MM-DDTHH:MM, origin local time"]
    arrive_local: Annotated[str, "Scheduled arrival, YYYY-MM-DDTHH:MM, destination local time"]
    depart_utc: Annotated[str, "Scheduled departure in UTC, YYYY-MM-DDTHH:MMZ"]
    arrive_utc: Annotated[str, "Scheduled arrival in UTC, YYYY-MM-DDTHH:MMZ"]
    in_air_minutes: Annotated[int, "Scheduled minutes from this segment's departure to its arrival"]
    cabins_sold: Annotated[list[NjcCabin], "Cabins this flight sells, lowest first; economy is always sold"]
    connection_after: Annotated[Connection | None, "The connection to the next segment; null for the last segment"]


@dataclass
class StatusDay(Output):
    date: Annotated[str, "Calendar date, YYYY-MM-DD, local where the traveller is"]
    status_start_local: Annotated[
        str | None, "Clock time travel status begins this day, HH:MM local; null when status began on an earlier day"
    ]
    status_end_local: Annotated[
        str | None, "Clock time travel status ends this day, HH:MM local; null when status continues past midnight"
    ]
    meals_provided: Annotated[list[Meal], "Meals provided to the traveller this day (on board, by a host, or included), any order"]


@dataclass
class TripRequestOutput(Output):
    scenario: Annotated[NjcScenario, "The scenario this trip belongs to"]
    request_text: Annotated[
        str, "The traveller's words, for flavour only: every fact is in the typed fields, and the words may ask for things policy forbids"
    ]
    traveller: Annotated[Traveller, "The traveller (descriptive only)"]
    destination: Annotated[Destination, "Where the trip goes, with its geography flag and allowance row id"]
    accommodation: Annotated[Accommodation, "Where the traveller sleeps at the destination"]
    outbound: Annotated[list[Segment], "The outbound journey's segments in flying order"]
    status_days: Annotated[list[StatusDay], "Every calendar day of the trip in travel status, earliest first, at most 30"]


@dataclass
class RatesInput(Output):
    rate_location_id: Annotated[str, "An allowance-table row id, e.g. D-KE-NAIROBI or C-USA"]


@dataclass
class RateRow(Output):
    accommodation: Annotated[Accommodation, "The accommodation type this row applies to"]
    breakfast_minor: Annotated[int, "Breakfast allowance, hundredths of the currency"]
    lunch_minor: Annotated[int, "Lunch allowance, hundredths of the currency"]
    dinner_minor: Annotated[int, "Dinner allowance, hundredths of the currency"]
    meal_total_minor: Annotated[int, "Breakfast + lunch + dinner, hundredths of the currency"]
    incidental_minor: Annotated[int, "Incidental expense allowance per day or part day, hundredths of the currency"]


@dataclass
class RatesOutput(Output):
    rate_location_id: Annotated[str, "The row id asked for"]
    appendix: Annotated[Appendix, "The NJC table the row is printed in"]
    place: Annotated[str, "The table's country and city or column name (descriptive only)"]
    currency: Annotated[Currency, "The currency every amount in this row is paid in"]
    effective_date: Annotated[str, "The table edition's effective date, YYYY-MM-DD"]
    rows: Annotated[list[RateRow], "The days 1-30 rates, one row per accommodation type, commercial first"]


@dataclass
class SegmentCabin(Output):
    segment_id: Annotated[str, "A segment id of the outbound journey"]
    cabin: Annotated[NjcCabin, "The cabin authorized on that segment"]


@dataclass
class NjcEntitlementOutput(Output):
    segment_cabins: Annotated[list[SegmentCabin], "One entry per outbound segment, each segment once, any order"]
    longest_continuous_air_minutes: Annotated[int, "The longest continuous air travel block of the outbound journey, minutes"]
    currency: Annotated[Currency, "The currency the allowances are paid in"]
    meal_allowance_minor: Annotated[int, "Total meal allowance for the whole trip, hundredths of the currency"]
    incidental_allowance_minor: Annotated[int, "Total incidental allowance for the whole trip, hundredths of the currency"]
    total_minor: Annotated[int, "meal_allowance_minor + incidental_allowance_minor, hundredths of the currency"]


TOOLS = {
    Tool.GET_TRIP_REQUEST: (ScenarioInput, TripRequestOutput),
    Tool.GET_ALLOWANCE_RATES: (RatesInput, RatesOutput),
    Tool.COMPUTE_NJC_ENTITLEMENT: (ScenarioInput, NjcEntitlementOutput),
}
TASKS = {Task.NJC_TRIP_ENTITLEMENT: (ScenarioInput, NjcEntitlementOutput)}
