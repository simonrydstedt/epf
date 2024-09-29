import datetime as dt

from zoneinfo import ZoneInfo

import src.constants as const


def check_for_missing_data(data: dict[const.BIDDING_AREAS : {str: {str: int}}]):
    invalid_dates = {}
    for area, dates in data.items():
        for date, points in dates.items():
            if len(points) != 24:  # Check if the length is not equal to 24
                if area not in invalid_dates:
                    invalid_dates[area] = []
                invalid_dates[area].append(date)  # Store only the date
    # Output the results
    print("Areas and dates with invalid number of points:")
    for area, dates in invalid_dates.items():
        print(f"{area}: {', '.join(dates)}")


def rm_dst_point(points: list[dict[str, int | float]]):
    points[:] = [p for p in points if p["ts"].fold != 1]


def add_dst_point(points: list[dict[str, int | float]], shift: bool = False):
    # New value for the 2:00 AM hour
    new_entry = {
        "ts": dt.datetime(2022, 3, 27, 2, 0, tzinfo=ZoneInfo(key="Europe/Stockholm")),
        "value": 10000,  # Replace with your desired value
    }

    # Insert the new entry for 2:00 AM
    points.append(new_entry)

    # Sort the points by timestamp to maintain order
    points.sort(key=lambda p: p["ts"])
    if shift:
        # Identify the first occurrence of 3:00 AM
        for i, p in enumerate(points):
            if p["ts"].hour == 3 and p["ts"].minute == 0:
                # Shift all subsequent entries by one hour
                for j in range(i + 1, len(points)):
                    points[j]["ts"] += dt.timedelta(hours=1)
                break

    # Check the updated points
