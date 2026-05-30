// Navigation Logic
// No specific JS needed for navigation in MPA mode as we use standard links.

// Prevent double-tap zoom on buttons
document.addEventListener('touchstart', function() {}, false);

// Handle viewport meta tag for mobile
function optimizeViewport() {
    const viewport = document.querySelector('meta[name="viewport"]');
    if (viewport) {
        viewport.setAttribute('content', 'width=device-width, initial-scale=1.0, viewport-fit=cover, maximum-scale=5.0, user-scalable=yes');
    }
}

// Initialize on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', optimizeViewport);
} else {
    optimizeViewport();
}


// Analysis Logic
async function analyzeContent() {
    const textInput = document.getElementById('input-text');
    if (!textInput) return;
    
    const text = textInput.value.trim();
    const btn = document.getElementById('analyze-btn');
    const btnText = document.getElementById('btn-text');
    const loader = document.getElementById('btn-loader');
    const resultsArea = document.getElementById('results-area');

    if (!text) {
        showErrorMessage("Please enter some text to analyze.");
        return;
    }

    if (text.length < 10) {
        showErrorMessage("Please enter at least 10 characters to analyze.");
        return;
    }

    // UI Loading State
    if (btn) btn.disabled = true;
    if (btnText) btnText.classList.add('hidden');
    if (loader) loader.classList.remove('hidden');
    if (resultsArea) resultsArea.classList.add('hidden');

    try {
        const response = await fetch('/api/analyze', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ text: text })
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `Server error: ${response.status}`);
        }

        const data = await response.json();
        renderResults(data);
        if (resultsArea) resultsArea.classList.remove('hidden');

    } catch (error) {
        console.error("Analysis failed:", error);
        showErrorMessage(error.message || "Failed to analyze content. Please try again.");
    } finally {
        // Reset UI
        if (btn) btn.disabled = false;
        if (btnText) btnText.classList.remove('hidden');
        if (loader) loader.classList.add('hidden');
    }
}

function showErrorMessage(message) {
    const resultsArea = document.getElementById('results-area');
    if (!resultsArea) {
        alert(message);
        return;
    }
    
    resultsArea.classList.remove('hidden');
    const errorDiv = document.createElement('div');
    errorDiv.className = 'result-card';
    errorDiv.style.borderColor = '#dc2626';
    errorDiv.innerHTML = `
        <div class="card-top">
            <div class="brand">
                <div class="brand-icon danger">
                    <i data-feather="alert-circle"></i>
                </div>
                <div>
                    <p class="brand-name">Error</p>
                    <span class="meta-text">Analysis failed</span>
                </div>
            </div>
        </div>
        <p style="color: #dc2626; margin: 0;">${message}</p>
    `;
    
    const resultsGrid = resultsArea.querySelector('.results-grid');
    if (resultsGrid) {
        resultsGrid.innerHTML = '';
        resultsGrid.appendChild(errorDiv);
    }
}

function renderResults(data) {
    const resultsArea = document.getElementById('results-area');
    resultsArea.classList.remove('hidden');

    // Score + pills
    const scoreVal = document.getElementById('score-value');
    const emotionPill = document.getElementById('emotion-pill');
    const credibilityPill = document.getElementById('credibility-pill');
    const riskLabel = document.getElementById('risk-label');
    const timestamp = document.getElementById('analysis-timestamp');

    const score = typeof data.misinformation_score === 'number' ? data.misinformation_score : '--';
    scoreVal.innerText = score;

    let color = '#10B981';
    let riskText = 'Low risk · information appears stable.';
    if (score !== '--' && score > 50) {
        color = '#DC2626';
        riskText = 'High risk · verify immediately.';
    } else if (score !== '--' && score > 20) {
        color = '#F59E0B';
        riskText = 'Moderate risk · cross-check claims.';
    }

    scoreVal.style.color = color;
    if (riskLabel) {
        riskLabel.innerText = riskText;
        riskLabel.style.color = color;
    }

    if (emotionPill) {
        emotionPill.innerText = `Emotion: ${data.emotional_intensity || '--'}`;
    }
    if (credibilityPill) {
        credibilityPill.innerText = `Credibility: ${data.credibility_rating || '--'}`;
    }
    if (timestamp) {
        const now = new Date();
        timestamp.innerText = now.toLocaleString('en-IN', {
            hour12: true,
            hour: '2-digit',
            minute: '2-digit',
            day: 'numeric',
            month: 'short'
        });
    }

    document.getElementById('summary-text').innerText = data.summary || 'No summary available.';

    // Biases
    const biasList = document.getElementById('bias-list');
    biasList.innerHTML = '';
    if (data.biases && data.biases.length > 0) {
        data.biases.forEach(bias => {
            const card = document.createElement('div');
            card.className = 'bias-card';
            card.innerHTML = `
                <div class="bias-card-title">${bias.type || 'Bias'}</div>
                <p>"${bias.text_snippet || '—'}"</p>
                <small>${bias.explanation || ''}</small>
            `;
            biasList.appendChild(card);
        });
    } else {
        const empty = document.createElement('div');
        empty.className = 'bias-card';
        empty.innerText = 'No significant biases detected.';
        biasList.appendChild(empty);
    }

    // Recommendations
    const recList = document.getElementById('rec-list');
    recList.innerHTML = '';
    if (data.recommendations && data.recommendations.length > 0) {
        data.recommendations.forEach(rec => {
            const pill = document.createElement('span');
            pill.className = 'pill-chip';
            pill.innerText = rec;
            recList.appendChild(pill);
        });
    } else {
        const pill = document.createElement('span');
        pill.className = 'pill-chip';
        pill.innerText = 'No recommendations returned.';
        recList.appendChild(pill);
    }

    // Reflection Steps
    const reflectionsWrapper = document.getElementById('reflection-steps');
    const reflectionsList = document.getElementById('reflection-list');
    if (reflectionsWrapper && reflectionsList) {
        reflectionsList.innerHTML = '';
        if (Array.isArray(data.reflection_steps) && data.reflection_steps.length > 0) {
            reflectionsWrapper.classList.remove('hidden');
            data.reflection_steps.forEach((step, index) => {
                const stepName = step.step || `Step ${index + 1}`;
                const stepPrompt = step.prompt || 'Focus on what feels most important right now.';
                const stepResponse = step.response || 'No guidance provided for this step.';
                const li = document.createElement('li');
                li.className = 'reflection-item';
                li.innerHTML = `
                    <div class="reflection-step-header">
                        <span class="reflection-step-name">${stepName}</span>
                        <small class="reflection-step-prompt">${stepPrompt}</small>
                    </div>
                    <p class="reflection-response">${stepResponse}</p>
                `;
                reflectionsList.appendChild(li);
            });
        } else {
            reflectionsWrapper.classList.add('hidden');
        }
    }
}

