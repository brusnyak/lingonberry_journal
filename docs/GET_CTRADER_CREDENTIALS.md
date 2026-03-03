# How to Get cTrader API Credentials

## 🎯 Current Status

Your credentials are **INVALID** - the Client ID format is incorrect.

## 📋 Your Account Info

From the JSON you provided:
- **User ID**: 5585174
- **Account ID**: 44798689 (ctidTraderAccountId)
- **Account Number**: 2067137
- **Broker**: BlackBull Markets (Demo)
- **Balance**: $9,725.70 USD
- **Leverage**: 100:1

## 🔧 How to Get Valid Credentials

### Step 1: Go to Applications Page

Visit: https://openapi.ctrader.com/apps

You should see your application(s) listed.

### Step 2: Find Your Application

Look for an application you created (or create a new one if needed).

### Step 3: Get Credentials

Click the **"Playground"** button on your application.

You'll see a page with these fields:

```
┌─────────────────────────────────────────────┐
│ cTrader Open API Playground                 │
├─────────────────────────────────────────────┤
│                                             │
│ Scope: [trading ▼]                         │
│                                             │
│ [Get token]                                 │
│                                             │
│ Access Token:                               │
│ ┌─────────────────────────────────────────┐│
│ │ mos8Bw3D4EG0fRPd4Eqq0JxaFT4zjd8e...   ││
│ └─────────────────────────────────────────┘│
│                                             │
│ Refresh Token:                              │
│ ┌─────────────────────────────────────────┐│
│ │ VCuafFhy81AFZjsWkbuEzdOhhRj5YTWz...   ││
│ └─────────────────────────────────────────┘│
│                                             │
└─────────────────────────────────────────────┘
```

### Step 4: View Application Credentials

Go back to the main Applications page and click **"View"** in the Credentials column.

You'll see:

```
Client ID: 5430012
Client Secret: 012sds23dlkjQsd...
```

## ✅ What You Need to Copy

You need **4 values total**:

| Field | Where to Find | Example Format |
|-------|---------------|----------------|
| Client ID | Applications → View Credentials | `5430012` (just numbers) |
| Client Secret | Applications → View Credentials | `012sds23dlkjQsd...` (long string) |
| Access Token | Playground → Get token | `mos8Bw3D4EG0fRPd...` (long string) |
| Refresh Token | Playground → Get token | `VCuafFhy81AFZjsWkbuEzdOhhRj5...` (long string) |

## 🚨 Common Mistakes

### ❌ Wrong Client ID Format

```bash
# WRONG - This is NOT the Client ID
CTRADER_CLIENT_ID=19103_504eATsGZ5s57offfwCL88DhVBP0Cq3QZsZCiv8fHZeTReMz1C

# CORRECT - Client ID is just a number
CTRADER_CLIENT_ID=19103
```

### ❌ Confusing User ID with Client ID

- **User ID** (5585174) - Your cTrader account ID
- **Client ID** (e.g., 19103) - Your API application ID
- These are different!

### ❌ Using Account ID as Client ID

- **Account ID** (44798689) - Your trading account
- **Client ID** (e.g., 19103) - Your API application
- These are different!

## 📝 Correct .env Format

Once you have all 4 values, your .env should look like:

```bash
# cTrader Open API Credentials
CTRADER_CLIENT_ID=5430012
CTRADER_CLIENT_SECRET=012sds23dlkjQsd_asdXCVCVAS_218kjashf
CTRADER_ACCESS_TOKEN=mos8Bw3D4EG0fRPd4Eqq0JxaFT4zjd8e4YijNezh_ag
CTRADER_REFRESH_TOKEN=VCuafFhy81AFZjsWkbuEzdOhhRj5YTWz8fWUwHam7KM
CTRADER_ACCOUNT_ID=44798689
```

## 🔄 After Updating

1. Save your .env file
2. Run validation: `python3 scripts/validate_ctrader_tokens.py`
3. If successful, test data fetch: `python3 scripts/test_ctrader_connection.py`

## 💡 Need Help?

If you're still having issues:

1. **Create a NEW application** at https://openapi.ctrader.com/apps
2. Click "Create Application"
3. Fill in the details
4. Get credentials from the new app
5. Use those in your .env file

## 📸 Visual Guide

When you're on the Playground page, you should see something like this:

```
Access Token: [long string starting with letters/numbers]
Refresh Token: [long string starting with letters/numbers]
```

When you click "View" in Credentials:

```
Client ID: [just numbers, like 5430012]
Client Secret: [long string]
```

---

**Once you have the correct credentials, paste them here and I'll update your .env and test immediately!**
