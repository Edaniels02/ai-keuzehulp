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
CORS(app)  # enable CORS for all routes and origins

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
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo")

# System prompt defining the assistant's behavior and style (in Dutch)
system_prompt = (
    "Je bent een behulpzame AI assistent die de gebruiker helpt bij het kiezen van een televisie. "
    "Je stelt systematisch gerichte vragen over de voorkeuren van de gebruiker (budget, schermgrootte, gebruiksdoel, favoriete merk, etc.). "
    "Blijf flexibel en behulpzaam als de gebruiker een andere vraag stelt: beantwoord die vraag netjes en vraag daarna of de gebruiker terug wil naar de televisie keuzehulp. "
    "Voer de conversatie in het Nederlands en spreek de gebruiker aan met 'u'. "
    "Zodra je voldoende informatie hebt verzameld, doe je een aanbeveling van enkele televisies uit de productlijst op basis van die voorkeuren. "
    "Presenteer je advies enthousiast en natuurlijk, zodat de gebruiker een prettige ervaring heeft."
)

def parse_preferences_from_conversation(messages):
    """
    Hulpfunctie om uit het gesprek de voorkeuren van de gebruiker te halen:
    budget (in euro's), gewenste schermgrootte (in inches), merkvoorkeur, en gebruiksdoel.
    """
    brand_pref = None
    size_pref = None
    budget = None
    usage_notes = []
    for idx, msg in enumerate(messages):
        if msg.get("role") == "user":
            text = msg.get("content", "").lower()
            # Zoek budget (euro bedrag in de tekst)
            if any(word in text for word in ["€", "euro", "eur"]):
                # Zoek getallen (budget) in de tekst
                import re
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
            else:
                # Als vorige vraag over budget ging en gebruiker gaf alleen een getal
                if idx > 0 and messages[idx-1].get("role") == "assistant":
                    prev_q = messages[idx-1].get("content", "").lower()
                    if "budget" in prev_q or "prijs" in prev_q:
                        import re
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
            # Zoek schermgrootte (inch in de tekst)
            if "inch" in text or '"' in text:
                import re
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
            else:
                # Als vorige vraag over grootte ging en gebruiker gaf alleen een getal
                if idx > 0 and messages[idx-1].get("role") == "assistant":
                    prev_q = messages[idx-1].get("content", "").lower()
                    if "inch" in prev_q or "scherm" in prev_q or "formaat" in prev_q:
                        import re
                        nums = re.findall(r'\d+', text)
                        if nums:
                            try:
                                size_val = int(nums[0])
                            except:
                                try:
                                    size_val = float(nums[0])
                                except:
                                    size_val = None
                            if size_val is not None:
                                size_pref = size_val
            # Zoek merkvoorkeur (bekende merknamen of aanduiding geen voorkeur)
            brands = ["samsung", "lg", "sony", "philips", "panasonic", "tcl", "hisense", "sharp"]
            no_pref_phrases = ["geen voorkeur", "maakt niet uit", "alles goed", "weet ik niet", "geen voorkeur specifiek"]
            if any(phrase in text for phrase in no_pref_phrases):
                brand_pref = None
            else:
                found_brands = [b for b in brands if b in text]
                if found_brands:
                    # Als er al een merkvoorkeur is gevonden, combineren (meerdere merken)
                    if brand_pref:
                        if isinstance(brand_pref, list):
                            for b in found_brands:
                                if b not in [bp.lower() for bp in brand_pref]:
                                    brand_pref.append(b.capitalize())
                        else:
                            # Maak van bestaande voorkeur een lijst als verschillend
                            if brand_pref.lower() not in found_brands:
                                found_brands.append(brand_pref.lower())
                            # Capitalize each brand for consistency
                            brand_pref = [b.capitalize() for b in set(found_brands)]
                    else:
                        brand_pref = [b.capitalize() for b in set(found_brands)]
                        if len(brand_pref) == 1:
                            brand_pref = brand_pref[0]  # single brand as string
            # Zoek gebruiksdoel (gaming, films, sport, etc.)
            usage_keywords = ["game", "gaming", "spel", "xbox", "playstation",
                               "film", "serie", "netflix",
                               "sport", "voetbal",
                               "nieuws", "dagelijks", "overdag", "donker", "licht"]
            for uk in usage_keywords:
                if uk in text:
                    usage_notes.append(text)
                    break
    usage_notes_combined = " ".join(usage_notes) if usage_notes else ""
    return brand_pref, size_pref, budget, usage_notes_combined

