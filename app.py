import os
import logging
import openai
import pandas as pd
from flask import Flask, request, jsonify
from flask_cors import CORS

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS voor alle routes en origins

# Load product feed CSV from the /data directory
product_feed_path = os.path.join(os.getcwd(), 'data', 'productfeed.csv')
df = None
try:
    df = pd.read_csv(product_feed_path, skipinitialspace=True)
    logging.info(f"Loaded product feed from {product_feed_path}, found {len(df)} products.")
except Exception as e:
    logging.error(f"Failed to load product feed CSV at {product_feed_path}: {e}")
    df = None

# Configure OpenAI API
openai.api_key = os.environ.get("OPENAI_API_KEY")
if not openai.api_key:
    logging.warning("OPENAI_API_KEY is not set. OpenAI API calls will fail without a valid key.")
# Gebruik de gewenste OpenAI-modelversie; standaard instellen op gpt-3.5-turbo of een ander model
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo")

# System prompt volgens de opgegeven AI Keuzehulp Prompt
system_prompt = (
    "Jij bent de AI Keuzehulp van Expert.nl. Je helpt klanten met het vinden van de perfecte televisie. "
    "Je begeleidt de klant door een reeks gerichte vragen en zorgt ervoor dat er altijd een geschikte aanbeveling uitkomt.\n\n"
    "🚀 Werkwijze:\n"
    "    - Stel systematisch vragen om de behoeften van de klant te achterhalen.\n"
    "    - Leid de klant naar een concreet advies op basis van de opgegeven voorkeuren.\n"
    "    - Geef altijd een of meerdere opties; er mag geen situatie zijn waarin je geen aanbeveling doet.\n\n"
    "✅ Vragenstructuur\n\n"
    "1️⃣ Waarvoor wil je de TV gebruiken?\n"
    "    • Standaard tv-kijken 📺 (Nieuws, programma’s, gemengd gebruik)\n"
    "    • Films en series kijken 🎬 (Beste beeldkwaliteit, bioscoopervaring)\n"
    "    • Sport kijken ⚽ (Snelle bewegingen, hoge refresh rate aanbevolen)\n"
    "    • Games spelen 🎮 (Lage input lag, 120Hz of hoger aanbevolen)\n"
    "    • Dat weet ik nog niet 🤔 (Ik geef uitleg over de verschillen)\n\n"
    "2️⃣ Welk formaat zoek je?\n"
    "    • 43\" 📏 (Kleine ruimtes)\n"
    "    • 50\" 📏 (Goede middenmaat)\n"
    "    • 55\" 📏 (Populair formaat)\n"
    "    • 65\" 📏 (Groter scherm voor impact)\n"
    "    • 75\"+ 📏 (Voor een bioscoopervaring)\n\n"
    "3️⃣ Heb je voorkeur voor een schermtechnologie?\n"
    "    • OLED 🌟 (Perfect zwart, diepe kleuren, bioscoopkwaliteit)\n"
    "    • QLED 🌈 (Helderder beeld, geschikt voor lichte ruimtes)\n"
    "    • LED 💡 (Betaalbaar, goed allround)\n"
    "    • Dat weet ik nog niet 🤔 (Ik leg het uit)\n\n"
    "4️⃣ Wat is je budget?\n"
    "    • Tot €1000 💰 (Budgetvriendelijk)\n"
    "    • €1000 - €1500 💶 (Goede balans tussen prijs en kwaliteit)\n"
    "    • Meer dan €1500 🏆 (Premium beleving)\n\n"
    "5️⃣ Wil je extra smartfuncties of specifieke features?\n"
    "    • Ingebouwde Chromecast\n"
    "    • Apple AirPlay\n"
    "    • HDMI 2.1 (Voor next-gen gaming)\n"
    "    • Antireflectie\n"
    "    • Geen voorkeur\n\n"
    "📌 Advies en Resultaten:\n"
    "    - Zorg dat er altijd een TV overblijft.\n"
    "    - Als een exacte match ontbreekt, bied dan 2-3 alternatieven die zo dicht mogelijk aansluiten.\n"
    "    - Als een TV niet op voorraad is, geef dit aan en bied een alternatief met uitleg.\n\n"
    "✅ Expert.nl Focus:\n"
    "    - Geen negatieve uitspraken over merken.\n"
    "    - Geen adviezen over concurrenten, maar leg wel uit waarom Expert een goede keuze is (eigen installateurs, 140 fysieke winkels, lokale service).\n\n"
    "✅ Voorraadstatus en Alternatieven:\n"
    "    - Als een aanbevolen TV niet op voorraad is: geef dit aan, vraag of een alternatief gewenst is en geef dan een vergelijkbare optie met uitleg.\n\n"
    "🎯 Voorbeeldaanbeveling:\n"
    "    \"Op basis van je voorkeuren is de beste keuze de LG OLED C2 (55\"). Dit model heeft perfect zwart, diepe kleuren en een snelle refresh rate – ideaal voor zowel films als gaming! 🎮🎬\"\n\n"
    "📌 Productfeed Gebruik:\n"
    "    - Gebruik de actuele productfeed (geladen vanuit een CSV).\n"
    "    - Selecteer alleen televisies die op dat moment beschikbaar zijn.\n"
    "    - Toon relevante specificaties uit de feed zoals schermformaat, prijs, en speciale functies.\n\n"
    "Belangrijk: Als de gebruiker tijdens de conversatie een vraag stelt die buiten deze gestructureerde vragen valt, beantwoord die dan op een nette manier en vraag daarna of u wilt doorgaan met het selectieproces."
)

