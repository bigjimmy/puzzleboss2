<?php
require('puzzlebosslib.php');

// Get authenticated username
$username = isset($_SERVER['REMOTE_USER']) ? $_SERVER['REMOTE_USER'] : 'anonymous';

// Get LLM model and system instruction from config
$gemini_model = $config->GEMINI_MODEL ?? 'unknown';
$gemini_instruction = $config->GEMINI_SYSTEM_INSTRUCTION ?? '';
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>PuzzBot - Hunt Assistant</title>
    <link rel="stylesheet" href="./pb-ui.css">
    <style>
        /* Chat UI specific color palette */
        :root {
            --chat-container-bg: #f9f9f9;    /* Chat container background */
            --chat-user-bg: #f0e6ff;         /* User message background (purple) */
            --chat-user-border: #d9ccff;     /* User message border */
            --chat-error-bg: #ffe6e6;        /* Error message background */
            --chat-error-border: #ffcccc;    /* Error message border */
            --chat-error-text: #cc0000;      /* Error message text */
            --chat-warning-bg: #fff3cd;      /* Warning background */
            --chat-warning-border: #ffc107;  /* Warning border */
            --chat-warning-text: #856404;    /* Warning text */
        }

        /* Fix whitespace between inline-block navbar elements */
        .nav-links {
            font-size: 0;
        }

        .nav-links a {
            font-size: 1rem;
        }

        .user-info {
            color: #666;
            font-size: 0.9em;
        }

        .chat-container {
            max-width: 900px;
            width: 100%;
            margin: 0 auto;
            padding: 1rem;
            display: none;
            flex-direction: column;
            gap: 1rem;
            overflow-y: auto;
            max-height: 500px;
            background: var(--chat-container-bg);
            border: 1px solid #ddd;
            border-radius: 4px;
        }

        .chat-container.has-messages {
            display: flex;
        }

        .message {
            padding: 1rem 1.25rem;
            border-radius: 1rem;
            max-width: 85%;
            line-height: 1.5;
            animation: fadeIn 0.3s ease;
            color: #333;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .message.bot {
            background: #e6f2ff;
            border: 1px solid #cce5ff;
            align-self: flex-start;
            border-bottom-left-radius: 0.25rem;
        }

        .message.user {
            background: var(--chat-user-bg);
            border: 1px solid var(--chat-user-border);
            align-self: flex-end;
            border-bottom-right-radius: 0.25rem;
        }

        .message.error {
            background: var(--chat-error-bg);
            border: 1px solid var(--chat-error-border);
            color: var(--chat-error-text);
            align-self: flex-start;
        }

        .message.loading {
            background: #f5f5f5;
            border: 1px solid #ddd;
            align-self: flex-start;
            color: #666;
        }

        .message.loading::after {
            content: '...';
            animation: dots 1.5s infinite;
        }

        @keyframes dots {
            0%, 20% { content: '.'; }
            40% { content: '..'; }
            60%, 100% { content: '...'; }
        }

        .message code {
            background: rgba(0, 0, 0, 0.08);
            padding: 0.15rem 0.4rem;
            border-radius: 0.25rem;
            font-family: 'Courier New', Courier, monospace;
            font-size: 0.9em;
        }

        .message ul, .message ol {
            margin: 0.5rem 0;
            padding-left: 1.5rem;
        }

        .message li {
            margin: 0.25rem 0;
        }

        .message strong {
            color: #000;
        }
        
        .input-area {
            background: white;
            padding: 1rem 0;
            margin-top: 1rem;
        }

        .input-wrapper {
            display: flex;
            gap: 0.75rem;
        }

        .disclaimers {
            margin-top: 1rem;
            padding: 1rem;
            background: var(--chat-warning-bg);
            border: 1px solid var(--chat-warning-border);
            border-radius: 4px;
        }

        .disclaimers ul {
            margin: 0;
            padding-left: 1.5rem;
            color: var(--chat-warning-text);
        }

        .disclaimers li {
            margin: 0.5rem 0;
        }

        #query-input {
            flex: 1;
            padding: 0.875rem 1.25rem;
            border: 2px solid #ccc;
            border-radius: 2rem;
            background: white;
            color: #333;
            font-size: 1rem;
            outline: none;
            transition: border-color 0.2s;
        }

        #query-input:focus {
            border-color: #0066cc;
        }

        #query-input::placeholder {
            color: #999;
        }

        #send-btn {
            padding: 0.875rem 1.75rem;
            background: #0066cc;
            color: white;
            border: none;
            border-radius: 2rem;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s, transform 0.1s;
        }

        #send-btn:hover {
            background: #0052a3;
        }

        #send-btn:active {
            transform: scale(0.98);
        }

        #send-btn:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        
        .example-chips {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
        }

        .example-chip {
            background: white;
            border: 1px solid #ccc;
            padding: 0.5rem 1rem;
            border-radius: 1rem;
            cursor: pointer;
            transition: border-color 0.2s, background 0.2s;
            color: #333;
        }

        .example-chip:hover {
            border-color: #0066cc;
            background: #f0f7ff;
        }

        .model-badge {
            display: inline-block;
            background: #e6f2ff;
            border: 1px solid #cce5ff;
            padding: 0.25rem 0.75rem;
            border-radius: 1rem;
            font-family: 'Courier New', Courier, monospace;
            font-size: 0.85rem;
            color: #333;
        }

        .system-instruction {
            margin-top: 1.5rem;
            padding-top: 1rem;
            border-top: 1px solid #ddd;
            font-size: 0.85rem;
            color: #666;
        }

        .system-instruction summary {
            cursor: pointer;
            font-weight: 600;
            margin-bottom: 0.5rem;
            color: #333;
        }

        .system-instruction summary:hover {
            color: #0066cc;
        }

        .system-instruction pre {
            white-space: pre-wrap;
            word-wrap: break-word;
            background: var(--chat-container-bg);
            border: 1px solid #ddd;
            padding: 0.75rem;
            border-radius: 0.5rem;
            margin-top: 0.5rem;
            max-height: 200px;
            overflow-y: auto;
            line-height: 1.4;
            color: #333;
            font-size: 0.75rem;
        }
    </style>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <script src="https://unpkg.com/vue@3/dist/vue.global.prod.js"></script>
    <script type="module" src="./auth-reload.js"></script>