def build_recommendation_text(brand_pref, size_pref, budget, usage_notes):
    """
    Hulpfunctie die op basis van de opgehaalde voorkeuren één of meerdere tv-aanbevelingen opstelt.
    Maakt gebruik van de ingelezen productfeed (df).
    """
    if df is None or df.empty:
        # Als productdata niet beschikbaar is
        return "Excuses, ik kan momenteel geen aanbevelingen doen omdat de productgegevens niet beschikbaar zijn."
    # Werk met een kopie van de data voor filtering
    results = df.copy()
    # Filter op merk (indien voorkeur opgegeven)
    if brand_pref:
        brand_list = []
        if isinstance(brand_pref, str):
            # Merkvoorkeur is één merk
            brand_list = [brand_pref.lower()]
        elif isinstance(brand_pref, list):
            brand_list = [b.lower() for b in brand_pref]
        if brand_list:
            brand_col = None
            for col in df.columns:
                if 'brand' in col.lower() or 'merk' in col.lower():
                    brand_col = col
                    break
            if brand_col:
                mask = pd.Series(False, index=results.index)
                for b in brand_list:
                    mask |= results[brand_col].str.lower().str.contains(b)
                results = results[mask]
    # Filter op schermgrootte (binnen een marge van ±5 inch)
    size_col = None
    if size_pref:
        for col in df.columns:
            if 'inch' in col.lower() or 'size' in col.lower() or 'diagonaal' in col.lower():
                size_col = col
                break
        if size_col:
            # Zorg dat de kolom numeriek is voor vergelijking
            try:
                results[size_col] = pd.to_numeric(results[size_col], errors='coerce')
            except Exception:
                pass
            if pd.api.types.is_numeric_dtype(results[size_col]):
                results = results[(results[size_col] >= size_pref - 5) & (results[size_col] <= size_pref + 5)]
            else:
                # Als grootte niet numeriek is, gebruik tekstvergelijking als noodoplossing
                results = results[results[size_col].astype(str).str.contains(str(int(size_pref)))]
    # Filter op budget (maximale prijs)
    price_col = None
    if budget:
        for col in df.columns:
            if 'price' in col.lower() or 'prijs' in col.lower():
                price_col = col
                break
        if price_col:
            try:
                results[price_col] = pd.to_numeric(results[price_col], errors='coerce')
            except Exception:
                pass
            if pd.api.types.is_numeric_dtype(results[price_col]):
                results = results[results[price_col] <= budget]
            else:
                # Als prijs kolom tekst bevat, verwijder niet-numerieke tekens en vergelijk
                numeric_prices = results[price_col].replace('[^0-9]', '', regex=True).astype(float)
                results = results[numeric_prices <= budget]
    # Als er geen resultaten zijn, versoepel de filters stap voor stap
    if results.empty:
        logging.info("No products found with initial filters. Relaxing criteria for a broader search.")
        results = df.copy()
        # 1. Laat de merkfilter vallen (neem alle merken)
        # (We maken gewoon een volledige kopie hierboven, dus alle merken zijn weer aanwezig.)
        # 2. Verhoog budgetlimiet met 20% (indien budget gegeven)
        if budget and price_col:
            if pd.api.types.is_numeric_dtype(df[price_col]):
                results = results[results[price_col] <= budget * 1.2]
            else:
                numeric_prices = results[price_col].replace('[^0-9]', '', regex=True).astype(float)
                results = results[numeric_prices <= budget * 1.2]
        # 3. Vergroot de marge voor schermgrootte naar ±10 inch
        if size_pref and size_col:
            if pd.api.types.is_numeric_dtype(df[size_col]):
                results = results[(results[size_col] >= size_pref - 10) & (results[size_col] <= size_pref + 10)]
            else:
                results = results[results[size_col].astype(str).str.contains(str(int(size_pref)))]
    # Als er nog steeds geen resultaten zijn, neem de volledige lijst (zodat we iets kunnen aanbevelen)
    if results.empty:
        results = df.copy()
    # Beperk tot maximaal 3 aanbevelingen
    if len(results) > 3:
        results = results.iloc[:3]
    # Bouw de aanbevelingsbericht tekst op
    rec_lines = []
    for _, row in results.iterrows():
        # Haal productnaam en prijs op
        name = str(row.get('Name', row.get('naam', 'Onbekend model')))
        # Zoek de prijswaarde uit de beschikbare kolommen
        price_value = None
        for col in ['Price', 'Prijs', 'price', 'prijs']:
            if col in row and not pd.isna(row[col]):
                price_value = row[col]
                break
        # Converteer prijs naar float voor format, indien mogelijk
        try:
            price_value = float(price_value)
        except Exception:
            # Als de prijs geen getal is, probeer cijfers te extraheren
            import re
            num_match = re.search(r'\d+\.?\d*', str(price_value))
            price_value = float(num_match.group(0)) if num_match else None
        # Verzamel beschrijvingselementen (schermgrootte, type, resolutie)
        desc_parts = []
        # Schermgrootte (indien beschikbaar)
        if size_col and size_col in row and not pd.isna(row[size_col]):
            try:
                size_num = float(row[size_col])
                desc_parts.append(f"{int(size_num)} inch")
            except Exception:
                size_text = str(row[size_col])
                if "inch" in size_text:
                    desc_parts.append(size_text)
        # Type paneel/technologie (bijv. OLED/QLED/LED)
        if 'Type' in row and not pd.isna(row['Type']):
            panel_type = str(row['Type']).strip()
        else:
            # Probeer uit productnaam te halen
            panel_type = ""
            n_lower = name.lower()
            if "oled" in n_lower:
                panel_type = "OLED"
            elif "qled" in n_lower:
                panel_type = "QLED"
            elif "led" in n_lower or "lcd" in n_lower:
                panel_type = "LED"
        if panel_type:
            desc_parts.append(panel_type + " TV")
        # Resolutie (bijv. 4K, 8K, Full HD)
        if 'Resolution' in row and not pd.isna(row['Resolution']):
            resolution = str(row['Resolution']).strip()
        else:
            resolution = ""
            n_upper = name.upper()
            if "8K" in n_upper:
                resolution = "8K"
            elif "4K" in n_upper or "UHD" in n_upper or "ULTRA HD" in n_upper:
                resolution = "4K"
            elif "1080" in n_upper or "FULL HD" in n_upper:
                resolution = "Full HD"
        if resolution:
            # Normaliseer "Ultra HD" naar "4K" voor beknoptheid
            if resolution.lower().startswith("ultra"):
                resolution = "4K"
            desc_parts.append(resolution)
        # Bouw de regel voor dit product
        line = f"- **{name}**"
        if desc_parts:
            line += " (" + ", ".join(desc_parts) + ")"
        if price_value is not None:
            line += f" – Prijs: €{price_value:.2f}"
        rec_lines.append(line)
    # Begin van het aanbevelingsbericht
    recommendation_text = "Op basis van uw voorkeuren raad ik de volgende televisies aan:\n" + "\n".join(rec_lines)
    # Voeg een afsluitende zin toe over het gebruiksdoel (indien bekend)
    usage_str = ""
    usage_notes_lower = usage_notes.lower() if isinstance(usage_notes, str) else ""
    usage_points = []
    if any(word in usage_notes_lower for word in ["game", "gaming", "spel"]):
        usage_points.append("gaming")
    if any(word in usage_notes_lower for word in ["film", "serie", "netflix"]):
        usage_points.append("het kijken van films en series")
    if "sport" in usage_notes_lower:
        usage_points.append("sportwedstrijden")
    if any(word in usage_notes_lower for word in ["nieuws", "dagelijks"]):
        usage_points.append("dagelijks tv-kijken")
    # Verwijder duplicaten terwijl volgorde behouden blijft
    seen = set()
    usage_points = [u for u in usage_points if not (u in seen or seen.add(u))]
    if usage_points:
        if len(usage_points) == 1:
            usage_str = usage_points[0]
        elif len(usage_points) == 2:
            usage_str = f"{usage_points[0]} en {usage_points[1]}"
        else:
            usage_str = ", ".join(usage_points[:-1]) + " en " + usage_points[-1]
    if usage_str:
        if len(rec_lines) == 1:
            recommendation_text += f"\n\nDit model is uitstekend geschikt voor {usage_str}."
        else:
            recommendation_text += f"\n\nDeze opties zijn uitstekend geschikt voor {usage_str}."
    # Sluit af met een vriendelijke vraag of er iets bij zit en verdere hulp
    recommendation_text += "\n\nZit er iets voor u bij? Laat het gerust weten als u vragen heeft over deze televisies!"
    return recommendation_text