def parse_preferences_from_conversation(messages):
    """
    Extraheer uit het gesprek de voorkeuren: budget, schermgrootte, merkvoorkeur en gebruiksdoel.
    """
    brand_pref = None
    size_pref = None
    budget = None
    usage_notes = []
    import re
    for idx, msg in enumerate(messages):
        if msg.get("role") == "user":
            text = msg.get("content", "").lower()
            # Zoek budget
            if any(word in text for word in ["€", "euro", "eur"]):
                nums = re.findall(r'\d+', text)
                if nums:
                    try:
                        budget_val = int(nums[0])
                    except:
                        try:
                            budget_val = float(nums[0])
                        except:
                            budget_val = None
                    if budget_val is not None:
                        budget = budget_val
            # Zoek schermgrootte
            if "inch" in text or '"' in text:
                match = re.search(r'(\d+)\s*(?:inch|")', text)
                if match:
                    try:
                        size_val = int(match.group(1))
                    except:
                        try:
                            size_val = float(match.group(1))
                        except:
                            size_val = None
                    if size_val is not None:
                        size_pref = size_val
            # Zoek merkvoorkeur
            brands = ["samsung", "lg", "sony", "philips", "panasonic", "tcl", "hisense", "sharp"]
            no_pref = ["geen voorkeur", "weet ik niet"]
            if any(phrase in text for phrase in no_pref):
                brand_pref = None
            else:
                found = [b for b in brands if b in text]
                if found:
                    brand_pref = [b.capitalize() for b in set(found)]
                    if len(brand_pref) == 1:
                        brand_pref = brand_pref[0]
            # Verzamel gebruiksdoel (gaming, films, sport, etc.)
            usage_keywords = ["game", "gaming", "film", "serie", "netflix", "sport", "nieuws", "dagelijks"]
            for uk in usage_keywords:
                if uk in text:
                    usage_notes.append(text)
                    break
    return brand_pref, size_pref, budget, " ".join(usage_notes)

def build_recommendation_text(brand_pref, size_pref, budget, usage_notes):
    """
    Genereer een aanbevelingsbericht op basis van de voorkeuren en gebruik de productfeed (df).
    """
    if df is None or df.empty:
        return "Excuses, ik kan momenteel geen aanbevelingen doen omdat de productgegevens niet beschikbaar zijn."
    results = df.copy()
    # Filter op merk als er een voorkeur is
    if brand_pref:
        brands = []
        if isinstance(brand_pref, str):
            brands = [brand_pref.lower()]
        elif isinstance(brand_pref, list):
            brands = [b.lower() for b in brand_pref]
        brand_col = None
        for col in df.columns:
            if 'brand' in col.lower() or 'merk' in col.lower():
                brand_col = col
                break
        if brand_col:
            mask = pd.Series(False, index=results.index)
            for b in brands:
                mask |= results[brand_col].str.lower().str.contains(b)
            results = results[mask]
    # Filter op schermgrootte (±5 inch marge)
    size_col = None
    if size_pref:
        for col in df.columns:
            if 'inch' in col.lower() or 'diagonaal' in col.lower():
                size_col = col
                break
        if size_col:
            try:
                results[size_col] = pd.to_numeric(results[size_col], errors='coerce')
            except:
                pass
            if pd.api.types.is_numeric_dtype(results[size_col]):
                results = results[(results[size_col] >= size_pref - 5) & (results[size_col] <= size_pref + 5)]
    # Filter op budget
    price_col = None
    if budget:
        for col in df.columns:
            if 'price' in col.lower() or 'prijs' in col.lower():
                price_col = col
                break
        if price_col:
            try:
                results[price_col] = pd.to_numeric(results[price_col], errors='coerce')
            except:
                pass
            if pd.api.types.is_numeric_dtype(results[price_col]):
                results = results[results[price_col] <= budget]
    # Als er geen resultaten zijn, versoepel de criteria
    if results.empty:
        results = df.copy()
    if len(results) > 3:
        results = results.iloc[:3]
    rec_lines = []
    for _, row in results.iterrows():
        name = str(row.get('Name', row.get('naam', 'Onbekend model')))
        price_val = None
        for col in ['Price', 'Prijs', 'price', 'prijs']:
            if col in row and not pd.isna(row[col]):
                price_val = row[col]
                break
        try:
            price_val = float(price_val)
        except:
            import re
            match = re.search(r'\d+\.?\d*', str(price_val))
            price_val = float(match.group(0)) if match else None
        desc_parts = []
        if size_col and size_col in row and not pd.isna(row[size_col]):
            try:
                size_num = float(row[size_col])
                desc_parts.append(f"{int(size_num)} inch")
            except:
                desc_parts.append(str(row[size_col]))
        if 'Type' in row and not pd.isna(row['Type']):
            panel_type = str(row['Type']).strip()
        else:
            panel_type = ""
            if "oled" in name.lower():
                panel_type = "OLED"
            elif "qled" in name.lower():
                panel_type = "QLED"
            elif "led" in name.lower() or "lcd" in name.lower():
                panel_type = "LED"
        if panel_type:
            desc_parts.append(panel_type + " TV")
        if 'Resolution' in row and not pd.isna(row['Resolution']):
            resolution = str(row['Resolution']).strip()
        else:
            resolution = ""
            if "8k" in name.lower():
                resolution = "8K"
            elif "4k" in name.lower() or "uhd" in name.lower():
                resolution = "4K"
            elif "1080" in name.lower() or "full hd" in name.lower():
                resolution = "Full HD"
        if resolution:
            desc_parts.append(resolution)
        line = f"- **{name}**"
        if desc_parts:
            line += " (" + ", ".join(desc_parts) + ")"
        if price_val is not None:
            line += f" – Prijs: €{price_val:.2f}"
        rec_lines.append(line)
    recommendation_text = "Op basis van uw voorkeuren raad ik de volgende televisies aan:\n" + "\n".join(rec_lines)
    if usage_notes:
        recommendation_text += f"\n\nDeze opties zijn uitstekend geschikt voor {usage_notes}."
    recommendation_text += "\n\nZit er iets voor u bij? Laat het gerust weten als u vragen heeft over deze televisies!"
    return recommendation_text

