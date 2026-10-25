from datetime import date


def current_season(run_date: date, calendar_year: bool = False) -> int:
    """Start year of the season under way on the run date; a split season starts in July."""
    if calendar_year or run_date.month >= 7:
        return run_date.year
    return run_date.year - 1