@app.route("/chat", methods=["POST"])
def chat():
    # Controleer of de aanvraag JSON bevat
    if not request.is_json:
        return jsonify({"error": "Ongeldig request formaat, JSON verwacht."}), 400
    data = request.get_json()
    user_messages = data.get("messages")
    single_message = data.get("message")
    # Bouw conversatiegeschiedenis op met system prompt
    conversation = [{"role": "system", "content": system_prompt}]
    if user_messages:
        # Voeg alle door de gebruiker verstrekte berichten toe (behalve eventuele system-berichten)
        for msg in user_messages:
            role = msg.get("role")
            content = msg.get("content")
            if role and content is not None:
                if role == "system":
                    continue  # negeer system-berichten van de gebruiker, we gebruiken onze eigen system prompt
                conversation.append({"role": role, "content": content})
    elif single_message:
        # Enkel bericht zonder geschiedenis
        conversation.append({"role": "user", "content": single_message})
    else:
        return jsonify({"error": "Geen bericht ontvangen."}), 400
    # Bepaal of we aanbevelingen moeten doen op basis van de laatste gebruikersinvoer
    last_user_msg = None
    for msg in reversed(conversation):
        if msg["role"] == "user":
            last_user_msg = msg["content"].lower()
            break
    recommend_trigger = False
    if last_user_msg:
        # Controleer op trefwoorden die duiden op verzoek om advies/aanbeveling
        trigger_words = ["aanbevel", "aanraden", "advies", "recommend", "suggest", "welke tv", "wat raad", "kopen?"]
        confirm_words = ["ja", "graag", "yes", "sure", "ok", "okay", "doe maar", "prima"]
        if any(word in last_user_msg for word in trigger_words):
            recommend_trigger = True
        elif last_user_msg.strip() in confirm_words:
            # Als de gebruiker bevestigend antwoordt (bv. "ja graag") op een aanbod voor advies
            if len(conversation) >= 2 and conversation[-2]["role"] == "assistant":
                prev_assistant = conversation[-2]["content"].lower()
                if any(w in prev_assistant for w in ["zal ik", "advies", "aanbeveling", "aanraden"]):
                    recommend_trigger = True
    # Als aanbevelingstrigger geactiveerd is, genereer aanbevelingen
    if recommend_trigger:
        brand_pref, size_pref, budget, usage_notes = parse_preferences_from_conversation(conversation)
        logging.info(f"Recommendation triggered. Preferences parsed: brand={brand_pref}, size={size_pref}, budget={budget}, usage={usage_notes}")
        recommendation_message = build_recommendation_text(brand_pref, size_pref, budget, usage_notes)
        return jsonify({"assistant": recommendation_message})
    # Anders, stuur het bericht door naar de OpenAI API voor normale conversatie (vragen stellen/beantwoorden)
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

# Optionele health-check route
@app.route("/", methods=["GET"])
def index():
    return "AI keuzehulp voor televisies is actief."

# Globale error handler voor ongehandelde exceptions (zorgt dat CORS headers ook dan aanwezig zijn)
@app.errorhandler(Exception)
def handle_exception(e):
    logging.error(f"Unhandled exception: {e}")
    return jsonify({"error": "Interne serverfout."}), 500

# Start de Flask applicatie (voor lokaal draaien; in Cloud Run wordt gunicorn gebruikt)
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
