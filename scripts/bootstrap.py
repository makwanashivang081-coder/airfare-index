from datetime import date

from apix.pipeline import Pipeline

if __name__ == "__main__":
    Pipeline().run(date(2026, 6, 1), date(2026, 9, 14), date(2026, 9, 14))
