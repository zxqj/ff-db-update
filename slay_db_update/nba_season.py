import re
from datetime import datetime, date
import parsedatetime

class NBASeason(int):
    """An int subclass representing the starting year of an NBA season.

    Construction accepts:
    - an int (treated as the starting year)
    - a date/datetime (mapped to the season start year: months Oct-Dec -> that year, Jan-Sep -> year-1)
    - a string containing a season range (e.g. "2025-26", "25-26", "2025-2026") in which case the first year is used
    - a string parseable as a date (e.g. "2026-03-02", "03/02/2026", "March 2nd, 2026")

    The __str__ prints the conventional range form: "2025-26" for internal value 2025.
    Arithmetic operators that produce integer results return NBASeason instances so the type is preserved.
    """

    def __new__(cls, value = datetime.now()):
        # If already an NBASeason, return directly
        if isinstance(value, NBASeason):
            return value

        start_year = None

        # integers: directly use
        if isinstance(value, int):
            start_year = int(value)

        # datetimes/dates: compute season start based on month
        elif isinstance(value, datetime):
            year = value.year
            month = value.month
            start_year = year if month >= 10 else year - 1

        # strings: attempt to interpret as season-range or date
        elif isinstance(value, str):
            c = parsedatetime.Calendar()
            value = c.parseDT(value)[0]
            year = value.year
            month = value.month
            start_year = year if month >= 10 else year - 1

        elif isinstance(value, date):
            year = value.year
            month = value.month
            start_year = year if month >= 10 else year - 1

        return super().__new__(cls, start_year)

    @staticmethod
    def _parse_date(s):
        """Parse a date string. Prefer dateutil.parser when available, otherwise try several formats."""
        try:
            # prefer python-dateutil if installed
            from dateutil import parser as _parser
            return _parser.parse(s, fuzzy=True)
        except Exception:
            # fallback parsing attempts
            from datetime import datetime as _dt
            fmts = [
                "%Y-%m-%d",
                "%Y/%m/%d",
                "%m/%d/%Y",
                "%m/%d/%y",
                "%B %d, %Y",
                "%b %d, %Y",
                "%B %d %Y",
                "%b %d %Y",
                "%Y",
            ]
            s2 = re.sub(r'(?<=\d)(st|nd|rd|th)', '', s, flags=re.IGNORECASE)
            for fmt in fmts:
                try:
                    return _dt.strptime(s2, fmt)
                except Exception:
                    continue
            # last-ditch: try ISO8601 via fromisoformat
            try:
                return _dt.fromisoformat(s2)
            except Exception:
                raise

    def __str__(self):
        y = int(self)
        return f"{y}-{str(y+1)[2:]}"

    def __repr__(self):
        return f"NBASeason({int(self)})"

    # small helper to wrap integer results back into NBASeason
    def _wrap(self, result):
        if isinstance(result, int) and not isinstance(result, bool):
            return NBASeason(result)
        return result

    # arithmetic
    def __add__(self, other):
        try:
            res = int(self) + (int(other) if isinstance(other, NBASeason) else other)
        except Exception:
            return NotImplemented
        return self._wrap(res)

    def __radd__(self, other):
        try:
            res = (int(other) if isinstance(other, NBASeason) else other) + int(self)
        except Exception:
            return NotImplemented
        return self._wrap(res)

    def __sub__(self, other):
        try:
            res = int(self) - (int(other) if isinstance(other, NBASeason) else other)
        except Exception:
            return NotImplemented
        return self._wrap(res)

    def __rsub__(self, other):
        try:
            res = (int(other) if isinstance(other, NBASeason) else other) - int(self)
        except Exception:
            return NotImplemented
        return self._wrap(res)

    def __mul__(self, other):
        try:
            res = int(self) * (int(other) if isinstance(other, NBASeason) else other)
        except Exception:
            return NotImplemented
        return self._wrap(res)

    def __rmul__(self, other):
        try:
            res = (int(other) if isinstance(other, NBASeason) else other) * int(self)
        except Exception:
            return NotImplemented
        return self._wrap(res)

    def __floordiv__(self, other):
        try:
            res = int(self) // (int(other) if isinstance(other, NBASeason) else other)
        except Exception:
            return NotImplemented
        return self._wrap(res)

    def __rfloordiv__(self, other):
        try:
            res = (int(other) if isinstance(other, NBASeason) else other) // int(self)
        except Exception:
            return NotImplemented
        return self._wrap(res)

    def __mod__(self, other):
        try:
            res = int(self) % (int(other) if isinstance(other, NBASeason) else other)
        except Exception:
            return NotImplemented
        return self._wrap(res)

    def __rmod__(self, other):
        try:
            res = (int(other) if isinstance(other, NBASeason) else other) % int(self)
        except Exception:
            return NotImplemented
        return self._wrap(res)

    def __pow__(self, other, modulo=None):
        try:
            if modulo is None:
                res = int(self) ** (int(other) if isinstance(other, NBASeason) else other)
            else:
                res = pow(int(self), (int(other) if isinstance(other, NBASeason) else other), modulo)
        except Exception:
            return NotImplemented
        return self._wrap(res)

    def __rpow__(self, other):
        try:
            res = (int(other) if isinstance(other, NBASeason) else other) ** int(self)
        except Exception:
            return NotImplemented
        return self._wrap(res)

    def __neg__(self):
        return self._wrap(-int(self))
