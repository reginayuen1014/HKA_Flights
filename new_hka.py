import requests
from datetime import datetime, timedelta
import warnings

# Suppress urllib3 warning
warnings.filterwarnings("ignore", category=UserWarning, module="urllib3")

"""
Find flight codes here - HKIA passenger flights arrival/departure:
url = https://www.hongkongairport.com/en/flights/arrivals/passenger.page

Public API - Flight schedule information of Hong Kong International Airport (Historical).
API doc = https://www.hongkongairport.com/iwov-resources/misc/opendata/Flight_Information_DataSpec_en.pdf
url = https://data.gov.hk/en-data/dataset/aahk-team1-flight-info/resource/8f41b55c-a2ef-4963-bb25-96d8b21f3db4

Sample call: 
Arrivals = https://www.hongkongairport.com/flightinfo-rest/rest/flights/past?date=2025-06-12&lang=en&cargo=false&arrival=true
Departures = https://www.hongkongairport.com/flightinfo-rest/rest/flights/past?date=2025-06-11&lang=en&cargo=false&arrival=false
"""

def fetch_flight_data(date, flight_number, arrival="true"):
    """
    Fetch flight data for a specific date and filter by flight number.
    REQ:
    Only deal with passenger flights -> DEFAULT: cargo = false
    arrival = true -> Flights towards Hong Kong International Airport(HKG), (Origin is other Airports) -> MODE A
    arrival = false -> departure flights (Origin is HKG) -> MODE D
    """
    base_url = "https://www.hongkongairport.com/flightinfo-rest/rest/flights/past"
    params = {
        "date": date,
        "lang": "en",
        "cargo": "false",
        "arrival": arrival
    }

    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()

        # Initialize matching flights
        matching_flights = []

        # Handle response as a list of dictionaries
        flight_list = []
        if isinstance(data, list):
            for entry in data:
                if isinstance(entry, dict) and "list" in entry:
                    flight_list.extend(entry.get("list", []))
                else:
                    print(f"Warning: Skipping invalid entry for {date}: {entry}") #json formatting
        else:
            print(f"Warning: Expected list of dictionaries, got {type(data)} for {date}") #expect json dict format in response list[]
            return []

        # Process each flight record
        for flight in flight_list:
            flight_data = flight.get("flight")
            if flight_data and isinstance(flight_data, list) and len(flight_data) > 0:
                if any(flight_item.get("no", "").replace(" ", "").upper() == flight_number.upper() #json record has spaces in between (ie. CX 418)
                       for flight_item in flight_data):
                    matching_flights.append(flight)
            else:
                print(f"Warning: Skipping invalid flight entry for {date}: {flight}")

        return matching_flights
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data for {date}: {e}")
        return []


def get_past_dates(days=10):
    """
    REQ: return the flight info of past [10] days, therefore generate the date values to match API "Date" field
    Generate a list of dates for the past 'days' days, including today.
    """
    today = datetime.now().date()
    return [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]


def is_on_time(scheduled_time, actual_time):
    """
    Determine if flight is on time
    REQ:
    early or up to 15 minutes late -> ON TIME.
    (actual time > scheduled time) over 15 minutes -> Delayed.
    No return or N/A -> Unknown
    ^ "Cancelled" and other status need to be tackled after implementing regex todo
    """
    if scheduled_time == "N/A" or actual_time == "N/A":
        return "Unknown"
    try:
        # Convert times to minutes for comparison (e.g., "19:30" -> 1170)
        sched_hours, sched_minutes = map(int, scheduled_time.split(":"))
        actual_hours, actual_minutes = map(int, actual_time.split(":"))
        sched_total = sched_hours * 60 + sched_minutes
        actual_total = actual_hours * 60 + actual_minutes
        # On Time if early (actual < scheduled) or late by ≤15 minutes
        return "On Time" if actual_total <= sched_total + 15 else "Delayed"
    except (ValueError, TypeError):
        return "Unknown"

