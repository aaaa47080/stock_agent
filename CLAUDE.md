# CLAUDE.md - CryptoMind Pi DApp

## Auto-Approve Rules

**For the following types of changes, I can proceed WITHOUT asking for approval:**
- Bug fixes that are clearly correct (syntax errors, obvious logic bugs)
- Error handling improvements (adding try-catch, null checks)
- API endpoint fixes that don't change behavior
- Frontend error message improvements
- Test mode / sandbox configuration fixes
- JavaScript syntax error fixes
- CSS/UI fixes that don't change functionality
- Adding missing import statements for ES modules
- Fixing broken subquery/correlate issues in SQLAlchemy

**For the following, I MUST ask first:**
- Changes to authentication/authorization logic
- Database schema changes
- Payment/money-related code
- User data handling changes
- Adding new dependencies
- Changes to Pi SDK integration
- Modifying the Pi payment flow

## Browser Testing Workflow

When asked to test in browser:

1. **Start server:** `python api_server.py` in `D:/okx/stock_agent`
2. **Use Playwright MCP tools** for browser automation
3. **Dev login:** `POST /api/user/dev-login` with `{"test_mode_confirmation":"I_UNDERSTAND_THE_RISKS"}`
4. **Test features:** Navigate to `#friends`, `#forum`, `#settings` tabs
5. **If fixes needed and under auto-approve rules:** Implement directly, commit with message
6. **If fixes need approval:** Explain what and why

## Key Commands

```bash
# Start server
cd D:/okx/stock_agent && python api_server.py

# Kill old process on port 8080
python -c "import os,signal; os.kill(PID, signal.SIGTERM)"

# Check JS syntax
node --check file.js

# Check if server is running
netstat -ano | grep 8080
```

## Important Paths

- Backend: `api_server.py`, `api/routers/`
- Frontend: `web/index.html`, `web/js/`
- ES Modules entry: `web/js/main.js`
- Premium module: `web/js/premium.js` (needs `loadPiPrices` from forum-config.js)
- Friends: `web/js/friends.js`
- Forum: `web/js/forum-app.js`
