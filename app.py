import os
import json
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from openai import OpenAI
from dotenv import load_dotenv

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

# Configure OpenRouter API
API_KEY = os.getenv("OPENROUTER_API_KEY") or os.getenv("GEMINI_API_KEY") # Fallback to existing key in env if renamed
if not API_KEY:
    print("Warning: OPENROUTER_API_KEY not found in environment variables.")

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=API_KEY,
)

MODEL_NAME = "google/gemini-2.0-flash-001"

# -----------------------------
# CHAT SYSTEM PROMPT
# -----------------------------
CHAT_SYSTEM_PROMPT = """
You are ClarityBot — a warm AI companion who gives short, supportive, and clear psychological guidance.
You are NOT a therapist. Never claim to be one.

Your replies must ALWAYS be:
- Short (5–7 lines max)
- In bullet points ONLY
- Warm, gentle, and supportive
- Easy to understand (no jargon unless explained simply)

When replying:
1. Briefly validate the user’s feelings.
2. Identify the thinking pattern (if visible).
3. Give a simple, calmer reframe.
4. Suggest 2–3 grounding/practical steps.
5. Ask ONE soft follow-up question.

Tone:
- Human, soft, kind
- Never lecture
- Never write long paragraphs
- Never overwhelm the user

If user expresses self-harm or crisis:
- Stay calm
- Encourage reaching out to real humans immediately
- Never give harmful instructions
"""

# -----------------------------
# ANALYZER SYSTEM PROMPT
# -----------------------------
SYSTEM_PROMPT = """
You are an expert cognitive scientist, fact-checker, and critical thinking coach.
Always guide the user through the following FIVE reflection steps before drawing conclusions.

Return a JSON object with this exact structure (and nothing else):
{
  "misinformation_score": integer 0-100,
  "credibility_rating": "High" | "Medium" | "Low",
  "emotional_intensity": "Low" | "Medium" | "High",
  "summary": string,
  "biases": [
    {"type": string, "text_snippet": string, "explanation": string}
  ],
  "recommendations": [string],
  "reflection_steps": [
    {
      "step": "Pause & Breathe",
      "prompt": "Before reacting, take a moment. What is the content claiming? Write it in your own words.",
      "placeholder": "The content claims that...",
      "response": string written in second person encouraging deliberation
    },
    {
      "step": "Identify Emotions",
      "prompt": "What emotions does this content trigger? Are you feeling scared, angry, excited, or validated?",
      "placeholder": "This makes me feel...because...",
      "response": string acknowledging emotional impact
    },
    {
      "step": "Question the Source",
      "prompt": "Who created this? What might be their motivation? Is this a reliable, unbiased source?",
      "placeholder": "The source is...Their motivation might be...",
      "response": string that inspects credibility
    },
    {
      "step": "Consider Alternatives",
      "prompt": "What's an opposing viewpoint? What would someone who disagrees say? What evidence would challenge this?",
      "placeholder": "Someone might argue that...The counter-evidence could be...",
      "response": string that fairly represents counterpoints
    },
    {
      "step": "Final Reflection",
      "prompt": "After this analysis, has your initial reaction changed? What will you do with this information?",
      "placeholder": "My conclusion is...I will...",
      "response": string summarizing how to act going forward
    }
  ]
}

Blend psychological safety with analytical rigor. NEVER skip or combine steps. Each response should prompt the user to pause, think, and articulate their reasoning in depth.

Scoring Logic Guide:
- Base Score: 0 (Safe)
- High Emotional Intensity: +15
- Logical Fallacies: +10 each
- Cognitive Distortions: +5 each
- Aggressive/Polarizing Language: +10
- Lack of Citations/Evidence for Claims: +10

Thresholds:
- 0-20: High Credibility (Green)
- 21-50: Medium Credibility (Yellow)
- 51+: Low Credibility / High Risk (Red)
"""

# -----------------------------
# HELPER FUNCTIONS
# -----------------------------
def _clean_response(raw_text: str):
    """Remove ```json code blocks."""
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.replace("```json", "").replace("```", "").strip()
    return cleaned

def _call_openrouter(messages, temperature=0.7, response_format=None, max_tokens=2000):
    try:
        kwargs = {
            "model": MODEL_NAME,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format == "json":
            # Just specify it in instructions, OpenRouter models vary in support for response_format={"type":"json_object"}
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
        
        raw_output = _call_openrouter(messages, temperature=0.7, response_format="json", max_tokens=4000)
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
    if score >= 80: analysis = "🌟 Excellent reflection! Your responses show deep thinking and self-awareness."
    elif score >= 60: analysis = "💡 Good job! Your reflection shows solid effort."
    elif score >= 40: analysis = "📝 You've made a good start."
    else: analysis = "🌱 This is a beginning. Reflection is a skill that grows with practice."
    
    response_count = len(responses)
    if response_count < 3: analysis += "\n\nYou've completed a few steps. Completing more steps will provide a more comprehensive reflection."
    emotions = ['happy', 'sad', 'angry', 'excited', 'nervous', 'proud', 'ashamed', 'grateful']
    has_emotion = any(emotion in str(responses).lower() for emotion in emotions)
    if not has_emotion and response_count > 0: analysis += "\n\nTip: Try to name specific emotions you're feeling. This can help with emotional awareness."
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
        raw = _call_openrouter([{"role": "user", "content": prompt}], temperature=0.6, response_format="json", max_tokens=1024)
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
        question = _call_openrouter([{"role": "user", "content": prompt}], temperature=0.6, max_tokens=200).strip()
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
        reply_text = _call_openrouter(messages, temperature=0.5, max_tokens=700).strip()
        return jsonify({"reply": reply_text})
    except Exception as e:
        return jsonify({"error": "Failed to chat with AI", "details": str(e)}), 500

# -----------------------------
# START SERVER
# -----------------------------
if __name__ == '__main__':
    print("Server running at http://localhost:5000")
    app.run(debug=True, port=5000)
