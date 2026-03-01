# Sona ChatBot - FastAPI + CrewAI Chatbot UI

This project adds a reusable chatbot UI to your existing CrewAI-based Sona College Assistant. The chatbot appears in the bottom-right corner of your application and connects to a FastAPI backend.

## 📁 Project Structure

```
sonachatbot/
├── src/sonachatbot/
│   ├── api.py              # FastAPI backend (NEW)
│   ├── main.py             # Original CLI chatbot
│   └── crews/
│       └── poem_crew/
│           └──
├── frontend/
 poem_crew.py│   ├── chat-widget.html   # Demo page with widget
│   ├── chat-widget.css    # Chat widget styles
│   └── chat-widget.js     # Chat widget functionality
├── pyproject.toml         # Updated with FastAPI deps
└── README_CHATBOT.md      # This file
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Install the project with new dependencies
pip install -e .

# Or install FastAPI directly
pip install fastapi uvicorn python-multipart
```

### 2. Start the FastAPI Server

```
bash
# Using uvicorn directly
uvicorn sonachatbot.api:app --reload --port 8000

# Or using Python
python -m sonachatbot.api

# Or using the built-in run function
python -c "from sonachatbot.api import run_server; run_server()"
```

### 3. Open the Chat Widget

Open `frontend/chat-widget.html` in your browser, or serve it:

```
bash
# Using Python's built-in server
cd frontend
python -m http.server 8080
```

Then visit `http://localhost:8080/chat-widget.html`

## 🔧 Configuration

### FastAPI Server Options

You can customize the server in `src/sonachatbot/api.py`:

```
python
# Change port
uvicorn sonachatbot.api:app --port 9000

# Enable debug mode
uvicorn sonachatbot.api:app --reload --debug
```

### Chat Widget Options

When initializing the widget:

```
javascript
SonaChatWidget.init({
    apiUrl: 'http://localhost:8000/api/chat',  // Required
    position: 'bottom-right',    // or 'bottom-left'
    primaryColor: '#4a90e2',    // Your brand color
    title: 'Sona Assistant',    // Chat title
    subtitle: 'Online',         // Status text
    welcomeMessage: 'Hi!',      // Welcome message
    placeholder: 'Type here...' // Input placeholder
});
```

## 🔌 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API info |
| `/health` | GET | Health check |
| `/api/chat` | POST | Send a chat message |

### Chat Endpoint

**Request:**
```
json
POST /api/chat
{
    "message": "What are the cutoff ranks for CS engineering?"
}
```

**Response:**
```json
{
    "response": "The cutoff rank for CS engineering is...",
    "status": "success"
}
```

## 🎨 Embedding in Your Application

### Option 1: Standalone HTML Page

```
html
<!DOCTYPE html>
<html>
<head>
    <link rel="stylesheet" href="path/to/chat-widget.css">
</head>
<body>
    <!-- Your app content -->
    
    <script src="path/to/chat-widget.js"></script>
    <script>
        SonaChatWidget.init({
            apiUrl: 'http://your-api-server.com/api/chat'
        });
    </script>
</body>
</html>
```

### Option 2: In an Existing Website

1. Copy `chat-widget.css` and `chat-widget.js` to your project
2. Add the CSS in your `<head>`:
   
```
html
   <link rel="stylesheet" href="/path/to/chat-widget.css">
   
```
3. Add the JS before `</body>`:
   
```
html
   <script src="/path/to/chat-widget.js"></script>
   <script>
       SonaChatWidget.init({
           apiUrl: 'http://localhost:8000/api/chat',
           title: 'Your App Assistant'
       });
   </script>
   
```

### Option 3: In a React/Vue/Angular App

```
jsx
// In your main App component
import { useEffect } from 'react';

function App() {
    useEffect(() => {
        // Load the script dynamically
        const script = document.createElement('script');
        script.src = '/path/to/chat-widget.js';
        script.onload = () => {
            window.SonaChatWidget.init({
                apiUrl: 'http://localhost:8000/api/chat'
            });
        };
        document.body.appendChild(script);
        
        // Load CSS
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = '/path/to/chat-widget.css';
        document.head.appendChild(link);
    }, []);
    
    return <div>Your app content</div>;
}
```

## 🔧 Troubleshooting

### CORS Issues

If you're embedding the widget on a different domain, add CORS support:

```
python
# In api.py, add this import
from fastapi.middleware.cors import CORSMiddleware

# Add this after app creation
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or your specific domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Connection Refused Error

Make sure the FastAPI server is running:
```
bash
uvicorn sonachatbot.api:app --reload
```

### Rate Limiting

The CrewAI backend has rate limits. If you get 429 errors, the API will automatically retry with a backoff. Check the console for messages.

## 📝 Customization

### Change Colors

```
javascript
SonaChatWidget.init({
    primaryColor: '#your-brand-color'
});
```

The widget uses CSS variables, so you can also override:

```
css
:root {
    --chat-primary-color: #your-color;
    --chat-primary-hover: #your-hover-color;
    --chat-user-msg-bg: #your-color;
}
```

### Change Position

```
javascript
SonaChatWidget.init({
    position: 'bottom-left'  // or 'bottom-right'
});
```

## 📄 License

Same as the main project.
