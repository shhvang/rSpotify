# Development Agent Rules & Guidelines

> **⚠️ PROPRIETARY PROJECT NOTICE:**  
> This is a **PRIVATE, PROPRIETARY** project. NOT open source. Do NOT reference GitHub, open source, forking, or contributions in ANY user-facing messages, documentation, or code comments.

---

## 0. MANDATORY PRE-WORK

### 0.1 Read This File First
**CRITICAL:** Read this ENTIRE file before starting any work. Acknowledge understanding.

### 0.2 Load Required Context
Before development, read:
- This `docs/rules.md` file
- All files in `docs/corrections/` (override PRD/Architecture)
- Relevant PRD and Architecture sections

### 0.3 Story Creation Requirements
Stories MUST include:
1. **"READ FIRST"** section listing required reading
2. Acknowledgment that corrections override base docs
3. References to correction documents in Dev Notes

### 0.4 Documentation Summaries
**DO NOT** create summaries unless explicitly requested by user.
- If requested: Place in `/summaries/` as `{number}-{DESCRIPTION}.md`
- Default: Complete work WITHOUT creating summaries

---

## 1. CORE PRINCIPLES

### 1.1 Quality Over Speed
**Take time. Be thorough. Don't rush.**
- Complete implementation
- Comprehensive error handling & testing
- Clear documentation
- Robust security & performance

### 1.2 Testing Requirements
- Unit tests for components
- Integration tests for services
- End-to-end tests for workflows
- Performance tests for critical paths

### 1.3 Security First
- Secure environment variables
- Input validation & sanitization
- No information leakage in errors
- Rate limiting & encryption

### 1.4 Code Quality
- Clear naming conventions
- Single-purpose functions
- Inline comments for complex logic
- Docstrings for all functions/classes

---

## 2. PROJECT-SPECIFIC RULES

### 2.1 Working Directory Structure
```
/rSpotify/rspotify-bot/  ← Main app is HERE
```
**ALWAYS** verify with `Get-Location` before running commands.

### 2.2 HTML Formatting for Telegram
ALL user-facing messages use HTML:
- `<b>bold</b>`, `<i>italic</i>`, `<code>code</code>`
- Set `parse_mode="HTML"` on all message functions
- Escape HTML special chars (&, <, >) in user data

### 2.3 Error Handling Pattern
- Add `return` statement after handling exceptions to prevent propagation to global error handler
- Prevents duplicate error messages to users
- Log errors properly before returning

```python
except Exception as e:
    logger.error(f"Error: {e}")
    await message.reply_html("Error message")
    return  # ← Prevent double error messages
```

---

## 3. CRITICAL TECHNICAL PATTERNS

### 3.1 Async MongoDB Operations
**ALWAYS** wrap pymongo calls with `asyncio.to_thread()`:
```python
# ✅ CORRECT
data = await asyncio.to_thread(collection.find_one, {"key": key})

# ❌ WRONG (blocks event loop)
data = collection.find_one({"key": key})
```

### 3.2 PyMongo Database Truthiness
**NEVER** use boolean checks on Database objects:
```python
# ✅ CORRECT
if db_service is None or db_service.database is None:

# ❌ WRONG (NotImplementedError)
if not db_service or not db_service.database:
```

### 3.3 httpx Response Methods
Response methods are **SYNCHRONOUS** - do NOT await:
```python
response = await client.post(url)  # ✅ Await request
data = response.json()              # ✅ NO await
text = response.text                # ✅ NO await
```

### 3.4 UTF-8 Encoding
- **ALL** source files: UTF-8 (with or without BOM)
- Always specify `encoding='utf-8'` in file operations
- Configure IDE default to UTF-8

### 3.5 Pillow Threading
- Pillow operations MUST run in thread pool
- Use `asyncio.get_event_loop().run_in_executor()`
- Never block async event loop with image processing

---

## 4. VERSION CONTROL WORKFLOW

