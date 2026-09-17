from datetime import date

from apix.pipeline import Pipeline

if __name__ == "__main__":
    # Full basket through today (settings as_of). Builds CPI chain + booking-window curves.
    Pipeline().run(date(2026, 6, 1), date(2026, 9, 16), date(2026, 9, 16))
