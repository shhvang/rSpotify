# Development Agent Rules & Guidelines

## MANDATORY PRE-WORK: Context Loading Requirements

### Rule #0.1: Read docs/rules.md FIRST (THIS FILE)
**CRITICAL: Always read this entire rules.md file before starting any work**
- This file contains all development standards, patterns, and critical lessons learned
- Reading this file prevents repeated mistakes and ensures consistency
- Explicitly acknowledge you have read and understood this file before proceeding

### Rule #0.2: Read docs/corrections/ Before Development
**CRITICAL: Always read all files in docs/corrections/ before developing or creating stories**
- The corrections folder contains critical architecture decisions and implementation details
- These documents override any conflicting information in PRD or Architecture files
- Stories must reference relevant correction documents explicitly
- Acknowledge corrections documents in your planning before starting development

### Rule #0.3: Story Creation Requirements
**All new stories MUST include these mandatory sections:**
1. **"Read First" section at the top** listing:
   - `docs/rules.md` (this file)
   - All relevant `docs/corrections/*.md` files
   - Related architecture and PRD sections
2. **Explicit acknowledgment** that correction documents override base architecture
3. **Reference to correction documents** in Dev Notes section

**Example Story Header:**
```markdown
# Story X.X: Feature Name

## READ FIRST (Mandatory Context)
Before starting this story, you MUST read:
- ✅ `docs/rules.md` - Development standards and patterns
- ✅ `docs/corrections/oauth-implementation.md` - OAuth architecture v2.0 (aiohttp+certbot)
- ✅ PRD Section 6.X - Story requirements
- ✅ Architecture Section X - Technical context

> **⚠️ CRITICAL:** Correction documents in `docs/corrections/` contain the ACTUAL implementation
> and override any conflicting information in PRD or Architecture base files.

## Status
Draft
...
```

### Rule #0.4: Documentation Summary Policy
**DO NOT create documentation summaries unless explicitly requested by the user**
- Agents should not autonomously create summary documents after completing work
- If explicitly requested, summaries must be placed in `/summaries/` directory (root repository)
- Summary files must follow naming convention: `{number}-{DESCRIPTION}.md`
  - Example: `1-COURSE_CORRECTION.md`, `2-EPIC_1_COMPLETION.md`, `3-OAUTH_MIGRATION.md`
- Number increments sequentially (1, 2, 3, etc.)
- Only create summaries when user explicitly asks: "create a summary" or "document this work"
- Default behavior: Complete work without creating summary documentation

## Rule #1: Quality Over Speed
**Do not rush, take your time and complete the tasks with utmost detailing and precision. Do not worry about time consumption.**

The quality of implementation, thoroughness of testing, and attention to detail are paramount. It is better to take additional time to ensure:
- Complete and correct implementation
- Comprehensive error handling
- Proper testing coverage
- Clear documentation
- Robust security practices
- Performance optimization

Speed should never come at the expense of quality, reliability, or maintainability.

## Rule #2: Comprehensive Testing
All code must include appropriate tests:
- Unit tests for individual components
- Integration tests for service interactions
- End-to-end tests for complete workflows
- Performance tests for critical paths

## Rule #3: Security First
Always implement security best practices:
- Secure environment variable handling
- Input validation and sanitization
- Proper error handling without information leakage
- Rate limiting and abuse prevention
- Encryption for sensitive data

## Rule #4: Documentation Standards
Maintain clear and comprehensive documentation:
- Inline code comments for complex logic
- Docstrings for all functions and classes
- README updates for new features
- Architecture documentation for design decisions

## Rule #5: Error Handling Excellence
Implement robust error handling:
- Graceful degradation when services are unavailable
- Meaningful error messages for users
- Proper logging for debugging
- Recovery mechanisms where possible

## Rule #6: Performance Considerations
Always consider performance implications:
- Efficient database queries
- Proper caching strategies
- Async/await patterns for I/O operations
- Resource cleanup and memory management