// Simple smooth scroll function
function scrollToSection(id) {
    const element = document.getElementById(id);
    if (element) {
        window.scrollTo({
            top: element.offsetTop - 20, // Small offset from the top
            behavior: 'smooth'
        });
    }
}

// Initialize scroll functionality
document.addEventListener('DOMContentLoaded', () => {
    // Handle click on scroll indicator
    const scrollIndicator = document.querySelector('.scroll-indicator');
    if (scrollIndicator) {
        scrollIndicator.addEventListener('click', (e) => {
            e.preventDefault();
            scrollToSection('dashboard');
        });
    }

    // Handle window scroll event
    window.addEventListener('scroll', function() {
        // This ensures the scroll event isn't being prevented
        console.log('Scrolling...');
    });

    // Chatbot wiring
    initChatbot();
});

// Chatbot Logic
const chatState = {
    history: [],
    isLoading: false
};

function appendChatMessage(role, text) {
    const container = document.getElementById('chat-messages');
    if (!container) return;

    const bubble = document.createElement('div');
    bubble.className = `message ${role === 'user' ? 'user-message' : 'bot-message'}`;
    bubble.textContent = text;
    bubble.setAttribute('role', 'article');
    container.appendChild(bubble);
    
    // Scroll to bottom with smooth behavior
    setTimeout(() => {
        container.scrollTop = container.scrollHeight;
    }, 0);
}

function toggleTypingIndicator(show) {
    const indicator = document.getElementById('typing-indicator');
    if (!indicator) return;
    indicator.style.display = show ? 'block' : 'none';
}

function initChatbot() {
    const form = document.getElementById('chat-form');
    const input = document.getElementById('user-input');
    const messages = document.getElementById('chat-messages');
    
    if (!form || !input || !messages) return;

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        
        if (chatState.isLoading) return;
        
        const text = input.value.trim();
        if (!text) return;

        appendChatMessage('user', text);
        chatState.history.push({ role: 'user', text });
        input.value = '';
        input.disabled = true;
        chatState.isLoading = true;
        toggleTypingIndicator(true);

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: text,
                    history: chatState.history
                })
            });

            if (!response.ok) {
                throw new Error(`Chat service error: ${response.status}`);
            }

            const data = await response.json();
            const reply = data.reply || 'I ran into an issue responding. Could you try again?';
            appendChatMessage('model', reply);
            chatState.history.push({ role: 'model', text: reply });
        } catch (error) {
            console.error('Chat error:', error);
            appendChatMessage('model', 'Sorry, I could not reach the AI right now. Please try again in a moment.');
        } finally {
            toggleTypingIndicator(false);
            input.disabled = false;
            chatState.isLoading = false;
            input.focus();
        }
    });
}

// Preloader
function initPreloader() {
    const preloader = document.querySelector('.preloader-container');
    if (!preloader) return;

    document.body.classList.add('preloader-active');

    function hidePreloader() {
        if (!preloader) return;

        // Re-enable scrolling immediately to avoid being stuck
        document.body.classList.remove('preloader-active');

        // Small delay for smoother start of transition
        requestAnimationFrame(() => {
            preloader.classList.add('hidden');
        });

        const onTransitionEnd = () => {
            preloader.style.display = 'none';
            preloader.removeEventListener('transitionend', onTransitionEnd);
        };

        preloader.addEventListener('transitionend', onTransitionEnd, { once: true });

        // Fallback in case transitionend fails to fire
        setTimeout(() => {
            preloader.style.display = 'none';
        }, 1200);
    }

    let pageLoaded = false;
    const MIN_LOAD_TIME = 3500;
    const loadStartTime = Date.now();

    function handleLoad() {
        if (pageLoaded) return;
        pageLoaded = true;

        const loadTime = Date.now() - loadStartTime;
        const remainingTime = Math.max(0, MIN_LOAD_TIME - loadTime);

        setTimeout(hidePreloader, remainingTime);
    }

    if (document.readyState === 'complete') {
        setTimeout(handleLoad, 0);
    } else {
        window.addEventListener('load', handleLoad);
    }

    const fallbackTimeout = setTimeout(() => {
        if (!pageLoaded) {
            handleLoad();
        }
    }, MIN_LOAD_TIME + 2000);

    return () => {
        window.removeEventListener('load', handleLoad);
        clearTimeout(fallbackTimeout);
    };
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPreloader);
} else {
    initPreloader();
}
