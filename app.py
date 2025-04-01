import os
import logging
import openai
import pandas as pd
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Load product feed
product_feed_path = os.path.join("data", "productfeed.csv")
df = None
try:
    df = pd.read_csv(product_feed_path, skipinitialspace=True)
    logging.info(f"Loaded product feed with {len(df)} products.")
except Exception as e:
    logging.error(f"Failed to load product feed: {e}")

# System prompt
system_prompt = (
    "Jij bent de AI Keuzehulp van Expert.nl. Je helpt klanten met het vinden van de perfecte televisie. "
    "Je begeleidt de klant door een reeks gerichte vragen en zorgt ervoor dat er altijd een geschikte aanbeveling uitkomt."
)

# Parse user preferences from conversation
def parse_preferences(messages):
    import re
    brand_pref, size_pref, budget, usage = None, None, None, []
    brands = ["samsung", "lg", "sony", "philips", "panasonic", "tcl", "hisense", "sharp"]

    for msg in messages:
        if msg.get("role") != "user":
            continue
        text = msg.get("content", "").lower()

        if any(w in text for w in ["euro", "eur", "€"]):
            found = re.findall(r'\d+', text)
            if found:
                try:
                    budget = int(found[0])
                except ValueError:
                    pass

        match = re.search(r'(\d+)[\s]*(?:inch|\")', text)
        if match:
            try:
                size_pref = int(match.group(1))
            except ValueError:
                pass

        if any(b in text for b in brands):
            brand_pref = next((b.capitalize() for b in brands if b in text), None)

        for keyword in ["game", "film", "sport", "serie", "tv", "netflix"]:
            if keyword in text:
                usage.append(keyword)
                break

    return brand_pref, size_pref, budget, " ".join(usage)

# Build recommendations
def build_recommendation(brand, size, budget, usage):
    if df is None or df.empty:
        return "Geen productdata beschikbaar."

    results = df.copy()
    if brand:
        brand_col = next((c for c in df.columns if 'merk' in c.lower() or 'brand' in c.lower()), None)
        if brand_col:
            results = results[results[brand_col].str.lower().str.contains(brand.lower())]

    if size:
        size_col = next((c for c in df.columns if 'inch' in c.lower() or 'diagonaal' in c.lower()), None)
        if size_col:
            results[size_col] = pd.to_numeric(results[size_col], errors='coerce')
            results = results[results[size_col].between(size - 5, size + 5)]

    if budget:
        price_col = next((c for c in df.columns if 'prijs' in c.lower() or 'price' in c.lower()), None)
        if price_col:
            results[price_col] = pd.to_numeric(results[price_col], errors='coerce')
            results = results[results[price_col] <= budget]

    if results.empty:
        return "Geen geschikte producten gevonden."

    lines = []
    for _, row in results.head(3).iterrows():
        name = row.get('Name') or row.get('naam') or "Onbekend model"
        line = f"- **{name}**"
        price = next((row.get(c) for c in df.columns if 'prijs' in c.lower()), None)
        try:
            price = float(price)
            line += f" – Prijs: €{price:.2f}"
        except:
            pass
        lines.append(line)

    return "\n".join(lines) + (f"\n\nGeschikt voor: {usage}." if usage else "")

# Homepage
@app.route("/")
def home():
    return "AI Keuzehulp is actief."

# HTML interface
@app.route("/keuzehulp")
def keuzehulp():
    return render_template("index.html")

# Chat endpoint
@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    messages = data.get("messages") or []
    message = data.get("message")

    conversation = [{"role": "system", "content": system_prompt}]
    if message:
        conversation.append({"role": "user", "content": message})
    elif messages:
        conversation += [m for m in messages if m.get("role") != "system"]
    else:
        return jsonify({"assistant": "Geen bericht ontvangen."}), 400

    last_msg = conversation[-1].get("content", "").lower()
    if any(kw in last_msg for kw in ["aanbevel", "welke", "advies", "kopen"]):
        brand, size, budget, usage = parse_preferences(conversation)
        return jsonify({"assistant": build_recommendation(brand, size, budget, usage)})

    try:
        response = openai.ChatCompletion.create(
            model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
            messages=conversation,
            temperature=0.7,
            max_tokens=500
        )
        return jsonify({"assistant": response['choices'][0]['message']['content']})
    except Exception as e:
        logging.error(f"OpenAI fout: {e}")
        return jsonify({"assistant": f"Fout bij OpenAI: {e}"}), 500

# Static files (if needed)
@app.route("/static/<path:path>")
def send_static(path):
    return send_from_directory("static", path)

# Global error handler
@app.errorhandler(Exception)
def handle_exception(e):
    logging.error(f"Unhandled exception: {e}")
    return jsonify({"assistant": f"Interne fout: {e}"}), 500
