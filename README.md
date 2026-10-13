# AI Lead Qualifier

Turns raw vehicle transport quote requests into qualified, ready-to-call leads.

For every lead the app:

- extracts the vehicle, pickup city, delivery city and desired date from free text
- scores the lead **Hot**, **Warm** or **Cold** with a short reason
- drafts a personalized follow-up email
- exports everything to CSV

Built from real experience in US auto transport sales, where agents spend hours reading quote requests and writing the same follow-ups by hand.

**Live demo:** (https://ai-lead-qualifier-mwbmqp4tzt6aifyytdgv8x.streamlit.app/)

![Screenshot](screenshot.png)

## Tech stack

- Python, pandas
- Google Gemini API (structured JSON output)
- Streamlit (web interface)

## How it works

1. Load leads from a CSV (`name, email, phone, message, date`) or use the sample data.
2. Each message is sent to Gemini with a prompt that defines the scoring rules and the JSON format to return.
3. The response is validated and merged back into the lead row. Failed requests are marked as `Error` instead of stopping the run.
4. Results are shown in a filterable table with counts per score and can be downloaded as CSV.

## Run locally

```bash
git clone https://github.com/<your-username>/ai-lead-qualifier.git
cd ai-lead-qualifier
pip install -r requirements.txt
cp .env.example .env
```

Add your free API key from [Google AI Studio](https://aistudio.google.com/) to `.env`, then:

```bash
streamlit run app.py
```

Or run it from the command line without the interface:

```bash
python qualifier.py sample_leads.csv results.csv
```

## Project structure

```
app.py              Streamlit web interface
qualifier.py        Core logic: prompt, Gemini call, parsing, CLI
sample_leads.csv    10 realistic sample leads
requirements.txt    Dependencies
.env.example        Template for the API key
```
