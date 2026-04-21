Fix timezone offset ordering in /reports endpoint

Apply user's timezone offset before rounding timestamps to day
boundaries so events near midnight appear on the correct day.