### Feature Branch Process
```bash
# 1. Create feature branch
git checkout -b feature/story-X.X-description

# 2. Commit frequently with conventional commits
git commit -m "feat: add feature"

# 3. Push for review
git push origin feature/story-X.X-description

# 4. WAIT for owner approval before merging
```

**CRITICAL RULES:**
- ❌ **NEVER** commit directly to main
- ❌ **NEVER** merge without owner approval
- ✅ **ALWAYS** use feature branches
- ✅ **ALWAYS** wait for review

---

## 5. DEPLOYMENT & PROCESS MANAGEMENT

### 5.1 Supervisor-Only Deployment
**NEVER** manually start bot processes:
```bash
# ❌ WRONG
python rspotify.py

# ✅ CORRECT
sudo supervisorctl restart rspotify-bot
```

### 5.2 Deployment Checklist
1. SSH to VPS
2. Check for rogue processes: `ps aux | grep rspotify`
3. Kill non-supervisor processes if found
4. Pull latest code
5. Restart via supervisor
6. Verify only ONE instance running

### 5.3 Prevent Duplicate Processes
- Check `ps aux | grep rspotify` before/after deploy
- Only supervisor-managed processes should exist
- Multiple instances cause race conditions & API conflicts

---

## 6. TERMINAL COMMAND SAFETY

### Before Running ANY Command:
1. Verify correct working directory
2. Check command won't break codebase
3. Double-check file paths
4. Test in safe environment if uncertain

**Working Directory Check:**
```powershell
Get-Location  # Verify you're in /rspotify-bot/
```

---

## 7. LEARNING & ADAPTATION

### When Mistakes Occur:
1. Fix the issue
2. Add new rule to this file
3. Document the mistake & correct approach
4. Prevent recurrence

**This is a LIVING DOCUMENT.** Update as needed.

## Rule #13: Future-Proofing
Consider long-term maintainability:
- Modular design for easy extension
- Configuration-driven behavior
- Backwards compatibility when possible
- Clear upgrade/migration paths

## Rule #14: Async/Await with Synchronous Database Operations
**CRITICAL: Always wrap synchronous MongoDB operations in async functions**

### The Problem:
When using synchronous MongoDB operations (pymongo) inside async functions, they will block the event loop, causing the application to hang, crash, or return "Internal Server Error" messages.

### The Solution:
**ALWAYS** wrap synchronous MongoDB operations with `asyncio.to_thread()` when called from async functions.

### Example - WRONG (blocks event loop):
```python
async def get_data(key: str):
    # This BLOCKS the event loop!
    data = self._database.collection.find_one({"key": key})
    return data
```

### Example - CORRECT (non-blocking):
```python
async def get_data(key: str):
    # This properly runs in thread pool
    data = await asyncio.to_thread(
        self._database.collection.find_one, {"key": key}
    )
    return data
```

### Common Operations to Wrap:
- `find_one()` → `await asyncio.to_thread(collection.find_one, query)`
- `insert_one()` → `await asyncio.to_thread(collection.insert_one, doc)`
- `update_one()` → `await asyncio.to_thread(collection.update_one, query, update)`
- `delete_one()` → `await asyncio.to_thread(collection.delete_one, query)`
- `replace_one()` → `await asyncio.to_thread(collection.replace_one, query, doc, upsert=True)`

### Exception:
One-time initialization operations (like creating indexes) that run during startup MAY use synchronous calls, as they don't block critical request handling. However, document this clearly with a comment.

### Impact:
- **Web servers**: Blocking calls cause request timeouts and "Internal Server Error" responses
- **Bot handlers**: Blocking calls freeze the bot and prevent other users from getting responses
- **Testing**: Tests may pass locally but fail in production under load

### Detection:
Look for these patterns in async functions:
- Direct calls to `database.collection.operation()` without `await asyncio.to_thread()`
- Any pymongo operation that doesn't use motor (async MongoDB driver)
- Operations in middleware, handlers, or services that process user requests

## Rule #16: httpx AsyncClient Response Methods - CRITICAL
**httpx.AsyncClient response.json() is SYNCHRONOUS - DO NOT await it**

