"""Seed the first test trip, Thailand (Nov 13–28, 2026), from the brief's
"first test" cases, so the Trips app has the real plan to check.

    .venv/bin/python scripts/import_thailand_trip.py

Safe to re-run: it does nothing if a trip named like this already exists.
Everything it writes goes through actions, so it lands in history and can be
undone. Dates and prices are the ones the brief names (Sep 2026); items the
brief left open are marked "to book" for Malachi to fix in the app.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import apps.trips.server.actions  # noqa: F401, E402
from engine import actions  # noqa: E402
from engine.store import Store  # noqa: E402

NAME = "Thailand, Nov 2026"


def main() -> int:
    store = Store()
    with store.read():
        if store.con.execute("SELECT 1 FROM trips WHERE name=? AND deleted_at IS NULL", (NAME,)).fetchone():
            print(f"{NAME!r} is already there; nothing done.")
            return 0
    run = lambda action_name, **p: actions.run(store, action_name, p, "import")  # noqa: E731
    t = run("trips.create", name=NAME, purpose="personal", start_date="2026-11-13", end_date="2026-11-28", headcount=2, travelers=["Malachi"],
            home_currency="USD", local_currency="THB", fx_rate=33.4, fx_date="2026-09-28", passport_country="USA", region_pack="thailand",
            purpose_note="Guys' trip: active days, water sports, nightlife. Bangkok → Krabi (Ao Nang) → Phuket (Patong) → Bangkok.")
    tid = t["id"]
    add = lambda **p: run("trips.add_item", trip_id=tid, **p)  # noqa: E731
    # Bangkok, first stay
    add(kind="stay", title="Charlie House, Bangkok", from_place="Bangkok", start_at="2026-11-13", end_at="2026-11-17", status="booked", operator="Charlie House",
             notes="Pays at check-in in baht, Visa or Mastercard only. Bag hold after checkout: not confirmed (W13).")
    # Nov 17: moving day, Charlie House → Don Mueang → Krabi (W01 proven)
    add(kind="flight", title="Bangkok (DMK) → Krabi, 5:20 PM", from_place="Don Mueang Airport (DMK), Bangkok", to_place="Krabi Airport", start_at="2026-11-17T17:20", end_at="2026-11-17T18:45",
        status="booked", price_cents=10593, currency="USD", basis="group", notes="Moved from the 6:15 AM ($99.84) to the 5:20 PM ($105.93). Re-check the airport taxi against the new landing time.",
        lead_minutes=60)
    add(kind="taxi", title="Airport taxi Krabi → Ao Nang", from_place="Krabi Airport", to_place="Nomads Ao Nang", start_at="2026-11-17T18:45", status="booked",
        notes="Booked against the rescheduled flight; the brief says check it (first test case). Shared shuttle is about ฿150 a person; the taxi counter quoted ฿1,200+.")
    nomads = add(kind="stay", title="Nomads, Ao Nang (Krabi)", from_place="Ao Nang", start_at="2026-11-17", end_at="2026-11-20", status="booked", operator="Nomads",
                 notes="Lockers are small: bring padlocks. Ask them to hold bags on Nov 20 (W13, W27).")
    # Nov 20: half-day tour, then the boat to Phuket and Grab to Patong (W02 proven, W07 proven, W12 adopted)
    add(kind="activity", title="4 Islands half-day tour", from_place="Ao Nang", start_at="2026-11-20T08:00", end_at="2026-11-20T13:00", status="to_book",
        notes="Only a half-day tour fits before the afternoon transfer (W07). Park fee ฿400 per adult, cash, usually included in booked tours.")
    add(kind="ferry", title="Boat Ao Nang → Rassada Pier, Phuket", from_place="Nopparat Thara Pier, Ao Nang", to_place="Rassada Pier, Phuket Town", start_at="2026-11-20T15:00", end_at="2026-11-20T17:00",
        status="to_book", last_departure="15:30", notes="Ferries stop mid-afternoon. Speedboat or ferry via 12Go / Rassada Pier sites; set the date and 2 people. Live test for W28 (the afternoon boat).")
    add(kind="taxi", title="Grab Rassada Pier → Patong", from_place="Rassada Pier, Phuket Town", to_place="Mazi Design Hotel, Patong", start_at="2026-11-20T17:20", status="idea",
        price_cents=45000, currency="THB", basis="group", notes="Grab or Bolt ฿350–500; meet the driver outside the pier gate. Skip the tuk-tuk touts (฿600+).")
    add(kind="stay", title="Mazi Design Hotel, Patong (Phuket)", from_place="Patong", start_at="2026-11-20", end_at="2026-11-22", status="booked", operator="Mazi Design Hotel",
        notes="Canal behind the hotel smells: high, front room away from it (requested in the booking).")
    # Phuket → Bangkok and the last Bangkok stay: still open (W14 open)
    add(kind="flight", title="Phuket → Bangkok", from_place="Phuket Airport (HKT)", to_place="Bangkok", start_at="2026-11-22T12:00", status="to_book",
        notes="Not booked. Compare Expedia with airasia.com, nokair.com, lionairthai.com, vietjetair.com; check which Bangkok airport. Budget fares climb into high season (book ~6 weeks out).")
    add(kind="stay", title="Bangkok hotel, Nov 22–28", from_place="Bangkok", start_at="2026-11-22", end_at="2026-11-28", status="to_book", notes="Search by neighborhood, never the airport (G06).")
    # Before you go
    run("trips.before_you_go", trip_id=tid)
    run("trips.add_task", trip_id=tid, title="Ask Nomads and Charlie House to hold bags after checkout (message first, call if no reply)", kind="confirm", due="2026-10-15", item_id=nomads["id"])
    run("trips.add_task", trip_id=tid, title="Set up Grab and Bolt with a card", kind="phone", due="2026-11-10")
    run("trips.add_task", trip_id=tid, title="Decide on scooters; if yes, get the International Driving Permit (motorcycle class) from AAA", kind="permit", due="2026-10-20")
    run("trips.add_task", trip_id=tid, title="Follow-up on the open items (the reminder set for Tue Sep 29, 7 PM)", kind="follow_up", due="2026-09-29")
    # The track record from the brief
    for code, outcome, note in [("W01", "proven", "Nov 17, Charlie House → Don Mueang → Krabi"), ("W02", "proven", "Bangkok → Krabi (flight booked), Krabi → Phuket (boat + Grab); Phuket → Bangkok open"),
                                ("W03", "proven", "Phuket → Kanchanaburi → Bangkok"), ("W04", "proven", "The $122 fare was for two ($61 each); AirAsia isn't on Expedia"),
                                ("W05", "rejected", "Chiang Mai turned down at $317; Kanchanaburi and Hua Hin dropped"), ("W06", "rejected", "Phi Phi dropped for day tours from Krabi"),
                                ("W07", "proven", "Phi Phi stop left ~4 hours; only a half-day tour fits Nov 20"), ("W08", "proven", "Krabi 3 nights, Phuket 2"),
                                ("W09", "proven", "Airport-based search moved to Ao Nang"), ("W10", "proven", "Nomads and Mazi booked; Vapa, Sai Rougn and the Erawan places ruled out"),
                                ("W11", "proven", "Phuket → Patong"), ("W12", "adopted", "4 Islands half-day tour on Nov 20, not booked"), ("W13", "open", "Bag holds not confirmed"),
                                ("W14", "open", "Phuket → Bangkok isn't booked"), ("W15", "open", "The private charter never showed on 12Go"), ("W16", "proven", "Taxi meets the bus (Hua Hin route later dropped)"),
                                ("W17", "proven", "Krabi flight moved from 6:15 AM to 5:20 PM"), ("W18", "proven", "12 threads labeled; caught the 12:00 PM taxi against the 6:45 PM landing"),
                                ("W19", "proven", "Timeline, 11 calendar events, follow-up Tue Sep 29"), ("W20", "adopted", "Patong; AfroRoom Friday not confirmed"),
                                ("W21", "open", "IDP with the motorcycle class needs a motorcycle endorsement"), ("W22", "proven", ""), ("W23", "proven", "")]:
        run("trips.log_workflow", trip_id=tid, code=code, outcome=outcome, note=note or None)
    r = run("trips.run_checks", trip_id=tid)
    print(f"Created {NAME!r} ({tid}): {len(r['findings'])} findings ({r['counts']}). Open the Trips app to review; edit anything that is wrong.")
    print("Bangkok Nov 22–28 and Phuket → Bangkok on Nov 22 are guesses from '2 nights in Phuket'; fix the dates if they differ.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