# main
def main():
    mode = "D"  # Default to Departure mode
    while True: # Repeatedly ask for user input unless they quit by inputting "q"
        # Display three-line prompt with current mode
        print(f"Current mode: [{'Departure' if mode == 'D' else 'Arrival'}]")
        print("To change mode: Enter 'D' to search for Departure flights, 'A' for Arrival flights")
        input_str = input("Enter flight number, or 'q' to quit: ").strip()

        # Handle input
        # Any input other than these -> unmatched flight number response. if Valid flight code from json -> print flight record
        if input_str.lower() == "q":
            print("Exiting program.")
            break
        elif input_str.lower() == "d":
            mode = "D"
            continue
        elif input_str.lower() == "a":
            mode = "A"
            continue
        elif not input_str:
            print("Error: Input cannot be empty. Please Enter a valid flight number.")
            continue

        # Normalize flight number (ie. CX 418, CX418, cx418)
        flight_number = input_str.replace(" ", "")
        # Change arrival param based on mode
        arrival = "true" if mode == "A" else "false"

        # Get past 10 days' dates
        dates = get_past_dates(10)
        all_flights = []

        # Fetch data for each date
        # TODO: Regex str to tackle "cancelled" & new/non-standard, non-time status
        for date in dates:
            flights = fetch_flight_data(date, flight_number, arrival)
            if flights:
                for flight in flights:
                    status = flight.get("status", "N/A")
                    scheduled_time = flight.get("time", flight.get("scheduleTime", "N/A"))
                    location_field = "origin" if arrival == "true" else "destination"
                    actual_time = (
                        status.split("At gate ")[-1] if arrival == "true" and "At gate" in status
                        else status.split()[1] if arrival == "false" and status.startswith("Dep ")
                        else flight.get("actualTime", "N/A")
                    )
                    flight_info = {
                        "date": date,
                        "flight_number": flight_number,
                        "location": flight.get(location_field, ["N/A"])[0] if flight.get(location_field) else
                        flight.get("listAirport", [{}])[0].get("city", "N/A"),
                        "scheduled_time": scheduled_time,
                        "actual_time": actual_time,
                        "status": status,
                        "on_time": is_on_time(scheduled_time, actual_time),
                        # Arrivals-specific
                        "baggage": flight.get("baggage", "N/A") if arrival == "true" else None,
                        "hall": flight.get("hall", "N/A") if arrival == "true" else None,
                        "stand": flight.get("stand", "N/A") if arrival == "true" else None,
                        # Departures-specific
                        "terminal": flight.get("terminal", "N/A"),
                        "aisle": flight.get("aisle", "N/A") if arrival == "false" else None,
                        "gate": flight.get("gate", "N/A") if arrival == "false" else None
                    }
                    all_flights.append(flight_info)

        # Display results
        # TODO: since flight codes are mostly identical to one another, can we auto-identify the origin/departure before making API request? fallback search? large no. of request...
        # TODO thought: (look up List/Dict for flights codes, origin/dept key) as to avoid this "wrong mode-valid flight code" false-negative scenario

        if not all_flights:
            print(
                f"No {'arrivals' if mode == 'A' else 'departures'} found for flight number {flight_number} in the past 10 days.\n")
            continue

        # Check if location and scheduled time are consistent
        locations = {flight["location"] for flight in all_flights}
        scheduled_times = {flight["scheduled_time"] for flight in all_flights}
        location = locations.pop() if len(locations) == 1 else "Varies"
        scheduled_time = scheduled_times.pop() if len(scheduled_times) == 1 else "Varies"

        # Print formatted output with aligned columns
        label = "Arrivals" if mode == "A" else "Departures"
        loc_label = "Origin" if mode == "A" else "Destination"
        print(f"\n{label} found for {flight_number} in the past 10 days:")
        print(f"Flight Number: {flight_number} | {loc_label}: {location}\n")
        print(f"Scheduled Time: {scheduled_time}")

        # Define column widths for alignment
        date_width = 16
        actual_time_width = 18
        status_width = 20   # For str, status message
        field_width = 12  # For terminal, aisle, gate, baggage, hall, stand

        for flight in sorted(all_flights, key=lambda x: x["date"], reverse=True):
            date_str = f"Date: {flight['date']}".ljust(date_width) #ljust() fill spaces til limit
            actual_time_str = f"Actual Time: {flight['actual_time']}".ljust(actual_time_width)
            status_str = f"{flight['status']}".ljust(status_width)
            if mode == "A":
                baggage_str = f"Baggage: {flight['baggage']}".ljust(field_width)
                hall_str = f"Hall: {flight['hall']}".ljust(field_width)
                terminal_str = f"Terminal: {flight['terminal']}".ljust(field_width)
                stand_str = f"Stand: {flight['stand']}".ljust(field_width)
                print(
                    f"{date_str} | {actual_time_str} | {status_str} | {baggage_str} | {hall_str} | {stand_str} | {flight['on_time']}")
            else: #Departures
                terminal_str = f"Terminal: {flight['terminal']}".ljust(field_width)
                aisle_str = f"Aisle: {flight['aisle']}".ljust(field_width)
                gate_str = f"Gate: {flight['gate']}".ljust(field_width)
                print(
                    f"{date_str} | {actual_time_str} | {status_str} | {terminal_str} | {aisle_str} | {gate_str} | {flight['on_time']}")

        print()  # Extra line for readability


if __name__ == "__main__":
    main()

