```
Apply timezone offset before rounding in /reports

The endpoint rounded to UTC before applying the user's offset,
shifting events near midnight to the wrong day.
```
