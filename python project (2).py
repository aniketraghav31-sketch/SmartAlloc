import csv
import os
from datetime import datetime, date

ROOMS_FILE = "rooms.csv"
BOOKINGS_FILE = "bookings.csv"
REPORT_FILE = "report.txt"

ROOM_FIELDS = ["room_id", "name", "capacity"]
BOOKING_FIELDS = ["booking_id", "room_id", "date", "start", "end",
                  "event_name", "organizer", "attendees"]

DAY_START = 8 * 60
DAY_END = 20 * 60

DEFAULT_ROOMS = [
    {"room_id": "SH1", "name": "Seminar Hall 1", "capacity": 120},
    {"room_id": "SH2", "name": "Seminar Hall 2", "capacity": 80},
    {"room_id": "AUD", "name": "Main Auditorium", "capacity": 500},
    {"room_id": "LAB1", "name": "Computer Lab 1", "capacity": 60},
    {"room_id": "LAB2", "name": "Computer Lab 2", "capacity": 40},
    {"room_id": "CR1", "name": "Conference Room", "capacity": 25},
]

# Input validation and alternative slot suggestions

def parse_date(text):

    try:
        return datetime.strptime(text.strip(), "%Y-%m-%d").date()
    except (ValueError, AttributeError):
        return None

def parse_time(text):

    try:
        t = datetime.strptime(text.strip(), "%H:%M")
        return t.hour * 60 + t.minute
    except (ValueError, AttributeError):
        return None

def fmt_time(minutes):

    return f"{minutes // 60:02d}:{minutes % 60:02d}"

def validate_booking_request(rooms, room_id, date_text, start_text,
                             end_text, attendees_text):

    room = find_room(rooms, room_id)
    if room is None:
        return None, f"Room '{room_id}' does not exist."

    d = parse_date(date_text)
    if d is None:
        return None, "Invalid date. Use YYYY-MM-DD (e.g. 2026-11-20)."
    if d < date.today():
        return None, "Date is in the past."

    s = parse_time(start_text)
    e = parse_time(end_text)
    if s is None or e is None:
        return None, "Invalid time. Use 24-hour HH:MM (e.g. 14:30)."
    if e <= s:
        return None, "End time must be after start time."
    if s < DAY_START or e > DAY_END:
        return None, (f"Bookings must be between {fmt_time(DAY_START)} "
                      f"and {fmt_time(DAY_END)}.")

    try:
        n = int(attendees_text)
    except (ValueError, TypeError):
        return None, "Attendees must be a whole number."
    if n <= 0:
        return None, "Attendees must be at least 1."
    if n > room["capacity"]:
        return None, (f"{room['name']} seats only {room['capacity']}; "
                      f"{n} expected.")

    return {"room": room, "date": d, "start": s, "end": e,
            "attendees": n}, None

def free_slots(bookings, room_id, d):
    busy = sorted(
        (parse_time(b["start"]), parse_time(b["end"]))
        for b in bookings
        if b["room_id"] == room_id and b["date"] == d.isoformat()
    )
    gaps, cursor = [], DAY_START
    for s, e in busy:
        if s > cursor:
            gaps.append((cursor, s))
        cursor = max(cursor, e)
    if cursor < DAY_END:
        gaps.append((cursor, DAY_END))
    return gaps

def recommend_alternatives(rooms, bookings, room_id, d, start, end,
                           attendees, limit=3):

    alt_rooms = [
        r for r in rooms
        if r["room_id"] != room_id
        and r["capacity"] >= attendees
        and not find_conflicts(bookings, r["room_id"], d, start, end)
    ]
    alt_rooms.sort(key=lambda r: r["capacity"])

    duration = end - start
    candidates = []
    for g_start, g_end in free_slots(bookings, room_id, d):
        if g_end - g_start >= duration:
            # Place the slot as close to the requested start as the gap allows
            new_start = min(max(start, g_start), g_end - duration)
            candidates.append((new_start, new_start + duration))
    candidates.sort(key=lambda slot: abs(slot[0] - start))

    return alt_rooms[:limit], candidates[:limit]

# CSV file handling

def init_files():
    if not os.path.exists(ROOMS_FILE):
        save_rooms(DEFAULT_ROOMS)
    if not os.path.exists(BOOKINGS_FILE):
        save_bookings([])

