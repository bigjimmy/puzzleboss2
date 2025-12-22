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
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PuzzBot - Hunt Assistant</title>
    <style>
        :root {
            --bg-dark: #1a1a2e;
            --bg-card: #16213e;
            --accent: #e94560;
            --accent-hover: #ff6b6b;
            --text: #eee;
            --text-muted: #888;
            --bot-bg: #0f3460;
            --user-bg: #533483;
        }
        
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        
        body {
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: var(--bg-dark);
            color: var(--text);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }
        
        header {
            background: var(--bg-card);
            padding: 1rem 2rem;
            border-bottom: 2px solid var(--accent);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        header h1 {
            font-size: 1.5rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        header h1::before {
            content: '🤖';
        }
        
        .user-info {
            color: var(--text-muted);
            font-size: 0.9rem;
        }
        
        .chat-container {
            flex: 1;
            max-width: 900px;
            width: 100%;
            margin: 0 auto;
            padding: 1rem;
            display: flex;
            flex-direction: column;
            gap: 1rem;
            overflow-y: auto;
        }
        
        .message {
            padding: 1rem 1.25rem;
            border-radius: 1rem;
            max-width: 85%;
            line-height: 1.5;
            animation: fadeIn 0.3s ease;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .message.bot {
            background: var(--bot-bg);
            align-self: flex-start;
            border-bottom-left-radius: 0.25rem;
        }
        
        .message.user {
            background: var(--user-bg);
            align-self: flex-end;
            border-bottom-right-radius: 0.25rem;
        }
        
        .message.error {
            background: #8b0000;
            align-self: flex-start;
        }
        
        .message.loading {
            background: var(--bot-bg);
            align-self: flex-start;
            color: var(--text-muted);
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
        
        .input-area {
            background: var(--bg-card);
            padding: 1rem 2rem;
            border-top: 1px solid #333;
        }
        
        .input-wrapper {
            max-width: 900px;
            margin: 0 auto;
            display: flex;
            gap: 0.75rem;
        }
        
        #query-input {
            flex: 1;
            padding: 0.875rem 1.25rem;
            border: 2px solid #333;
            border-radius: 2rem;
            background: var(--bg-dark);
            color: var(--text);
            font-size: 1rem;
            outline: none;
            transition: border-color 0.2s;
        }
        
        #query-input:focus {
            border-color: var(--accent);
        }
        
        #query-input::placeholder {
            color: var(--text-muted);
        }
        
        #send-btn {
            padding: 0.875rem 1.75rem;
            background: var(--accent);
            color: white;
            border: none;
            border-radius: 2rem;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s, transform 0.1s;
        }
        
        #send-btn:hover {
            background: var(--accent-hover);
        }
        
        #send-btn:active {
            transform: scale(0.98);
        }
        
        #send-btn:disabled {
            background: #555;
            cursor: not-allowed;
        }
        
        .examples {
            text-align: center;
            padding: 2rem;
            color: var(--text-muted);
        }
        
        .examples h3 {
            margin-bottom: 1rem;
            font-weight: normal;
        }
        
        .example-chips {
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 0.5rem;
        }
        
        .example-chip {
            background: var(--bg-card);
            border: 1px solid #444;
            padding: 0.5rem 1rem;
            border-radius: 1rem;
            cursor: pointer;
            transition: border-color 0.2s, background 0.2s;
        }
        
        .example-chip:hover {
            border-color: var(--accent);
            background: var(--bot-bg);
        }
        
        .bot-info {
            background: var(--bg-card);
            border: 1px solid #333;
            border-radius: 1rem;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            text-align: left;
            max-width: 600px;
        }
        
        .bot-info h3 {
            color: var(--accent);
            margin-bottom: 0.75rem;
            font-size: 1.1rem;
        }
        
        .bot-info p {
            color: var(--text-muted);
            margin-bottom: 0.75rem;
            line-height: 1.5;
        }
        
        .bot-info ul {
            color: var(--text-muted);
            margin-left: 1.25rem;
            margin-bottom: 0.75rem;
        }
        
        .bot-info li {
            margin-bottom: 0.25rem;
        }
        
        .bot-info .model-badge {
            display: inline-block;
            background: var(--bot-bg);
            padding: 0.25rem 0.75rem;
            border-radius: 1rem;
            font-family: monospace;
            font-size: 0.85rem;
            color: var(--text);
        }
        
        .system-instruction {
            background: var(--bg-card);
            border-top: 1px solid #333;
            padding: 1rem 2rem;
            font-size: 0.75rem;
            color: var(--text-muted);
        }
        
        .system-instruction summary {
            cursor: pointer;
            font-weight: 600;
            margin-bottom: 0.5rem;
        }
        
        .system-instruction summary:hover {
            color: var(--text);
        }
        
        .system-instruction pre {
            white-space: pre-wrap;
            word-wrap: break-word;
            background: var(--bg-dark);
            padding: 0.75rem;
            border-radius: 0.5rem;
            margin-top: 0.5rem;
            max-height: 200px;
            overflow-y: auto;
            line-height: 1.4;
        }
    </style>
