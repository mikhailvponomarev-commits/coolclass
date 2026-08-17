# CoolClassTestBot

Standalone Telegram bot for the CoolClass 10-question mathematics diagnostic.

## Render

Create a **NEW** Render Web Service from this repository. Do not change the existing CoolClass service.

Start command:

`python quiz_bot.py`

Environment variables:

- `BOT_TOKEN` = token from @BotFather for @CoolclassTestbot
- `ADMIN_USERNAME` = `Mikhail7890`
- `ADMIN_CHAT_ID` = optional numeric Telegram chat ID
- `PUBLIC_URL` = the new Render service URL, without a trailing slash
- `WEBHOOK_SECRET` = any private random string
- `DB_PATH` = `coolclass_quiz.db`

The administrator should open @CoolclassTestbot and press **Start** once. The bot records the administrator chat ID when the Telegram username matches `ADMIN_USERNAME`, so quiz results can then be sent directly to the administrator.

The bot is completely separate at runtime from the old CoolClass bot: separate token, webhook, Render service and database file.
