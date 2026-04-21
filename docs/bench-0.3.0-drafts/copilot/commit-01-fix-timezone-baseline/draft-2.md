Fix /reports timezone day rounding

Apply the user's timezone offset before rounding timestamps so
events near midnight stay on the correct day.