</head>
<body class="status-page">
    <div class="status-header">
        <h1>PuzzBot - Hunt Assistant</h1>
    </div>

    <?= render_navbar('puzzbot') ?>

    <div id="vue-app">
        <div class="info-box">
            <div class="info-box-header" @click="showAbout = !showAbout">
                <span class="collapse-icon" :class="{ collapsed: !showAbout }">▼</span>
                <h3>About PuzzBot</h3>
            </div>
            <div class="info-box-content" v-show="showAbout">
                <p>I'm an AI assistant that can answer questions about the hunt in natural language.</p>

                <h4>📊 Data I Can Access</h4>
                <ul>
                    <li>All puzzles, rounds, and their statuses</li>
                    <li>Team wiki (puzzle-solving techniques, resources, policies)</li>
                    <li>Puzzle details: answers, tags, sheet counts, comments, locations</li>
                    <li>Solver information: current assignments and puzzle history</li>
                    <li>Hunt statistics: open/solved counts, progress by round</li>
                </ul>

                <h4>⚙️ Model</h4>
                <p><span class="model-badge"><?php echo htmlentities($gemini_model); ?></span></p>

                <div class="system-instruction">
                    <details>
                        <summary>📜 System Instruction (click to expand)</summary>
                        <pre><?php echo htmlentities($gemini_instruction); ?></pre>
                    </details>
                </div>
            </div>
        </div>

        <div class="info-box">
            <div class="info-box-header" @click="showExamples = !showExamples">
                <span class="collapse-icon" :class="{ collapsed: !showExamples }">▼</span>
                <h3>Example Queries</h3>
            </div>
            <div class="info-box-content" v-show="showExamples">
                <div class="example-chips">
                    <span class="example-chip" onclick="askExample(this)">What's the hunt status?</span>
                    <span class="example-chip" onclick="askExample(this)">What puzzle should I work on?</span>
                    <span class="example-chip" onclick="askExample(this)">What puzzles have I worked on?</span>
                    <span class="example-chip" onclick="askExample(this)">Which round has the most open puzzles?</span>
                    <span class="example-chip" onclick="askExample(this)">What puzzles are critical?</span>
                    <span class="example-chip" onclick="askExample(this)">How do I solve a cryptic crossword?</span>
                </div>
            </div>
        </div>
    </div>

    <div class="info-box" id="chat-box">
        <div class="info-box-header" onclick="toggleChat()">
            <span class="collapse-icon" id="chat-collapse-icon">▼</span>
            <h3>Bot Chat</h3>
        </div>
        <div class="info-box-content" id="chat-content">
            <div class="chat-container" id="chat-container">
            </div>

            <div class="input-area">
                <div class="input-wrapper">
                    <input type="text" id="query-input" placeholder="Ask about puzzles, rounds, solvers..." autocomplete="off">
                    <button id="send-btn" onclick="sendQuery()">Send</button>
                </div>
            </div>

            <div class="disclaimers">
                <ul>
                    <li>Warning: this feature is very experimental. It is not guaranteed to be correct, even when constrained to its own limited data sets.</li>
                    <li>This query interface is not a conversation. Puzzbot does not remember context or any past queries or answers.</li>
                </ul>
            </div>
        </div>
    </div>

    <script>
        const username = <?php echo json_encode($username); ?>;
        const chatContainer = document.getElementById('chat-container');
        const queryInput = document.getElementById('query-input');
        const sendBtn = document.getElementById('send-btn');

        queryInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !sendBtn.disabled) {
                sendQuery();
            }
        });

        function askExample(el) {
            queryInput.value = el.textContent;
            sendQuery();
        }

        function addMessage(text, type) {
            // Show chat container when first message is added
            if (!chatContainer.classList.contains('has-messages')) {
                chatContainer.classList.add('has-messages');
            }

            const msg = document.createElement('div');
            msg.className = 'message ' + type;

            // Format bot messages with markdown, plain text for user messages
            if (type === 'bot') {
                msg.innerHTML = marked.parse(text);
            } else {
                msg.textContent = text;
            }

            chatContainer.appendChild(msg);
            chatContainer.scrollTop = chatContainer.scrollHeight;
            return msg;
        }
        
        async function sendQuery() {
            const query = queryInput.value.trim();
            if (!query) return;
            
            // Add user message
            addMessage(query, 'user');
            queryInput.value = '';
            
            // Add loading message
            const loadingMsg = addMessage('Thinking', 'loading');
            sendBtn.disabled = true;
            
            try {
                const response = await fetch('apicall.php?apicall=query', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        user_id: username,
                        text: query
                    })
                });
                
                const data = await response.json();
                
                // Remove loading message
                loadingMsg.remove();
                
                if (data.status === 'ok' && data.response) {
                    window.onFetchSuccess?.();
                    addMessage(data.response, 'bot');
                } else {
                    addMessage('Error: ' + (data.error || 'Unknown error'), 'error');
                }
            } catch (err) {
                loadingMsg.remove();
                if (window.onFetchFailure?.()) return;
                addMessage('Error: ' + err.message, 'error');
            }
            
            sendBtn.disabled = false;
            queryInput.focus();
        }

        // Initialize Vue for collapsible info boxes
        const { createApp } = Vue;
        createApp({
            data() {
                return {
                    showAbout: true,
                    showExamples: true
                }
            }
        }).mount('#vue-app');

        // Toggle chat box collapse (vanilla JavaScript)
        function toggleChat() {
            const content = document.getElementById('chat-content');
            const icon = document.getElementById('chat-collapse-icon');
            if (content.style.display === 'none') {
                content.style.display = 'block';
                icon.classList.remove('collapsed');
            } else {
                content.style.display = 'none';
                icon.classList.add('collapsed');
            }
        }
    </script>
</body>
</html>

