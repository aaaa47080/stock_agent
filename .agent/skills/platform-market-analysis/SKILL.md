---
name: Platform Market Analysis System
description: Market analysis system using AI agents, streaming chat interface, and real-time data integration.
---

# Platform Market Analysis Skill

## Overview

The Market Analysis System is an AI-powered chat interface that allows users to ask questions about crypto markets, trends, and technical indicators. It uses a "ReAct" style agent approach to reason, fetch data, and formulate answers.

**Key Features:**
- **Natural Language Parsing**: Understands "Analyze BTC" or "Is ETH bullish?".
- **Real-time Data**: Fetches live prices, technical indicators (RSI, MAX), and news.
- **Streaming Response**: Shows the "thought process" (steps) in real-time before the final answer.
- **Session Management**: Multi-session chat history with pinning and persistence.

**Key Files:**
- **Frontend**: `web/js/chat.js` (Chat UI & Stream Handler), `web/js/market.js` (Data Visualization)
- **Backend API**: `api/routers/analysis.py` (Endpoints)
- **Core Logic**: `interfaces/chat_interface.py` (Bot & Parser), `core/agents.py` (Agent Logic)

---

## Architecture

### Data Flow
1. **User Input**: Typed in `web/js/chat.js`.
2. **API Request**: `POST /api/analyze` (Stream).
3. **Query Parsing**: `CryptoQueryParser` calls LLM to extract intent (Symbol: BTC, Action: Analyze).
4. **Execution**: `CryptoAnalysisBot` decides which tools to run (Price, News, Indicators).
5. **Streaming**: 
   - Backend yields "Process Steps" (`[PROCESS] Fetching data...`)
   - Backend yields "Final Answer" (`[RESULT] Bitcoin is currently...`)
6. **Rendering**: Frontend parses the stream and updates the UI incrementally.

### Components

#### 1. CryptoAnalysisBot (`interfaces/chat_interface.py`)
the main orchestrator. It:
- Maintains conversation history.
- Manages the `CryptoAgent` or executes the "Standard Analysis Mode" (legacy).
- Generates the streaming response generator.

#### 2. Streaming Protocol (`NDJSON` style)
The `/api/analyze` endpoint returns a stream of JSON objects or specially formatted text lines.
- `data: {"content": "[PROCESS] Checking limits..."}` -> Updates the "Thinking" UI.
- `data: {"content": "[RESULT] **Analysis**: ..."}` -> Renders the final markdown response.
- `data: {"done": true}` -> Closes the stream.

#### 3. Frontend Chat (`web/js/chat.js`)
- **Session Management**: Loads/Creates/Deletes sessions via `/api/chat/sessions`.
- **Stream Reader**: Uses `response.body.getReader()` to process chunks.
- **UI Rendering**: 
  - `renderStoredBotMessage()` parses the special tags (`[PROCESS_START]`, `[RESULT]`) to create the collapsible "Process" section and the Markdown result.

---

## API Endpoints

### Analysis

#### POST /api/analyze
Streamed analysis response.
**Payload:**
```json
{
  "message": "Analyze BTC",
  "manual_selection": ["rsi", "macd"],
  "market_type": "spot",
  "session_id": "uuid..."
}
```

#### POST /api/analysis/backtest
Runs a quick backtest for a strategy.

### Session Management

#### GET /api/chat/sessions
List user's chat sessions.

#### POST /api/chat/sessions
Create a new session.

#### GET /api/chat/history?session_id=...
Get message history for a session.

---

## Frontend Integration (`chat.js`)

**Key Function**: `sendMessage()`
1. Checks for API Key.
2. Creates/Selects a session.
3. Sends `POST /api/analyze`.
4. Reads stream loop:
   ```javascript
   while (true) {
       const { value, done } = await reader.read();
       // Decode and update UI
       botMsgDiv.innerHTML = renderStoredBotMessage(fullContent, true);
   }
   ```

**UI States**:
- **Thinking**: Shows a spinner and elapsed time.
- **Process**: Collapsible details tag showing step-by-step actions.
- **Result**: Final markdown content.

---

## Modification Guidelines

### ✅ Safe Modifications
1. **Adding New Tools**: 
   - Add tool function in `core/tools.py`.
   - Register tool in `core/agents.py`.
   - The Bot will automatically have access to it (if using Agent mode).

2. **Customizing UI**:
   - `web/js/chat.js`: `renderStoredBotMessage` controls how the message looks. You can change styling here.

### ⚠️ Risks
1. **LLM Context Window**: 
   - Passing too much history or too large data (news articles) can hit token limits.
   - **Fix**: Use `trim_history` or summarization techniques in `CryptoAnalysisBot`.

2. **Timeout**:
   - Complex analysis takes time (>30s).
   - **Fix**: Ensure Nginx/frontend timeout settings allow for long-lived streams.

---

## Related Skills
- **platform-db-pattern**: For session storage logic.
- **pi-auth**: For user identification in sessions.