## Rule #7: HTML Formatting for User Messages
Use HTML formatting globally for all user-facing messages in Telegram:
- Use `<b>` for bold text
- Use `<i>` for italic text
- Use `<code>` for inline code
- Use `<pre>` for code blocks
- Use `<a href="url">text</a>` for links
- Set `parse_mode="HTML"` in all message sending functions
- Escape HTML special characters (&, <, >) when displaying user data

## Rule #7: Code Review Mindset
Write code as if it will be reviewed by senior engineers:
- Follow established coding standards
- Use meaningful variable and function names
- Keep functions focused and single-purpose
- Maintain consistent code style

## Rule #8: Terminal Command Safety
**CRITICAL: Always verify terminal commands before execution**
- Always check you are trying to run valid, harmless code in the terminal
- Verify commands will not break or corrupt the codebase
- Double-check file paths and working directories before running commands
- Test commands in safe environments when uncertain

## Rule #9: Working Directory Awareness
**CRITICAL: Always verify correct working directory**
- The project structure has a nested directory: `/rSpotify/rspotify-bot/`
- Main application files are in `/rspotify-bot/` subdirectory, NOT in `/rSpotify/`
- Always check current working directory with `pwd` or `Get-Location` before running commands
- Navigate to correct directory before executing Python scripts or package management commands
- Example: To run the bot, navigate to `/rspotify-bot/` directory first, then run `python rspotify.py`

## Rule #10: Mistake Documentation & Learning
**Append new rules when mistakes are discovered**
- When you make a mistake and fix it, immediately add a new rule to this file
- Document the specific mistake, the correct approach, and prevention methods
- Update this file as a living document to prevent recurring issues
- Each new rule should include the context of what went wrong and how to avoid it

## Rule #11: Version Control System (VCS) Workflow - MANDATORY
**CRITICAL: Always use feature branches for development - NEVER commit directly to main**

### Feature Branch Workflow:
1. **Before Starting Any Story**: Create a new feature branch
   - Branch naming: `feature/story-{epic}.{story}-{short-description}`
   - Example: `git checkout -b feature/story-1.3-secure-user-data-storage`
   
2. **During Development**: 
   - Make all commits to the feature branch
   - Commit frequently with descriptive messages
   - Follow conventional commit format: `feat:`, `fix:`, `test:`, `docs:`, etc.
   
3. **After Story Completion**:
   - Push feature branch to remote: `git push origin feature/story-x.x-description`
   - Create Pull Request (PR) for review
   - **WAIT for owner confirmation before merging**
   - Do NOT merge to main without explicit owner approval
   
4. **After Owner Approval**:
   - Owner will merge PR to main branch
   - Delete feature branch after successful merge
   - Pull latest main before starting next story

### Critical VCS Rules:
- **NEVER** work directly on main branch
- **NEVER** commit directly to main branch
- **ALWAYS** create feature branch for each story
- **ALWAYS** wait for owner approval before merging
- If you accidentally commit to main, immediately stop and notify owner

## Rule #12: Pillow (PIL) Library Installation
**Handle Pillow installation issues on Windows systems**

### Known Issue:
Pillow library may have installation issues on Windows systems, particularly with wheel building.

### Solution Approach:
1. **Try standard installation first**: `pip install Pillow==10.1.0`
2. **If installation fails**, try these alternatives in order:
   - Update pip first: `python -m pip install --upgrade pip`
   - Install with no-cache: `pip install --no-cache-dir Pillow==10.1.0`
   - Try latest stable version: `pip install Pillow` (without version pin)
   - Use pre-built wheels from: `pip install --only-binary :all: Pillow`

3. **For Windows-specific issues**:
   - Ensure Microsoft Visual C++ Build Tools are installed
   - Consider using conda if available: `conda install pillow`
   - Document the working solution in installation docs

4. **Thread Safety Reminder**:
   - Pillow operations must run in separate thread (executor) to avoid blocking async event loop
   - Use `asyncio.get_event_loop().run_in_executor()` for image processing

### Documentation:
When Pillow installation is resolved, document the working method in README.md under "Installation" section.

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

