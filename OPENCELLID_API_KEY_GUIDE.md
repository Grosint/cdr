# How to Get OpenCellID API Key - Complete Guide

## Overview

OpenCellID is a free, open-source database of cell tower locations. You need an API key to use their service for looking up cell tower coordinates using MCC, MNC, LAC, and Cell ID.

## Step-by-Step Procedure

### Step 1: Visit OpenCellID Website

1. Open your web browser
2. Navigate to: **https://www.opencellid.org/**
3. You'll see the OpenCellID homepage

### Step 2: Create an Account

1. Click on **"Sign Up"** or **"Register"** button (usually in the top right corner)
2. Fill in the registration form:
   - **Email address**: Enter your valid email
   - **Password**: Create a strong password
   - **Username**: Choose a username (optional in some cases)
3. Accept the Terms of Service and Privacy Policy
4. Click **"Register"** or **"Sign Up"**

### Step 3: Verify Your Email

1. Check your email inbox for a verification email from OpenCellID
2. Click on the verification link in the email
3. Your account will be activated

### Step 4: Log In to Your Account

1. Go back to **https://www.opencellid.org/**
2. Click **"Login"** or **"Sign In"**
3. Enter your email and password
4. Click **"Login"**

### Step 5: Access API Key Section

1. After logging in, look for one of these options:
   - **"API"** menu item in the navigation
   - **"My Account"** or **"Dashboard"** section
   - **"API Keys"** or **"Get API Key"** link
   - **"Developer"** section

2. Common locations:
   - Top navigation menu → "API"
   - User profile dropdown → "API Settings"
   - Dashboard → "API Keys"

### Step 6: Generate API Key

1. Once in the API section, you'll see:
   - **"Generate API Key"** button, OR
   - **"Create New Key"** button, OR
   - An existing key if you've created one before

2. Click the button to generate a new API key

3. The API key will be displayed (usually a long alphanumeric string)

4. **IMPORTANT**: Copy the API key immediately and save it securely!

### Step 7: Copy and Save Your API Key

The API key will look something like:
```
a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
```

**Save it in a secure location** - you won't be able to see it again after closing the page!

### Step 8: Add API Key to Your Project

#### Option A: Using .env File (Recommended)

1. Navigate to your project root directory:
   ```bash
   cd /Users/navitas28/Work/grosint/cdr
   ```

2. Open or create a `.env` file:
   ```bash
   # If file doesn't exist, create it
   touch .env

   # Or edit existing file
   nano .env
   # or
   code .env  # if using VS Code
   ```

3. Add the API key to the `.env` file:
   ```bash
   OPENCELLID_API_KEY=your_actual_api_key_here
   ```

4. Save the file

#### Option B: Set as Environment Variable

**On macOS/Linux:**
```bash
export OPENCELLID_API_KEY="your_actual_api_key_here"
```

**On Windows (Command Prompt):**
```cmd
set OPENCELLID_API_KEY=your_actual_api_key_here
```

**On Windows (PowerShell):**
```powershell
$env:OPENCELLID_API_KEY="your_actual_api_key_here"
```

### Step 9: Verify the Setup

1. Restart your backend server if it's running:
   ```bash
   # Stop the server (Ctrl+C)
   # Then restart it
   cd backend
   python main.py
   # or
   uvicorn main:app --reload
   ```

2. The server will automatically load the API key from the `.env` file

3. Test the KML export feature - it should now use OpenCellID for coordinate lookups

## Alternative: Using Mozilla Location Service (No API Key Required)

If you don't want to get an OpenCellID API key, the system will automatically fall back to Mozilla Location Service, which doesn't require an API key. However, OpenCellID generally has better coverage and accuracy.

## API Key Limits

OpenCellID free tier typically includes:
- **Rate limits**: Usually 1000 requests per day
- **No credit card required**
- **Free for non-commercial use**

For higher limits, check OpenCellID's pricing page for paid plans.

## Troubleshooting

### Problem: Can't find API section
- **Solution**: Look for "Developer", "Account Settings", or check the footer links

### Problem: API key not working
- **Solution**:
  1. Verify the key is correctly copied (no extra spaces)
  2. Check that `.env` file is in the project root
  3. Restart the server after adding the key
  4. Check server logs for API errors

### Problem: Rate limit exceeded
- **Solution**:
  - Wait 24 hours for the limit to reset
  - Consider upgrading to a paid plan
  - The system will automatically fall back to Mozilla Location Service

### Problem: Key not loading from .env
- **Solution**:
  1. Ensure `.env` file is in the project root (same level as `backend/` folder)
  2. Check file permissions: `chmod 644 .env`
  3. Verify the format: `OPENCELLID_API_KEY=your_key` (no spaces around `=`)
  4. Make sure `python-dotenv` is installed: `pip install python-dotenv`

## Security Best Practices

1. **Never commit `.env` file to Git**
   - Add `.env` to your `.gitignore` file
   - Use `.env.example` as a template without actual keys

2. **Keep your API key secret**
   - Don't share it publicly
   - Don't include it in code or documentation

3. **Rotate keys if compromised**
   - Generate a new key from OpenCellID dashboard
   - Update your `.env` file
   - Revoke the old key if possible

## Quick Reference

**Website**: https://www.opencellid.org/
**Registration**: https://www.opencellid.org/register (or look for Sign Up)
**Login**: https://www.opencellid.org/login
**API Documentation**: Usually found in the API section after login

## Example .env File

```bash
# MongoDB Configuration
MONGODB_URL=mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority
DATABASE_NAME=cdr_intelligence
PORT=8000

# OpenCellID API Key (for cell tower coordinate lookup)
OPENCELLID_API_KEY=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
```

## Next Steps

After setting up your API key:

1. ✅ Test the KML export feature
2. ✅ Verify cell tower coordinate lookups are working
3. ✅ Check server logs to confirm API calls are successful
4. ✅ Open exported KML files in Google Earth to visualize paths

Your CDR Intelligence Platform is now ready to automatically lookup cell tower coordinates!
