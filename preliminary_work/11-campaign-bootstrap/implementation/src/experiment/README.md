# Pithos experiment

1. Replace the template in `PROJECT.md` with the concrete objective and acceptance criteria.
2. Add the private GitHub repository when it exists:

```bash
git remote add origin <private_repository_url>
```

3. From the Pithos repository root, launch one supervised run:

```bash
harness/.venv/bin/python harness/scripts/run_experiment.py experiments/<experiment-id>
```

Telegram is activated automatically only when `TELEGRAM_BOT_TOKEN` and `TELEGRAM_USER_ID` are present in the
host environment. Git operations are activated only when `origin` exists. Neither credential enters this
workspace.
