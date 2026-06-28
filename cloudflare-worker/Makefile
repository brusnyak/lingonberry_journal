.PHONY: deploy dev logs test

deploy:
	npx wrangler deploy

dev:
	npx wrangler dev

logs:
	npx wrangler tail

test:
	curl -s "https://ctrader-callback.recareo.workers.dev/callback?code=abc123" | head -20