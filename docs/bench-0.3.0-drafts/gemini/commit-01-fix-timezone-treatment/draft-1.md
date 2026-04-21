Apply offset before rounding report timestamps
The endpoint now applies the user offset before UTC rounding to ensure
midnight events map to the correct day in the /reports endpoint.
