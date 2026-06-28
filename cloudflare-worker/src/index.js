/**
 * cTrader OAuth Callback Worker
 *
 * Route: recareo.uk/callback*
 *
 * Receives the short-lived OAuth code from cTrader,
 * displays it safely, and optionally exchanges it for tokens.
 *
 * This is the fastest way to get /callback working on recareo.uk
 * without a full Vercel deployment.
 */

// ── cTrader OAuth Configuration ──────────────────────────────────────────
// These are injected as Worker secrets:
//   CTRADER_CLIENT_ID
//   CTRADER_SECRET
// Optionally set via wrangler secret put

const CTRADER_TOKEN_URL = "https://openapi.ctrader.com/apps/token";

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // ── Only handle /callback ─────────────────────────────────────────────
    if (url.pathname !== "/callback") {
      return new Response("Not Found", { status: 404 });
    }

    const code = url.searchParams.get("code") || "";
    const error = url.searchParams.get("error") || url.searchParams.get("errorCode") || "";
    const description = url.searchParams.get("description") || "";

    // ── Handle OAuth error ────────────────────────────────────────────────
    if (error) {
      return htmlResponse(
        "OAuth Error",
        `<h1>OAuth Error</h1>
         <p><strong>${escapeHtml(error)}</strong></p>
         <p>${escapeHtml(description)}</p>`,
        400
      );
    }

    // ── Handle missing code ───────────────────────────────────────────────
    if (!code) {
      return htmlResponse(
        "OAuth Callback",
        `<h1>OAuth Callback</h1>
         <p>No authorization code was provided.</p>`,
        400
      );
    }

    // ── Exchange code for tokens (if secrets are configured) ───────────────
    let tokenResult = null;
    let tokenError = null;

    if (env.CTRADER_CLIENT_ID && env.CTRADER_SECRET) {
      try {
        const tokenParams = new URLSearchParams({
          grant_type: "authorization_code",
          code: code,
          client_id: env.CTRADER_CLIENT_ID,
          client_secret: env.CTRADER_SECRET,
          redirect_uri: "https://recareo.uk/callback",
        });

        const tokenResp = await fetch(`${CTRADER_TOKEN_URL}?${tokenParams.toString()}`, {
          method: "GET",
          headers: { "Accept": "application/json" },
        });

        if (tokenResp.ok) {
          tokenResult = await tokenResp.json();
        } else {
          tokenError = `${tokenResp.status}: ${await tokenResp.text()}`;
        }
      } catch (err) {
        tokenError = err.message;
      }
    }

    // ── Render response ───────────────────────────────────────────────────
    let tokenSection = "";
    if (tokenResult) {
      tokenSection = `
        <h2>Tokens Exchanged Successfully</h2>
        <p>Use the refresh token to maintain long-lived access.</p>
        <pre style="background:#1e1e2e;color:#cdd6f4;padding:16px;border-radius:8px;overflow-x:auto;">
${escapeHtml(JSON.stringify(tokenResult, null, 2))}
        </pre>
        <p style="color:#f38ba8;font-size:0.9em;">
          &#x26a0;&#xfe0f; These tokens are displayed once. Rotate the secret if compromised.
        </p>`;
    } else if (tokenError) {
      tokenSection = `
        <h2>Token Exchange Failed</h2>
        <p style="color:#f38ba8;">${escapeHtml(tokenError)}</p>`;
    }

    return htmlResponse(
      "OAuth Code Received",
      `<h1>Authorization Code Received</h1>
       <p>The short-lived code below must be exchanged for an access token.
       Do not paste it into chats or commit it to files.</p>
       <label style="display:block;font-weight:600;margin-top:20px;">Code</label>
       <textarea readonly style="width:100%;height:80px;font-family:monospace;background:#313244;color:#cdd6f4;border:1px solid #45475a;border-radius:6px;padding:8px;">${escapeHtml(code)}</textarea>
       ${tokenSection}
       <hr style="border-color:#45475a;margin-top:24px;" />
       <p style="font-size:0.85em;color:#6c7086;">
         Lingonberry Journal &middot; recareo.uk &middot; cTrader OAuth callback
       </p>`,
      200
    );
  },
};

function htmlResponse(title, body, status = 200) {
  return new Response(
    `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>${escapeHtml(title)}</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: system-ui, -apple-system, sans-serif;
      background: #11111b;
      color: #cdd6f4;
      margin: 40px auto;
      max-width: 720px;
      padding: 0 16px;
      line-height: 1.6;
    }
    h1 { color: #89b4fa; margin-bottom: 12px; }
    h2 { color: #a6e3a1; margin: 20px 0 8px; }
    p  { margin-bottom: 8px; }
    hr { margin: 16px 0; border: none; border-top: 1px solid #45475a; }
    label { display: block; font-weight: 600; margin-top: 20px; margin-bottom: 4px; }
    textarea { width: 100%; resize: vertical; }
    strong { color: #f38ba8; }
  </style>
</head>
<body>
  ${body}
</body>
</html>`,
    {
      status,
      headers: { "Content-Type": "text/html; charset=utf-8" },
    }
  );
}

function escapeHtml(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}