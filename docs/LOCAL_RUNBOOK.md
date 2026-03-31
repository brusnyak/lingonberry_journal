# Local Runbook

## 1) Install deps

```bash
make install
```

## 2) Configure env

```bash
cp .env.example .env
# fill all secrets
```

## 3) Run web app

```bash
make run-web
```

## 4) Run bot

```bash
make run-bot
```

## 5) Run web + bot together (background)

```bash
make run-all
bash scripts/manage.sh status
# stop when done:
bash scripts/manage.sh stop all
```

On Linux servers with installed journal systemd units, the same `manage.sh` commands automatically use `systemd` instead of local `nohup` processes.

## 6) Trigger SL/TP poll check manually

```bash
make sltp-check
```

## 7) Trigger ML export

```bash
make export-ml
```

## 8) Run tests and pre-push checks

```bash
make test
make deploy-prep
```
