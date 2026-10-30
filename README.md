# Sarcoidosis Likelihood Score (prototype)

## What it does
1. Gives each symptom / finding points (-2 to 5): starts from clinical knowledge of how typical it is
   for sarcoidosis, then adjusted by the case sheet (how often it appears in sarcoidosis vs look-alike diseases).
2. Gives lab results points by how far they are outside the normal range (severity).
3. Adds the points and turns the total into a %: start at a base chance (10%), every 2 points doubles the odds.

## Files
- `data/cases.xlsx` – the cleaned cases (sheet "Clean cases")
- `config.json` – lab normal ranges, lab max points, starting points, base chance
- `engine.py` – the scoring logic
- `make_outputs.py` – poster numbers + charts -> `outputs/`
- `app.py` – web demo

## Run
    pip install -r requirements.txt
    python make_outputs.py
    streamlit run app.py

## Add more cases (next rounds)
Add rows to `data/cases.xlsx` (same columns), then run `python make_outputs.py` again.
Points, stats and charts all update.

## Change normal ranges
Edit the `labs` section of `config.json` (low / high / max_points).

## Put it online (free)
Push this folder to a GitHub repo -> share.streamlit.io -> New app -> pick the repo, file `app.py`.

Not a diagnostic tool. Research prototype for a student competition.