</head>
<body>
    <header>
        <h1>PuzzBot</h1>
        <span class="user-info">Logged in as: <?php echo htmlentities($username); ?></span>
    </header>
    
    <div class="chat-container" id="chat-container">
        <div class="examples" id="examples">
            <div class="bot-info">
                <h3>🤖 About PuzzBot</h3>
                <p>I'm an AI assistant that can answer questions about the hunt in natural language.</p>
                
                <h3>📊 Data I Can Access</h3>
                <ul>
                    <li>All puzzles, rounds, and their statuses</li>
                    <li>Puzzle details: answers, tags, sheet counts, comments, locations</li>
                    <li>Solver information: current assignments and puzzle history</li>
                    <li>Hunt statistics: open/solved counts, progress by round</li>
                </ul>
                
                <h3>⚙️ Model</h3>
                <p><span class="model-badge"><?php echo htmlentities($gemini_model); ?></span></p>
            </div>
            
            <h3>Try asking me something!</h3>
            <div class="example-chips">
                <span class="example-chip" onclick="askExample(this)">What's the hunt status?</span>
                <span class="example-chip" onclick="askExample(this)">What puzzle should I work on?</span>
                <span class="example-chip" onclick="askExample(this)">What puzzles have I worked on?</span>
                <span class="example-chip" onclick="askExample(this)">Which round has the most open puzzles?</span>
                <span class="example-chip" onclick="askExample(this)">What puzzles are critical?</span>
            </div>
        </div>
    </div>
    
    <div class="input-area">
        <div class="input-wrapper">
            <input type="text" id="query-input" placeholder="Ask about puzzles, rounds, solvers..." autocomplete="off">
            <button id="send-btn" onclick="sendQuery()">Send</button>
        </div>
    </div>
    
    <div class="system-instruction">
        <details>
            <summary>📜 System Instruction (click to expand)</summary>
            <pre><?php echo htmlentities($gemini_instruction); ?></pre>
        </details>
    </div>
    
    <script>
        const username = <?php echo json_encode($username); ?>;
        const chatContainer = document.getElementById('chat-container');
        const queryInput = document.getElementById('query-input');
        const sendBtn = document.getElementById('send-btn');
        const examples = document.getElementById('examples');
        
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
            // Hide examples on first message
            if (examples) {
                examples.style.display = 'none';
            }
            
            const msg = document.createElement('div');
            msg.className = 'message ' + type;
            msg.textContent = text;
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
                    addMessage(data.response, 'bot');
                } else {
                    addMessage('Error: ' + (data.error || 'Unknown error'), 'error');
                }
            } catch (err) {
                loadingMsg.remove();
                addMessage('Error: ' + err.message, 'error');
            }
            
            sendBtn.disabled = false;
            queryInput.focus();
        }
    </script>
</body>
</html>