### The Problem:
httpx.AsyncClient makes async HTTP requests, but response methods like `.json()` and `.text` are **synchronous** methods that return data directly.

**Common mistakes:**
- ❌ `data = await response.json()`  # TypeError: object dict can't be used in 'await' expression
- ❌ `text = await response.text`    # TypeError: object str can't be used in 'await' expression

### The Solution:
```python
async with httpx.AsyncClient() as client:
    response = await client.post(url, data=data)  # ✅ Await the HTTP request
    data = response.json()  # ✅ NO await for response methods
    text = response.text    # ✅ NO await for response properties
```

### Pattern to Remember:
1. **Await the request**: `response = await client.get/post/put/delete()`
2. **Don't await the response**: `data = response.json()`, `text = response.text`

### Impact:
- Causes `TypeError: object dict/str can't be used in 'await' expression`
- Breaks OAuth token exchange flow
- Prevents user authentication
- Can cause cascading failures in API integrations

### Detection:
- Search for `await response.json()` or `await response.text` patterns
- Run integration tests with actual HTTP requests
- Monitor production logs for TypeError with httpx in stack trace

## Rule #17: Process Management & Deployment - CRITICAL
**ALWAYS use supervisor to manage bot processes - NEVER start bots manually**

### The Problem:
Multiple bot instances running simultaneously causes:
- Race conditions (one bot gets updates before the other)
- Telegram API conflicts ("terminated by other getUpdates request")
- Old code running alongside new code
- Unpredictable behavior and difficult debugging

### Root Cause Found:
1. Old bot process started manually on Sep 30 (PID 67737)
2. New bot started via supervisor on Oct 4 (PID 161042)
3. Both competing for Telegram updates
4. Old process using outdated code with bugs

### The Solution:

**Deployment Process:**
```bash
# 1. SSH to VPS
ssh root@178.128.48.130

# 2. Check for manual/rogue processes
ps aux | grep -E 'rspotify|python.*bot' | grep -v grep

# 3. Kill any non-supervisor processes
# Find PIDs not managed by supervisor and kill them
kill -9 <PID>

# 4. Navigate to repo and pull latest code
cd /opt/rspotify-bot/repo
git pull origin main

# 5. Restart via supervisor (proper way)
supervisorctl restart rspotify-bot
supervisorctl restart rspotify-oauth

# 6. Verify only ONE instance per service
supervisorctl status
ps aux | grep rspotify

# 7. Monitor logs for successful startup
tail -f /opt/rspotify-bot/logs/bot_error.log
```

### Prevention Rules:
1. **NEVER** run `python rspotify.py` manually on VPS
2. **ALWAYS** use `supervisorctl restart rspotify-bot`
3. **CHECK** for duplicate processes before and after deployment
4. **VERIFY** supervisor manages all services

### Supervisor Configuration:
Location: `/etc/supervisor/conf.d/rspotify-bot.conf`

Key settings:
- `autostart=true` - Starts on boot
- `autorestart=true` - Restarts on crash
- `user=rspotify` - Runs as non-root user
- Logs to `/opt/rspotify-bot/logs/`

### Detection of Issues:
1. **Multiple processes**: `ps aux | grep rspotify | wc -l` should match number of services
2. **Telegram conflicts**: Logs show "terminated by other getUpdates request"
3. **Old code running**: Check process start time with `ps -fp <PID>`
4. **Version mismatch**: Compare process start time with last git pull

### Impact:
- Causes intermittent behavior (works then stops)
- Makes debugging impossible
- Wastes time on "fixed" bugs that reappear
- Can cause data corruption or inconsistent state

## Rule #18: UTF-8 Encoding Standard - MANDATORY
**ALL source files MUST be encoded in UTF-8 with BOM or UTF-8 without BOM**

### The Problem:
Mixed file encodings cause:
- Character encoding errors in strings
- Import failures with non-ASCII characters
- Inconsistent behavior across different environments
- Issues with special characters in comments or docstrings
- Python runtime errors when reading/writing files

