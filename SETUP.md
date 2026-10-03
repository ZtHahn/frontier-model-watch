# Frontier Model Watch — setup (about 10 minutes, $0)

> Already set up for this repo. These steps are for rebuilding it from scratch or making a copy.

You'll create a Telegram bot, put two files in a private GitHub repo, and add three settings. After that, GitHub checks for new AI models every 2 hours and messages you on Telegram.

## 1. Create your Telegram bot (3 min)

1. In Telegram, open a chat with **@BotFather** (blue check mark).
2. Send `/newbot`. Pick a name (e.g. "Model Watch") and a username ending in `bot`.
3. BotFather replies with a **token** like `7234567890:AAH...`. Copy it. This is your `TELEGRAM_BOT_TOKEN`.
4. Open a chat with your new bot and press **Start** (or send "hi"). The bot can't message you until you do this.
5. Get your chat ID: open a chat with **@userinfobot** and press Start. It replies with your **Id** (a number). This is your `TELEGRAM_CHAT_ID`.

## 2. Create the repo (3 min)

1. Go to github.com → **New repository**. Name it `frontier-model-watch`, choose **Private**, tick **Add a README**, then **Create**.
2. Click **Add file → Upload files** and upload `check_releases.py`. Commit.
3. Click **Add file → Create new file**. In the name box type exactly
   `.github/workflows/check.yml`
   (typing the slashes creates the folders). Paste the contents of `check.yml`. Commit.

## 3. Add your settings (2 min)

In the repo: **Settings → Secrets and variables → Actions**.

- **Secrets** tab → **New repository secret**:
  - `TELEGRAM_BOT_TOKEN` = the token from BotFather
  - `TELEGRAM_CHAT_ID` = your Id number
- **Variables** tab → **New repository variable**:
  - `DASHBOARD_URL` = `https://claude.ai/artifact/RD7Sw7sZTW77KqtCnzoeRq`

## 4. Turn it on and test (1 min)

1. Go to the **Actions** tab. If asked, click **I understand my workflows, go ahead and enable them**.
2. Click **Frontier Model Watch → Run workflow** (leave "Send a test message" ticked) → **Run workflow**.
3. Within a minute you should get a "connected" message on Telegram. The first run records today's releases silently, so you're only pinged for genuinely new models.

From then on it runs every 2 hours on its own.

## Good to know

- **Cost:** $0. Private repos get 2,000 free Actions minutes a month; this uses about 150.
- **If something breaks:** GitHub emails you when a run fails (e.g. a site is down). One failed run is normal; repeated failures mean a source changed and the script needs a tweak.
- **The dashboard link** opens on your phone in the Claude app or browser when you're signed in. To share it with others, use the dashboard's Share menu first.
- **Pause it:** Actions tab → Frontier Model Watch → ··· → Disable workflow.
- **Check more or less often:** edit the `cron` line in `check.yml` (`23 */2 * * *` = every 2 hours at :23).
