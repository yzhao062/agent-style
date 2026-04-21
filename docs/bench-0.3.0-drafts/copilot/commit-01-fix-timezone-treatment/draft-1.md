Fix /reports timezone rounding order

Apply the user's offset before rounding so events near
midnight stay on the correct local day in /reports.

