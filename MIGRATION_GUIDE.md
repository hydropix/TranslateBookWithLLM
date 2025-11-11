# Migration Guide - Configuration System Update

## What Changed?

We've improved TBL's configuration system to make it more user-friendly, especially for fresh installations. The application now provides:

✅ **Clear warnings** when `.env` is missing
✅ **Helpful error messages** with step-by-step solutions
✅ **Interactive setup wizard** for easy configuration
✅ **Configuration validation** tool
✅ **Automatic fallback** to safe defaults

## Do I Need to Do Anything?

### If your installation already works:

**No action required!** Your existing `.env` file will continue to work perfectly.

### If you're setting up TBL on a new computer:

Follow one of these methods to configure TBL:

#### Option 1: Use start.bat (Windows - Easiest)

```bash
start.bat
```

The script will:
- Automatically create `.env` from template
- Open it in Notepad for editing
- Start the application

#### Option 2: Interactive Setup Wizard

```bash
python setup_config.py
```

Follow the on-screen prompts to configure your installation.

#### Option 3: Manual Copy

```bash
copy .env.example .env
notepad .env
```

Edit the values to match your setup.

## New Features

### 1. Missing .env Warning

When you start TBL without a `.env` file, you'll see:

```
⚠️  WARNING: .env configuration file not found
================================================================
The application will run with default settings, but you may need to
configure it for your specific setup.

📋 QUICK SETUP:
   1. Copy the template: copy .env.example .env
   2. Edit .env to match your configuration
   3. Restart the application

🔧 DEFAULT SETTINGS BEING USED:
   • API Endpoint: http://localhost:11434/api/generate
   • LLM Provider: ollama
   • Model: mistral-small:24b
   • Port: 5000

Press Ctrl+C to stop and configure, or wait 5 seconds to continue...
```

You have 5 seconds to press **Ctrl+C** to stop and configure.

### 2. Configuration Validation

Check if your configuration is correct:

```bash
python -m src.utils.env_helper validate
```

Output example:

```
🔍 CONFIGURATION VALIDATION
================================================================

📁 .env file exists: ✅ Yes

⚙️  Current Configuration:
   • LLM Provider: ollama
   • API Endpoint: http://ai_server.mds.com:11434/api/generate
   • Model: mistral-small:24b
   • Port: 5000

⚠️  WARNINGS:
   • Using remote Ollama server: http://ai_server.mds.com:11434/api/generate

✅ Configuration looks good!
```

### 3. Interactive Setup Wizard

```bash
python setup_config.py
```

Provides a user-friendly menu:

```
================================================================
  TranslateBookWithLLM - Configuration Setup
================================================================

What would you like to do?

  1. Quick setup (copy from .env.example)
  2. Interactive setup wizard (guided configuration)
  3. Validate current configuration
  4. Exit

Enter your choice (1-4):
```

### 4. Better Error Messages

Configuration errors now show:

```
❌ CONFIGURATION ERROR
================================================================
   • API_ENDPOINT must be configured
   • GEMINI_API_KEY required when using gemini provider

💡 SOLUTION:
   1. Create a .env file from .env.example
   2. Configure the required settings
   3. Restart the application

   Quick setup:
   python -m src.utils.env_helper setup
================================================================
```

## Common Migration Scenarios

### Scenario 1: Copying TBL to a New Computer

**Old way:**
- Clone project
- Application starts but uses wrong settings
- Confusion about why it's not connecting

**New way:**
- Clone project
- Run `python setup_config.py`
- Follow guided setup
- Application configured correctly

### Scenario 2: Using Remote Ollama Server

**Old way:**
- Manually create `.env` from scratch
- Trial and error with settings

**New way:**
- Run `python setup_config.py`
- Select option 2 (Interactive setup)
- Enter remote server address: `http://ai_server.mds.com:11434/api/generate`
- Configuration created automatically

### Scenario 3: Switching Between Providers

**Old way:**
- Edit `.env` manually, hope you got everything right

**New way:**
- Run `python -m src.utils.env_helper validate` to check current config
- Edit `.env` if needed
- Validate again to confirm

## Troubleshooting

### "My existing installation stopped working"

This update should not break existing installations. If you encounter issues:

1. Check your `.env` file exists:
   ```bash
   dir .env
   ```

2. Validate your configuration:
   ```bash
   python -m src.utils.env_helper validate
   ```

3. If issues persist, backup your current `.env` and recreate:
   ```bash
   copy .env .env.backup
   python setup_config.py
   ```

### "Fresh clone won't start"

If you clone TBL to a new location:

1. **Don't** just copy the `.env` from your old installation blindly
2. **Do** run the setup wizard:
   ```bash
   python setup_config.py
   ```
3. Or manually copy and edit:
   ```bash
   copy .env.example .env
   notepad .env
   ```

### "SyntaxError in prompts.py"

If you see:
```
SyntaxError: f-string expression part cannot include a backslash
```

This was fixed in the update. Pull the latest changes:

```bash
git pull origin main
```

## Benefits of the New System

✅ **Clearer errors** - Know exactly what's wrong and how to fix it
✅ **Faster setup** - Interactive wizard guides you through configuration
✅ **Fewer mistakes** - Validation catches issues before they cause problems
✅ **Better onboarding** - New users don't get stuck with configuration
✅ **Team-friendly** - Easy to set up on multiple machines

## Questions?

If you have questions about the new configuration system, please:

1. Read the main [README.md](README.md) - See the "Configuration" section
2. Run the validation tool: `python -m src.utils.env_helper validate`
3. Open an issue on GitHub if you're still stuck

---

**Last Updated**: 2025-01-11
**Version**: 2.0 - Configuration System Update
