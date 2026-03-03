# Garmin + Browser Stress Analyzer ❤️

Discover which websites raise your stress and heart rate the most — by combining Garmin biometric data with your browser history.

> Companion app for the Medium article: [*Your Watch Knows Which Websites Stress You Out*](#)

![Python](https://img.shields.io/badge/python-3.9%2B-blue) ![Streamlit](https://img.shields.io/badge/streamlit-1.x-red)

---

## How It Works

1. Pulls your **heart rate & stress data** from Garmin Connect via the `garminconnect` library
2. Reads your **browser history** (Chrome, Firefox, Edge, Brave, Opera)
3. **Joins the two timelines** using a configurable time window
4. Ranks domains by average stress and heart rate during your visits

---

## Setup

```bash
git clone https://github.com/yourusername/garmin-browser-stress
cd garmin-browser-stress

pip install -r requirements.txt
streamlit run app.py
```

### Requirements

```
streamlit
pandas
numpy
plotly
garminconnect
```

Or install directly:

```bash
pip install streamlit pandas numpy plotly garminconnect
```

---

## Usage

1. **Log in** to Garmin Connect using the sidebar
2. **Load Garmin data** for the desired number of days
3. **Load browser history** — two options:
   - 🌟 **Export from extension** (recommended): install a history export extension, export as JSON/CSV, upload the file
   - 💾 **Direct database read**: close your browser, let the app auto-detect the database
4. Go to the **Analysis** tab to see results

### Recommended browser extensions for export

| Browser               | Extension                                       |
| --------------------- | ----------------------------------------------- |
| Chrome / Edge / Brave | Export Chrome History, History Trends Unlimited |
| Firefox               | Export History                                  |

---

## Privacy

All data is processed **locally**. Nothing is sent to any server beyond Garmin's own API during login and data fetch.

---

## Caveats

- `garminconnect` is an **unofficial** library based on reverse-engineered endpoints — it may break after Garmin app updates
- Garmin's stress metric is derived from HRV and is affected by factors beyond mental stress (caffeine, posture, exercise)
- The time-window join is a heuristic — **correlation, not causation**
- Chrome's database must be copied while the browser is closed for direct reads; use the export method to avoid this

---

## License

MIT
