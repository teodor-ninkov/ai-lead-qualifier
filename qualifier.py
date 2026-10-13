import json
import os
import sys

import pandas as pd
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

DEFAULT_MODEL = "gemini-2.5-flash"
REQUIRED_COLUMNS = ["name", "email", "phone", "message", "date"]
SCORES = ["Hot", "Warm", "Cold"]
OUTPUT_FIELDS = [
    "vehicle",
    "pickup_city",
    "delivery_city",
    "desired_date",
    "score",
    "score_reason",
    "follow_up_email",
]

PROMPT = """You are a sales assistant at a US vehicle transport brokerage.
Analyze the quote request below and return a JSON object with exactly these keys:

vehicle: year, make and model if mentioned, otherwise "Unknown"
pickup_city: city and state if mentioned, otherwise "Unknown"
delivery_city: city and state if mentioned, otherwise "Unknown"
desired_date: the date or timeframe the customer wants, otherwise "Not specified"
score: one of "Hot", "Warm", "Cold"
score_reason: one short sentence explaining the score
follow_up_email: a short, friendly, personalized follow-up email to the customer (max 120 words), signed "Auto Transport Team"

Scoring rules:
Hot: vehicle, route and date are clear, the date is within about 2 weeks, the customer sounds ready to book.
Warm: most details are present, but the date is flexible or later, or the customer is comparing prices.
Cold: vague request, key details missing, or the customer is just browsing.

Customer name: {name}
Request received: {date}
Message: {message}
"""


def get_client(api_key=None):
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        raise ValueError("GEMINI_API_KEY is missing. Add it to .env or Streamlit secrets.")
    return genai.Client(api_key=key)


def validate_columns(df):
    return [col for col in REQUIRED_COLUMNS if col not in df.columns]


def parse_response(text):
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    data = json.loads(cleaned)
    result = {field: str(data.get(field, "")).strip() for field in OUTPUT_FIELDS}
    score = result["score"].capitalize()
    result["score"] = score if score in SCORES else "Cold"
    return result


def qualify_lead(client, lead, model=DEFAULT_MODEL):
    prompt = PROMPT.format(
        name=lead.get("name", ""),
        date=lead.get("date", ""),
        message=lead.get("message", ""),
    )
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.3,
        ),
    )
    return parse_response(response.text)


def qualify_leads(df, api_key=None, model=None, on_progress=None):
    client = get_client(api_key)
    model = model or os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    rows = []
    total = len(df)
    for i, lead in enumerate(df.to_dict(orient="records"), start=1):
        try:
            result = qualify_lead(client, lead, model)
        except Exception as error:
            result = {field: "" for field in OUTPUT_FIELDS}
            result["score"] = "Error"
            result["score_reason"] = str(error)[:200]
        rows.append({**lead, **result})
        if on_progress:
            on_progress(i, total)
    return pd.DataFrame(rows)


def main():
    if len(sys.argv) < 2:
        print("Usage: python qualifier.py leads.csv [results.csv]")
        sys.exit(1)
    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else "results.csv"

    df = pd.read_csv(input_path)
    missing = validate_columns(df)
    if missing:
        print(f"Missing columns: {', '.join(missing)}")
        sys.exit(1)

    results = qualify_leads(df, on_progress=lambda i, t: print(f"Qualified {i}/{t}"))
    results.to_csv(output_path, index=False)
    print(f"Saved {len(results)} leads to {output_path}")
    print(results["score"].value_counts().to_string())


if __name__ == "__main__":
    main()