@app.route("/", methods=["GET"])
def index():
    return "AI keuzehulp voor televisies is actief."

@app.route("/chat", methods=["POST"])
def chat():
    if not request.is_json:
        return jsonify({"error": "Ongeldig request formaat, JSON verwacht."}), 400
    data = request.get_json()
    # Ondersteuning voor zowel een volledige berichtenhistorie als een enkel bericht
    user_messages = data.get("messages")
    single_message = data.get("message")
    conversation = [{"role": "system", "content": system_prompt}]
    if user_messages:
        for msg in user_messages:
            role = msg.get("role")
            content = msg.get("content")
            if role and content is not None and role != "system":
                conversation.append({"role": role, "content": content})
    elif single_message:
        conversation.append({"role": "user", "content": single_message})
    else:
        return jsonify({"error": "Geen bericht ontvangen."}), 400

    # Bepaal of we een aanbeveling moeten doen op basis van trefwoorden in de laatste gebruikerbericht
    last_user_msg = None
    for msg in reversed(conversation):
        if msg["role"] == "user":
            last_user_msg = msg["content"].lower()
            break
    recommend_trigger = False
    if last_user_msg:
        trigger_words = ["aanbevel", "advies", "welke tv", "wat raad", "kopen"]
        confirm_words = ["ja", "graag", "yes", "sure", "ok", "okay", "doe maar", "prima"]
        if any(word in last_user_msg for word in trigger_words):
            recommend_trigger = True
        elif last_user_msg.strip() in confirm_words:
            if len(conversation) >= 2 and conversation[-2]["role"] == "assistant":
                prev_assistant = conversation[-2]["content"].lower()
                if any(w in prev_assistant for w in ["zal ik", "advies", "aanbeveling", "aanraden"]):
                    recommend_trigger = True

    if recommend_trigger:
        brand_pref, size_pref, budget, usage_notes = parse_preferences_from_conversation(conversation)
        logging.info(f"Recommendation triggered: brand={brand_pref}, size={size_pref}, budget={budget}, usage={usage_notes}")
        recommendation_message = build_recommendation_text(brand_pref, size_pref, budget, usage_notes)
        return jsonify({"assistant": recommendation_message})
    else:
        try:
            response = openai.ChatCompletion.create(
                model=OPENAI_MODEL,
                messages=conversation,
                temperature=0.7,
                max_tokens=500
            )
            assistant_reply = response['choices'][0]['message']['content']
            logging.info("OpenAI response generated successfully.")
            return jsonify({"assistant": assistant_reply})
        except Exception as e:
            logging.error(f"OpenAI API call failed: {e}")
            return jsonify({"error": "Er ging iets mis bij het genereren van een antwoord van de AI."}), 500

@app.errorhandler(Exception)
def handle_exception(e):
    logging.error(f"Unhandled exception: {e}")
    return jsonify({"error": "Interne serverfout."}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