'''
# Arrival
=========================================================================================================
Current mode: [Arrival]
To change mode: Enter 'D' to search for Departure flights, 'A' for Arrival flights
Enter flight number, or 'q' to quit: hx631

Arrivals found for hx631 in the past 10 days:
Flight Number: hx631 | Origin: NRT

Scheduled Time: 00:45
Date: 2025-06-12 | Actual Time: 01:00 | At gate 01:00        | Baggage: 12  | Hall: B      | Stand: D219  | On Time
Date: 2025-06-10 | Actual Time: 00:36 | At gate 00:36        | Baggage: 15  | Hall: B      | Stand: D204  | On Time
Date: 2025-06-09 | Actual Time: 00:39 | At gate 00:39        | Baggage: 15  | Hall: B      | Stand: D218  | On Time
Date: 2025-06-08 | Actual Time: 00:32 | At gate 00:32        | Baggage: 14  | Hall: B      | Stand: D211  | On Time
Date: 2025-06-07 | Actual Time: 00:50 | At gate 00:50        | Baggage: 14  | Hall: B      | Stand: D311  | On Time
Date: 2025-06-06 | Actual Time: 00:27 | At gate 00:27        | Baggage: 14  | Hall: B      | Stand: D307R | On Time
Date: 2025-06-04 | Actual Time: 00:40 | At gate 00:40        | Baggage: 13  | Hall: B      | Stand: D311  | On Time

# Departure
=========================================================================================================
Current mode: [Departure]
To change mode: Enter 'D' to search for Departure flights, 'A' for Arrival flights
Enter flight number, or 'q' to quit: cx418

Departures found for cx418 in the past 10 days:
Flight Number: cx418 | Destination: ICN

Scheduled Time: 14:25
Date: 2025-06-12 | Actual Time: 14:22 | Dep 14:22            | Terminal: T1 | Aisle: A     | Gate: 68     | On Time
Date: 2025-06-11 | Actual Time: 14:27 | Dep 14:27            | Terminal: T1 | Aisle: A     | Gate: 65     | On Time
Date: 2025-06-10 | Actual Time: 14:27 | Dep 14:27            | Terminal: T1 | Aisle: A     | Gate: 71     | On Time
Date: 2025-06-09 | Actual Time: 14:30 | Dep 14:30            | Terminal: T1 | Aisle: A     | Gate: 45     | On Time
Date: 2025-06-08 | Actual Time: 14:22 | Dep 14:22            | Terminal: T1 | Aisle: A     | Gate: 71     | On Time
Date: 2025-06-07 | Actual Time: 14:26 | Dep 14:26            | Terminal: T1 | Aisle: A     | Gate: 71     | On Time
Date: 2025-06-06 | Actual Time: 14:36 | Dep 14:36            | Terminal: T1 | Aisle: A     | Gate: 11     | On Time
Date: 2025-06-05 | Actual Time: 14:26 | Dep 14:26            | Terminal: T1 | Aisle: A     | Gate: 2      | On Time
Date: 2025-06-04 | Actual Time: 14:23 | Dep 14:23            | Terminal: T1 | Aisle: A     | Gate: 42     | On Time
Date: 2025-06-03 | Actual Time: 14:30 | Dep 14:30            | Terminal: T1 | Aisle: A     | Gate: 71     | On Time

Current mode: [Departure]
To change mode: Enter 'D' to search for Departure flights, 'A' for Arrival flights
Enter flight number, or 'q' to quit: a
Current mode: [Arrival]
To change mode: Enter 'D' to search for Departure flights, 'A' for Arrival flights
Enter flight number, or 'q' to quit: q
Exiting program.

Process finished with exit code 0

# Flights that are currently flying (<- & codeshare flight, delayed)
=========================================================================================================
Arrivals found for NZ4850 in the past 10 days: 
Flight Number: NZ4850 | Origin: IST

Scheduled Time: 17:15
Date: 2025-06-12 | Actual Time: N/A   | Est at 20:55         | Baggage:     | Hall:        | Stand:       | Unknown
Date: 2025-06-11 | Actual Time: 17:14 | At gate 17:14        | Baggage: 9   | Hall: A      | Stand: W50   | On Time
Date: 2025-06-10 | Actual Time: 17:14 | At gate 17:14        | Baggage: 8   | Hall: A      | Stand: S35   | On Time
Date: 2025-06-09 | Actual Time: 17:24 | At gate 17:24        | Baggage: 10  | Hall: A      | Stand: S31   | On Time
Date: 2025-06-08 | Actual Time: 17:27 | At gate 17:27        | Baggage: 16  | Hall: B      | Stand: W44   | On Time
Date: 2025-06-07 | Actual Time: 17:30 | At gate 17:30        | Baggage: 13  | Hall: B      | Stand: S29   | On Time
Date: 2025-06-06 | Actual Time: 17:13 | At gate 17:13        | Baggage: 12  | Hall: B      | Stand: N64   | On Time
Date: 2025-06-05 | Actual Time: 16:58 | At gate 16:58        | Baggage: 10  | Hall: A      | Stand: N66   | On Time
Date: 2025-06-03 | Actual Time: 16:51 | At gate 16:51        | Baggage: 9   | Hall: A      | Stand: S29   | On Time

Current mode: [Arrival]
To change mode: Enter 'D' to search for Departure flights, 'A' for Arrival flights
Enter flight number, or 'q' to quit: 
'''