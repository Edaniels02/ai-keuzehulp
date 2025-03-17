import os
import json
from flask import Flask, request, jsonify
import openai

app = Flask(__name__)

# -- CORS-instellingen zodat je vanuit GitHub Pages kunt aanroepen --
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    return response

# -- OpenAI API key uit omgevingsvariabele --
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# -- Vragen die de AI stap voor stap stelt --
questions = [
    "Waarvoor wil je de TV gebruiken? (Dagelijks TV-kijken, Films & Series, Sport, Gaming, Weet ik niet)",
    "Welk formaat zoek je? (Bijv. 43\", 50\", 55\", 65\", 75\"+)",
    "Heb je voorkeur voor een schermtechnologie? (OLED, QLED, LED, Weet ik niet)",
    "Wat is je budget? (Tot €1000, €1000-€1500, Meer dan €1500)",
    "Wil je extra smartfuncties of specifieke features? (AirPlay, Google TV, HDMI 2.1, Geen voorkeur)"
]

@app.route("/", methods=["GET"])
def home():
    return "AI Keuzehulp is running! Probeer /ask via POST."

@app.route("/ask", methods=["POST"])
def ask():
    """
    Ontvangt:
      - questionIndex: index van de huidige vraag
      - answers: lijst met alle gegeven antwoorden tot nu toe
    Stuurt terug:
      - nextQuestion: de volgende vraag (of eindboodschap)
      - newQuestionIndex: de nieuwe vraagindex
      - done: True/False of we klaar zijn
    """
    data = request.json
    question_index = data.get("questionIndex", 0)
    answers = data.get("answers", [])

    if question_index < len(questions):
        # We hebben nog vragen over
        next_question = questions[question_index]
        return jsonify({
            "nextQuestion": next_question,
            "newQuestionIndex": question_index,
            "done": False
        })
    else:
        # Alle vragen zijn beantwoord, genereer een advies met OpenAI
        try:
            # Bouw een prompt met alle antwoorden
            # (Je kunt dit aanpassen aan je eigen smaak)
            prompt = f"""
            Jij bent de AI Keuzehulp van Expert.nl. Op basis van de volgende antwoorden geef je een TV-advies.
            Antwoorden van de gebruiker:
            1) {answers[0]}
            2) {answers[1]}
            3) {answers[2]}
            4) {answers[3]}
            5) {answers[4]}

            Geef nu een concreet TV-advies op basis van deze antwoorden.
            """

            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Je bent een AI keuzehulp voor Expert.nl."},
                    {"role": "user", "content": prompt}
                ]
            )
            final_answer = response["choices"][0]["message"]["content"].strip()
        except Exception as e:
            final_answer = f"Er trad een fout op bij het genereren van het advies: {str(e)}"

        return jsonify({
            "nextQuestion": final_answer,
            "newQuestionIndex": question_index,
            "done": True
        })

if __name__ == "__main__":
    # Run lokaal, voor Cloud Run is dit niet nodig
    app.run(debug=True, host='0.0.0.0', port=8080)
