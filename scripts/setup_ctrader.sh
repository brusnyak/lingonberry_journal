#!/bin/bash
# Setup script for cTrader Open API integration

echo "=================================================="
echo "cTrader Open API Setup"
echo "=================================================="
echo ""

# Check if virtual environment is active
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo "⚠️  No virtual environment detected"
    echo "   Activate with: source .venv/bin/activate"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "📦 Installing cTrader OpenAPI Python library..."
echo ""

pip install ctrader-open-api twisted pyOpenSSL service_identity

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Installation successful!"
    echo ""
    echo "=================================================="
    echo "Next Steps:"
    echo "=================================================="
    echo ""
    echo "1. Get your credentials from cTrader Playground:"
    echo "   https://openapi.ctrader.com/apps"
    echo ""
    echo "2. Update your .env file with:"
    echo "   CTRADER_CLIENT_ID=your_client_id"
    echo "   CTRADER_CLIENT_SECRET=your_client_secret"
    echo "   CTRADER_ACCESS_TOKEN=your_access_token"
    echo "   CTRADER_REFRESH_TOKEN=your_refresh_token"
    echo ""
    echo "3. Test the connection:"
    echo "   python infra/ctrader_protobuf_client.py"
    echo ""
    echo "4. Read the guide:"
    echo "   cat docs/CTRADER_API_GUIDE.md"
    echo ""
else
    echo ""
    echo "❌ Installation failed"
    echo "   Try manually: pip install ctrader-open-api twisted pyOpenSSL service_identity"
    exit 1
fi
