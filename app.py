import os
import json
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from openai import OpenAI
from dotenv import load_dotenv

def _load_prompt(name: str) -> str:
    return (Path(__file__).parent / "prompts" / f"{name}.st").read_text(encoding="utf-8").strip()

CHAT_SYSTEM_PROMPT = _load_prompt("chat")
ANALYZER_SYSTEM_PROMPT = _load_prompt("analyzer")
REFLECTION_SYSTEM_PROMPT = _load_prompt("reflection")

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)  # Enable CORS for all routes

# Security headers for deployment
@app.after_request
def set_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response

# Configure Groq API
API_KEY = os.getenv("GROQ_API_KEY")
if not API_KEY:
    print("Warning: GROQ_API_KEY not found in environment variables.")

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=API_KEY,
)

MODEL_ANALYSIS = "llama-3.3-70b-versatile"   # structured JSON output — needs quality
MODEL_FAST     = "llama-3.1-8b-instant"       # chat and reflection — speed over scale

SYSTEM_PROMPT = ANALYZER_SYSTEM_PROMPT  # alias used by /api/analyze

# -----------------------------
# HELPER FUNCTIONS
# -----------------------------
def _clean_response(raw_text: str):
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.replace("```json", "").replace("```", "").strip()
    return cleaned

def _call_groq(messages, temperature=0.7, response_format=None, max_tokens=2000, model=None):
    try:
        kwargs = {
            "model": model or MODEL_ANALYSIS,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format == "json":
            pass
            
        completion = client.chat.completions.create(**kwargs)
        return completion.choices[0].message.content
    except Exception as e:
        raise ValueError(f"OpenRouter API error: {e}")

# -----------------------------
# ROUTES
# -----------------------------
@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

# -----------------------------
# ANALYZE CONTENT ENDPOINT
# -----------------------------
@app.route('/api/analyze', methods=['POST'])
def analyze_content():
    if not API_KEY:
        return jsonify({"error": "Server error: API key missing"}), 500

    data = request.json
    text_to_analyze = data.get('text', '').strip()

    if not text_to_analyze:
        return jsonify({"error": "No text provided"}), 400

    try:
        prompt = f"""
        Please analyze the following text for cognitive load, clarity, and potential biases. 
        Return the analysis in the specified JSON format.
        
        Text to analyze:
        {text_to_analyze}
        """
        
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
        
        raw_output = _call_groq(messages, temperature=0.5, response_format="json", max_tokens=1200)
        cleaned = _clean_response(raw_output)

        analysis = json.loads(cleaned)
        
        if 'misinformation_score' not in analysis: analysis['misinformation_score'] = 50
        if 'credibility_rating' not in analysis: analysis['credibility_rating'] = 'Medium'
        if 'emotional_intensity' not in analysis: analysis['emotional_intensity'] = 'Medium'
        if 'biases' not in analysis: analysis['biases'] = []
        if 'recommendations' not in analysis: analysis['recommendations'] = ["No specific recommendations available."]
        if 'reflection_steps' not in analysis: analysis['reflection_steps'] = []
        if 'summary' not in analysis: analysis['summary'] = "No summary available."

        return jsonify(analysis)

    except json.JSONDecodeError as e:
        return jsonify({"error": "Invalid JSON response from AI", "details": str(e), "raw_output": raw_output if 'raw_output' in locals() else None}), 500
    except Exception as e:
        print("Analysis error:", str(e))
        return jsonify({"error": "An error occurred during analysis", "details": str(e)}), 500

# -----------------------------
# REFLECTION ENDPOINTS
# -----------------------------
def _sanitize_question_map(raw_questions):
    sanitized = {}
    for i in range(1, 6):
        key = str(i)
        value = ''
        if isinstance(raw_questions, dict) and key in raw_questions:
            value = str(raw_questions[key]).strip()
        sanitized[key] = value
    return sanitized

def _calculate_reflection_score(responses):
    if not responses: return 0
    total_score = 0
    max_possible = len(responses) * 20
    for response in responses.values():
        length_score = min(len(str(response).strip()) / 2, 20)
        question_bonus = min(str(response).count('?') * 2, 5)
        reasoning_words = ['because', 'since', 'as', 'therefore', 'thus', 'hence']
        reasoning_bonus = min(sum(word in str(response).lower() for word in reasoning_words) * 2, 5)
        total_score += min(length_score + question_bonus + reasoning_bonus, 20)
    return min(round((total_score / max_possible) * 100, 1), 100) if max_possible > 0 else 0

def _generate_analysis(score, responses):
    if score >= 80: analysis = "Excellent reflection. Your responses show deep thinking and self-awareness."
    elif score >= 60: analysis = "Good effort. Your reflection shows solid engagement."
    elif score >= 40: analysis = "A good start. Keep building on these thoughts."
    else: analysis = "This is a beginning. Reflection is a skill that grows with practice."

    response_count = len(responses)
    if response_count < 3: analysis += "\n\nCompleting more steps will give you a more complete picture."
    emotions = ['happy', 'sad', 'angry', 'excited', 'nervous', 'proud', 'ashamed', 'grateful']
    has_emotion = any(emotion in str(responses).lower() for emotion in emotions)
    if not has_emotion and response_count > 0: analysis += "\n\nTip: Try naming specific emotions. It helps build emotional awareness."
    return analysis

@app.route('/api/reflection/questions', methods=['POST'])
def generate_reflection_questions():
    if not API_KEY: return jsonify({"error": "Server error: API key missing"}), 500
    data = request.json or {}
    user_text = (data.get('text') or '').strip()
    if len(user_text) < 20: return jsonify({"error": "Please provide at least a short paragraph (20+ characters)."}), 400

    prompt = f"""
You are an AI helping the user think clearly and reduce cognitive distortions.

Your goal:
- Ask exactly 5 reflection questions.
- Steps MUST adapt based on the user's previous answer.
- The tone must be calm, supportive, simple, non-judgmental.
- DO NOT give long paragraphs—give short, simple questions.

User content:
"{user_text}"

Output format ONLY (as JSON, nothing else):
{{
 "1": "question text",
 "2": "next question",
 "3": "next question",
 "4": "next question",
 "5": "final question"
}}
"""
    try:
        raw = _call_groq([{"role": "system", "content": REFLECTION_SYSTEM_PROMPT}, {"role": "user", "content": prompt}], temperature=0.5, response_format="json", max_tokens=400, model=MODEL_FAST)
        cleaned = _clean_response(raw)
        questions = json.loads(cleaned)
        return jsonify({"questions": _sanitize_question_map(questions)})
    except Exception as e:
        print("Reflection question error:", e)
        return jsonify({"error": "Failed to generate reflection questions", "details": str(e)}), 500

@app.route('/api/reflection/analyze', methods=['POST'])
def analyze_reflection():
    try:
        data = request.json or {}
        responses = data.get('responses', {})
        score = _calculate_reflection_score(responses)
        analysis = _generate_analysis(score, responses)
        return jsonify({'score': score, 'analysis': analysis, 'responses': responses})
    except Exception as e:
        return jsonify({"error": "Failed to analyze reflection", "details": str(e)}), 500

@app.route('/api/reflection/next', methods=['POST'])
def generate_next_reflection_question():
    if not API_KEY: return jsonify({"error": "Server error: API key missing"}), 500
    data = request.json or {}
    current_step = data.get('current_step')
    answer = (data.get('answer') or '').strip()
    try: current_step = int(current_step)
    except: return jsonify({"error": "current_step must be an integer between 1 and 5."}), 400
    if current_step < 1 or current_step >= 5: return jsonify({"error": "current_step must be between 1 and 4."}), 400
    next_step = current_step + 1

    prompt = f"""
You are an AI guiding a 5-step emotional clarity reflection. Tone: calm, supportive, simple, non-judgmental.
User just answered Step {current_step}:
"{answer}"

Now generate the NEXT SINGLE QUESTION ONLY (Step {next_step}) in 1 sentence.
ONLY return the question text. No explanation.
"""
    try:
        question = _call_groq([{"role": "system", "content": REFLECTION_SYSTEM_PROMPT}, {"role": "user", "content": prompt}], temperature=0.5, max_tokens=100, model=MODEL_FAST).strip()
        if not question: raise ValueError("Empty question returned")
        return jsonify({"question": question})
    except Exception as e:
        return jsonify({"error": "Failed to adapt next question", "details": str(e)}), 500

# -----------------------------
# CHAT ENDPOINT
# -----------------------------
@app.route('/api/chat', methods=['POST'])
def chat_with_ai():
    if not API_KEY: return jsonify({"error": "Server error: API key missing"}), 500
    data = request.json or {}
    user_message = data.get('message', '').strip()
    history = data.get('history', [])
    if not user_message: return jsonify({"error": "No message provided"}), 400

    messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]
    if isinstance(history, list):
        for turn in history[-6:]:
            text_val = str(turn.get('text', '')).strip()
            if not text_val: continue
            role = 'assistant' if turn.get('role') == 'model' else 'user'
            messages.append({"role": role, "content": text_val})
            
    messages.append({"role": "user", "content": user_message})

    try:
        reply_text = _call_groq(messages, temperature=0.5, max_tokens=250, model=MODEL_FAST).strip()
        return jsonify({"reply": reply_text})
    except Exception as e:
        return jsonify({"error": "Failed to chat with AI", "details": str(e)}), 500

# -----------------------------
# START SERVER
# -----------------------------
if __name__ == '__main__':
    print("Server running at http://localhost:5000")
    app.run(debug=True, port=5000)