### The Solution:
**File Encoding Requirements:**
1. **All Python files (.py)**: UTF-8 encoding (with or without BOM)
2. **All text files (.md, .txt, .json, .yaml)**: UTF-8 encoding
3. **All configuration files**: UTF-8 encoding
4. **Source control**: Configure git to handle UTF-8 properly

**How to Verify Encoding:**
```bash
# PowerShell: Check file encoding
Get-Content -Path "file.py" -Encoding UTF8

# VS Code: Check encoding in status bar (bottom-right)
# Click to change if needed
```

**How to Fix Non-UTF-8 Files:**
1. Open file in VS Code
2. Click encoding indicator in status bar (bottom-right)
3. Select "Save with Encoding"
4. Choose "UTF-8" or "UTF-8 with BOM"

### Python Code Requirements:
```python
# Always specify UTF-8 when reading/writing files
with open('file.txt', 'r', encoding='utf-8') as f:
    content = f.read()

with open('file.txt', 'w', encoding='utf-8') as f:
    f.write(content)
```

### Prevention Rules:
1. **NEVER** commit files with non-UTF-8 encoding
2. **ALWAYS** specify `encoding='utf-8'` in file operations
3. **CHECK** file encoding before committing
4. **CONFIGURE** IDE/editor to default to UTF-8
5. **TEST** on Windows (PowerShell) to catch encoding issues early

### VS Code Configuration:
Add to `.vscode/settings.json`:
```json
{
  "files.encoding": "utf8",
  "files.autoGuessEncoding": false
}
```

### Impact:
- Prevents runtime encoding errors
- Ensures cross-platform compatibility
- Makes code review easier
- Avoids git diff issues with encoding mismatches

## Rule #15: PyMongo Database Truthiness - CRITICAL
**NEVER use boolean checks on pymongo Database objects**

### The Problem:
PyMongo's Database class does NOT implement __bool__(), which means you cannot use it in truthiness checks.
? if not database:
? if not db_service or not db_service.database:

This raises: NotImplementedError: Database objects do not implement truth value testing

### The Solution:
ALWAYS use explicit 'is None' or 'is not None' comparisons:
? if database is None:
? if db_service is None or db_service.database is None:


## Rule #15: PyMongo Database Truthiness - CRITICAL
**NEVER use boolean checks on pymongo Database objects**

### The Problem:
PyMongo's Database class does NOT implement __bool__(), which means you cannot use it in truthiness checks.
? if not database:
? if not db_service or not db_service.database:

This raises: NotImplementedError: Database objects do not implement truth value testing

### The Solution:
ALWAYS use explicit 'is None' or 'is not None' comparisons:
? if database is None:
? if db_service is None or db_service.database is None:


## Rule #16: httpx AsyncClient Response Methods - CRITICAL
**httpx.AsyncClient response.json() is SYNCHRONOUS - DO NOT await it**

### The Problem:
httpx.AsyncClient makes async HTTP requests, but response methods like .json(), .text are SYNCHRONOUS.
 data = await response.json()  # WRONG - TypeError!
 text = await response.text    # WRONG - TypeError!

### The Solution:
 data = response.json()  # Correct - no await
 text = response.text    # Correct - no await

### Pattern:
- await client.post()  # Await the HTTP request
- response.json()      # NO await for response methods

### Impact:
- Causes 'TypeError: object dict/str can't be used in await expression'
- Breaks OAuth token exchange
- Prevents user authentication


## Rule #16: httpx AsyncClient Response Methods - CRITICAL
**httpx.AsyncClient response.json() is SYNCHRONOUS - DO NOT await it**

### The Problem:
httpx.AsyncClient makes async HTTP requests, but response methods like .json(), .text are SYNCHRONOUS.
? data = await response.json()  # WRONG - TypeError!
? text = await response.text    # WRONG - TypeError!

### The Solution:
? data = response.json()  # Correct - no await
? text = response.text    # Correct - no await

### Pattern:
- await client.post()  # Await the HTTP request
- response.json()      # NO await for response methods

### Impact:
- Causes 'TypeError: object dict/str can't be used in await expression'
- Breaks OAuth token exchange
- Prevents user authentication

