Fix /reports timestamp rounding order

Apply timezone offset before rounding to UTC to ensure events near
midnight map to the correct calendar day.