def load_rooms():
    rooms = []
    try:
        with open(ROOMS_FILE, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    row["capacity"] = int(row["capacity"])
                    rooms.append(row)
                except (ValueError, KeyError):
                    continue  # skip corrupted rows
    except FileNotFoundError:
        pass
    return rooms

def save_rooms(rooms):
    with open(ROOMS_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=ROOM_FIELDS)
        w.writeheader()
        w.writerows(rooms)

def load_bookings():
    bookings = []
    try:
        with open(BOOKINGS_FILE, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    row["attendees"] = int(row["attendees"])
                    bookings.append(row)
                except (ValueError, KeyError):
                    continue
    except FileNotFoundError:
        pass
    return bookings

def save_bookings(bookings):
    with open(BOOKINGS_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=BOOKING_FIELDS)
        w.writeheader()
        w.writerows(bookings)

def next_booking_id(bookings):
    nums = [int(b["booking_id"][1:]) for b in bookings
            if b["booking_id"][1:].isdigit()]
    return f"B{(max(nums) + 1 if nums else 1):03d}"

# Booking conflicts and menu actions

def find_room(rooms, room_id):
    for r in rooms:
        if r["room_id"].upper() == str(room_id).strip().upper():
            return r
    return None

def find_conflicts(bookings, room_id, d, start, end):

    clashes = []
    for b in bookings:
        if b["room_id"] == room_id and b["date"] == d.isoformat():
            b_start, b_end = parse_time(b["start"]), parse_time(b["end"])
            if start < b_end and b_start < end:
                clashes.append(b)
    return clashes

def add_booking(rooms, bookings, data, event_name, organizer):
    booking = {
        "booking_id": next_booking_id(bookings),
        "room_id": data["room"]["room_id"],
        "date": data["date"].isoformat(),
        "start": fmt_time(data["start"]),
        "end": fmt_time(data["end"]),
        "event_name": event_name,
        "organizer": organizer,
        "attendees": data["attendees"],
    }
    bookings.append(booking)
    save_bookings(bookings)
    return booking

def print_rooms(rooms):
    print(f"\n{'ID':<6}{'Name':<22}{'Capacity':>8}")
    print("-" * 36)
    for r in rooms:
        print(f"{r['room_id']:<6}{r['name']:<22}{r['capacity']:>8}")

def print_bookings(bookings, title="BOOKINGS"):
    print(f"\n{title}")
    if not bookings:
        print("  (none)")
        return
    print(f"{'ID':<6}{'Room':<6}{'Date':<12}{'Time':<13}"
          f"{'Event':<24}{'Organizer':<16}{'Att.':>5}")
    print("-" * 82)
    for b in sorted(bookings, key=lambda x: (x["date"], x["start"])):
        print(f"{b['booking_id']:<6}{b['room_id']:<6}{b['date']:<12}"
              f"{b['start']}-{b['end']:<7}{b['event_name'][:22]:<24}"
              f"{b['organizer'][:14]:<16}{b['attendees']:>5}")

def menu_add_room(rooms):
    room_id = input("New room ID (e.g. SH3): ").strip().upper()
    if not room_id or " " in room_id or "," in room_id:
        print("Invalid ID (no spaces or commas).")
        return
    if find_room(rooms, room_id):
        print("That room ID already exists.")
        return
    name = input("Room name: ").strip().replace(",", " ")
    if not name:
        print("Name cannot be empty.")
        return
    try:
        cap = int(input("Seating capacity: "))
        if cap <= 0:
            raise ValueError
    except ValueError:
        print("Capacity must be a positive whole number.")
        return
    rooms.append({"room_id": room_id, "name": name, "capacity": cap})
    save_rooms(rooms)
    print(f"Room {room_id} added.")

def menu_book_room(rooms, bookings):
    print_rooms(rooms)
    room_id = input("\nRoom ID: ").strip()
    date_text = input("Date (YYYY-MM-DD): ")
    start_text = input("Start time (HH:MM, 24h): ")
    end_text = input("End time (HH:MM, 24h): ")
    att_text = input("Expected attendees: ")

    data, error = validate_booking_request(
        rooms, room_id, date_text, start_text, end_text, att_text)
    if error:
        print(f"\n[Error] {error}")
        return

    room = data["room"]
    clashes = find_conflicts(bookings, room["room_id"], data["date"],
                             data["start"], data["end"])
    if clashes:
        print(f"\n[Conflict] {room['name']} is already booked:")
        for c in clashes:
            print(f"  {c['start']}-{c['end']}  {c['event_name']} "
                  f"({c['organizer']})")
        offer_alternatives(rooms, bookings, data)
        return

    event = input("Event name: ").strip().replace("\n", " ") or "Untitled"
    org = input("Organizer / club: ").strip() or "Unknown"
    b = add_booking(rooms, bookings, data, event, org)
    print(f"\n[Confirmed] {b['booking_id']}: {room['name']} on {b['date']} "
          f"{b['start']}-{b['end']} for '{b['event_name']}'.")

def offer_alternatives(rooms, bookings, data):
    room = data["room"]
    alt_rooms, alt_slots = recommend_alternatives(
        rooms, bookings, room["room_id"], data["date"],
        data["start"], data["end"], data["attendees"])

    options = []
    print("\nSuggestions:")
    for r in alt_rooms:
        options.append(("room", r))
        print(f"  {len(options)}. Same time in {r['name']} "
              f"[{r['room_id']}] (capacity {r['capacity']})")
    for s, e in alt_slots:
        options.append(("slot", (s, e)))
        print(f"  {len(options)}. {room['name']} at {fmt_time(s)}-{fmt_time(e)}")

    if not options:
        print("  No alternatives available that day. Try another date.")
        return

    choice = input("Pick a number to book it, or press Enter to cancel: ").strip()
    if not choice.isdigit() or not (1 <= int(choice) <= len(options)):
        print("No booking made.")
        return

    kind, value = options[int(choice) - 1]
    new = dict(data)
    if kind == "room":
        new["room"] = value
    else:
        new["start"], new["end"] = value

    event = input("Event name: ").strip() or "Untitled"
    org = input("Organizer / club: ").strip() or "Unknown"
    b = add_booking(rooms, bookings, new, event, org)
    print(f"\n[Confirmed] {b['booking_id']}: {new['room']['name']} on "
          f"{b['date']} {b['start']}-{b['end']} for '{b['event_name']}'.")

def menu_cancel(bookings):
    print_bookings(bookings, "ALL BOOKINGS")
    bid = input("\nBooking ID to cancel: ").strip().upper()
    for b in bookings:
        if b["booking_id"].upper() == bid:
            bookings.remove(b)
            save_bookings(bookings)
            print(f"Booking {bid} cancelled.")
            return
    print("Booking ID not found.")

def menu_view_bookings(bookings):
    text = input("Filter by date (YYYY-MM-DD) or press Enter for all: ").strip()
    if text:
        d = parse_date(text)
        if d is None:
            print("Invalid date.")
            return
        shown = [b for b in bookings if b["date"] == d.isoformat()]
        print_bookings(shown, f"BOOKINGS ON {d.isoformat()}")
    else:
        print_bookings(bookings, "ALL BOOKINGS")

# Report generation

def build_report(rooms, bookings):
    lines = ["=" * 60, "SMARTALLOC - BOOKING & UTILIZATION REPORT",
             f"Generated: {datetime.now():%Y-%m-%d %H:%M}", "=" * 60, ""]

    lines.append("BOOKING SUMMARY")
    lines.append(f"Total bookings : {len(bookings)}")
    if bookings:
        dates = sorted({b["date"] for b in bookings})
        total_att = sum(b["attendees"] for b in bookings)
        lines.append(f"Dates covered  : {dates[0]} to {dates[-1]} "
                     f"({len(dates)} day(s) with events)")
        lines.append(f"Total attendees: {total_att}")
        lines.append("")
        lines.append("Bookings per organizer:")
        counts = {}
        for b in bookings:
            counts[b["organizer"]] = counts.get(b["organizer"], 0) + 1
        for org, n in sorted(counts.items(), key=lambda x: -x[1]):
            lines.append(f"  {org:<20}{n}")
    lines.append("")

    lines.append("ROOM UTILIZATION")
    lines.append("(% of operating hours used, on days that have bookings)")
    lines.append(f"{'Room':<6}{'Name':<22}{'Bookings':>9}{'Hours':>8}"
                 f"{'Util.':>8}")
    lines.append("-" * 53)
    active_days = len({b["date"] for b in bookings}) or 1
    available = active_days * (DAY_END - DAY_START)
    for r in rooms:
        mine = [b for b in bookings if b["room_id"] == r["room_id"]]
        minutes = sum(parse_time(b["end"]) - parse_time(b["start"])
                      for b in mine)
        pct = 100 * minutes / available
        lines.append(f"{r['room_id']:<6}{r['name']:<22}{len(mine):>9}"
                     f"{minutes / 60:>8.1f}{pct:>7.1f}%")
    if bookings:
        busiest = max(rooms, key=lambda r: sum(
            1 for b in bookings if b["room_id"] == r["room_id"]))
        lines.append("")
        lines.append(f"Most booked room: {busiest['name']}")
    return "\n".join(lines)

def menu_reports(rooms, bookings):
    report = build_report(rooms, bookings)
    print("\n" + report)
    if input("\nSave report to report.txt? (y/n): ").strip().lower() == "y":
        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            f.write(report + "\n")
        print(f"Saved to {REPORT_FILE}.")

# MAIN

MENU = """
========== SMARTALLOC ==========
1. View rooms
2. Add room
3. Book a room
4. View bookings
5. Cancel a booking
6. Reports
0. Exit
================================"""

def main():
    init_files()
    rooms = load_rooms()
    bookings = load_bookings()
    print("Welcome to SmartAlloc - Campus Event & Room Slot Scheduler")

    while True:
        print(MENU)
        choice = input("Choose an option: ").strip()
        if choice == "1":
            print_rooms(rooms)
        elif choice == "2":
            menu_add_room(rooms)
        elif choice == "3":
            menu_book_room(rooms, bookings)
        elif choice == "4":
            menu_view_bookings(bookings)
        elif choice == "5":
            menu_cancel(bookings)
        elif choice == "6":
            menu_reports(rooms, bookings)
        elif choice == "0":
            print("Goodbye!")
            break
        else:
            print("Invalid option. Enter a number from the menu.")

if __name__ == "__main__":
    main()
