Fix /reports timezone date rounding

Apply the user's timezone offset before rounding timestamps for
/reports, so events near midnight stay on the correct day.

