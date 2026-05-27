import { createStore } from "/js/AlpineStore.js";
import * as API from "/js/api.js";

const CONNECTORS = [
  {
    id: "my-browser",
    name: "My Browser",
    logo: "MB",
    icon: "travel_explore",
    tone: "chrome",
    type: "built-in",
    surfaceId: "browser",
    description: "Use Vini AI Computer's real browser surface for web research and authenticated browsing.",
    requirements: ["Vini AI Computer browser surface"],
    prompts: ["Open my browser and search for competitor pricing.", "Use the browser to inspect the latest docs for this API."],
  },
  {
    id: "gmail",
    name: "Gmail",
    logo: "M",
    icon: "mail",
    tone: "google",
    type: "oauth",
    authUrl: "https://accounts.google.com/",
    description: "Open Google sign-in in your real Windows browser for Gmail access and permission setup.",
    requirements: ["Google account permission in Chrome or Edge", "A Gmail API/OAuth credential flow before Vini AI marks it connected"],
    prompts: ["Draft a concise reply to my latest client email.", "Summarize unread Gmail threads from today."],
  },
  {
    id: "github",
    name: "GitHub",
    logo: "GH",
    icon: "code",
    tone: "mono",
    type: "api-key",
    authUrl: "https://github.com/settings/tokens",
    envKeys: ["GITHUB_TOKEN"],
    description: "Connect repositories, issues, pull requests, and code operations with a GitHub token.",
    requirements: ["Fine-grained GitHub token with the repositories you want Vini AI to access"],
    prompts: ["Summarize the latest open pull requests.", "Create an issue from this bug report."],
  },
  {
    id: "google-drive",
    name: "Google Drive",
    logo: "DR",
    icon: "drive_folder_upload",
    tone: "google",
    type: "oauth",
    authUrl: "https://drive.google.com/",
    description: "Open Google Drive sign-in in your real Windows browser for file access and permission setup.",
    requirements: ["Google account permission in Chrome or Edge"],
    prompts: ["Find the latest proposal in Drive.", "Summarize this project folder."],
  },
  {
    id: "google-calendar",
    name: "Google Calendar",
    logo: "31",
    icon: "calendar_month",
    tone: "calendar",
    type: "oauth",
    authUrl: "https://calendar.google.com/",
    description: "Open Google Calendar sign-in in your real Windows browser for schedule access and permission setup.",
    requirements: ["Google account permission in Chrome or Edge"],
    prompts: ["Check my meetings tomorrow.", "Create a follow-up event for Friday afternoon."],
  },
  {
    id: "instagram",
    name: "Instagram",
    logo: "IG",
    icon: "photo_camera",
    tone: "pink",
    type: "oauth",
    authUrl: "https://www.instagram.com/accounts/login/",
    description: "Open Instagram sign-in for publishing and account workflows.",
    requirements: ["Instagram account permission"],
    prompts: ["Draft a post caption for this launch.", "Review recent Instagram content ideas."],
  },
  {
    id: "meta-ads",
    name: "Meta Ads Manager",
    logo: "∞",
    icon: "campaign",
    tone: "blue",
    type: "oauth",
    authUrl: "https://business.facebook.com/adsmanager/",
    description: "Open Meta Ads Manager for ad account permission and campaign work.",
    requirements: ["Meta Business account permission"],
    prompts: ["Review ad performance and suggest changes.", "Create campaign copy variants."],
  },
  {
    id: "notion",
    name: "Notion",
    logo: "N",
    icon: "article",
    tone: "mono",
    type: "oauth",
    authUrl: "https://www.notion.so/login",
    description: "Open Notion sign-in for workspace content and notes access.",
    requirements: ["Notion workspace permission"],
    prompts: ["Search Notion for the onboarding checklist.", "Turn this chat into a Notion task list."],
  },
  {
    id: "outlook-mail",
    name: "Outlook Mail",
    logo: "O",
    icon: "alternate_email",
    tone: "microsoft",
    type: "plugin",
    pluginName: "_email_integration",
    description: "Use the built-in Email integration for Outlook, IMAP, SMTP, and inbox automation.",
    requirements: ["Email integration settings", "Mailbox credentials or app password"],
    prompts: ["Reply to an Outlook email with a polished response.", "Monitor this inbox for support requests."],
  },
  {
    id: "whatsapp",
    name: "WhatsApp",
    logo: "WA",
    icon: "chat",
    tone: "green",
    type: "plugin",
    pluginName: "_whatsapp_integration",
    description: "Use the built-in WhatsApp bridge with real QR pairing and message handling.",
    requirements: ["WhatsApp QR pairing", "Local bridge process"],
    prompts: ["Reply to my latest WhatsApp lead.", "Summarize unread WhatsApp messages."],
  },
  {
    id: "telegram",
    name: "Telegram",
    logo: "TG",
    icon: "send",
    tone: "blue",
    type: "plugin",
    pluginName: "_telegram_integration",
    description: "Use the built-in Telegram bot integration for chats and updates.",
    requirements: ["Telegram bot token", "Webhook or polling configuration"],
    prompts: ["Send a Telegram status update.", "Watch this Telegram bot for incoming tasks."],
  },
  {
    id: "email",
    name: "Email",
    logo: "@",
    icon: "mail",
    tone: "microsoft",
    type: "plugin",
    pluginName: "_email_integration",
    description: "Connect Gmail, Outlook, iCloud, Yahoo, Exchange, or custom IMAP/SMTP accounts.",
    requirements: ["Email provider settings", "Mailbox credentials or app password"],
    prompts: ["Draft an email from this summary.", "Route incoming emails into task chats."],
  },
  {
    id: "codex",
    name: "Codex/ChatGPT Account",
    logo: "CX",
    icon: "key",
    tone: "violet",
    type: "plugin",
    pluginName: "_oauth",
    description: "Connect your Codex or ChatGPT account to use OpenAI models through the existing account auth flow.",
    requirements: ["Codex/ChatGPT sign-in"],
    prompts: ["Use my connected OpenAI account for the main model.", "Refresh Codex model availability."],
  },
  {
    id: "similarweb",
    name: "Similarweb",
    logo: "SW",
    icon: "monitoring",
    tone: "orange",
    type: "api-key",
    authUrl: "https://www.similarweb.com/",
    envKeys: ["SIMILARWEB_API_KEY"],
    description: "Access website traffic, audience, SEO, and app intelligence data.",
    requirements: ["Similarweb API key"],
    prompts: ["Compare traffic trends for these competitors.", "Find the strongest acquisition channels."],
  },
  {
    id: "dify",
    name: "Dify",
    logo: "DF",
    icon: "schema",
    tone: "mono",
    type: "api-key",
    authUrl: "https://cloud.dify.ai/",
    envKeys: ["DIFY_API_KEY"],
    description: "Connect Dify applications and workflow endpoints.",
    requirements: ["Dify app API key and endpoint"],
    prompts: ["Call my Dify workflow with this payload.", "Summarize the output from a Dify app."],
  },
  {
    id: "ahrefs",
    name: "Ahrefs",
    logo: "A",
    icon: "query_stats",
    tone: "blue",
    type: "api-key",
    authUrl: "https://app.ahrefs.com/",
    envKeys: ["AHREFS_API_KEY"],
    description: "Analyze SEO performance, backlinks, rankings, and keyword research.",
    requirements: ["Ahrefs API key"],
    prompts: ["Find keyword gaps for this domain.", "Review backlinks for a competitor."],
  },
  {
    id: "canva",
    name: "Canva",
    logo: "C",
    icon: "palette",
    tone: "canva",
    type: "oauth",
    authUrl: "https://www.canva.com/login",
    description: "Open Canva sign-in for design creation and export workflows.",
    requirements: ["Canva account permission"],
    prompts: ["Create a presentation from this outline.", "Resize this design for social platforms."],
  },
  {
    id: "supabase",
    name: "Supabase",
    logo: "SB",
    icon: "database",
    tone: "green",
    type: "api-key",
    authUrl: "https://supabase.com/dashboard",
    envKeys: ["SUPABASE_ACCESS_TOKEN"],
    description: "Manage Supabase projects, databases, and data operations.",
    requirements: ["Supabase access token"],
    prompts: ["Inspect this table schema.", "Generate SQL for the requested report."],
  },
  {
    id: "vercel",
    name: "Vercel",
    logo: "▲",
    icon: "change_history",
    tone: "mono",
    type: "api-key",
    authUrl: "https://vercel.com/account/tokens",
    envKeys: ["VERCEL_TOKEN"],
    description: "Manage deployments, projects, domains, and environment variables.",
    requirements: ["Vercel token"],
    prompts: ["Check the latest deployment status.", "Create a preview deployment summary."],
  },
  {
    id: "zapier",
    name: "Zapier",
    logo: "Z",
    icon: "conversion_path",
    tone: "orange",
    type: "oauth",
    authUrl: "https://zapier.com/app/login",
    description: "Open Zapier to connect workflow automations across apps.",
    requirements: ["Zapier account permission"],
    prompts: ["Trigger a Zap from this task.", "Create an automation idea for this workflow."],
  },
  {
    id: "prisma-postgres",
    name: "Prisma Postgres",
    logo: "P",
    icon: "deployed_code",
    tone: "mono",
    type: "api-key",
    authUrl: "https://console.prisma.io/",
    envKeys: ["PRISMA_API_KEY"],
    description: "Connect to Postgres resources and Prisma project tooling.",
    requirements: ["Prisma API key or database URL"],
    prompts: ["Review this Prisma schema.", "Generate a migration plan."],
  },
  {
    id: "heygen",
    name: "HeyGen",
    logo: "HG",
    icon: "video_camera_front",
    tone: "canva",
    type: "api-key",
    authUrl: "https://app.heygen.com/settings?nav=API",
    envKeys: ["HEYGEN_API_KEY"],
    description: "Generate lifelike AI avatars, voices, and video workflows.",
    requirements: ["HeyGen API key"],
    prompts: ["Create a talking-head video brief.", "Generate a script for an avatar presenter."],
  },
  {
    id: "slack",
    name: "Slack",
    logo: "SL",
    icon: "tag",
    tone: "slack",
    type: "api-key",
    authUrl: "https://api.slack.com/apps",
    envKeys: ["SLACK_BOT_TOKEN"],
    description: "Read and write Slack conversations with a bot token.",
    requirements: ["Slack app", "Bot token with approved scopes"],
    prompts: ["Summarize today in this Slack channel.", "Post a status update to the team."],
  },
  {
    id: "cloudflare",
    name: "Cloudflare",
    logo: "CF",
    icon: "cloud",
    tone: "orange",
    type: "api-key",
    authUrl: "https://dash.cloudflare.com/profile/api-tokens",
    envKeys: ["CLOUDFLARE_API_TOKEN"],
    description: "Manage Workers, DNS, apps, and deployable resources.",
    requirements: ["Cloudflare API token"],
    prompts: ["Review Cloudflare Worker logs.", "Create a DNS change checklist."],
  },
  {
    id: "metabase",
    name: "Metabase",
    logo: "MB",
    icon: "analytics",
    tone: "blue",
    type: "api-key",
    authUrl: "https://www.metabase.com/",
    envKeys: ["METABASE_API_KEY"],
    description: "Access analytics, dashboards, and query results.",
    requirements: ["Metabase API key or session credentials"],
    prompts: ["Explain this dashboard trend.", "Pull the last 7 days of revenue data."],
  },
  {
    id: "stripe",
    name: "Stripe",
    logo: "S",
    icon: "payments",
    tone: "violet",
    type: "api-key",
    authUrl: "https://dashboard.stripe.com/apikeys",
    envKeys: ["STRIPE_API_KEY"],
    description: "Streamline billing, payments, subscriptions, and account operations.",
    requirements: ["Stripe restricted or secret key with needed scopes"],
    prompts: ["Summarize failed payments this week.", "Create a billing issue checklist."],
  },
  {
    id: "make",
    name: "Make",
    logo: "MK",
    icon: "auto_awesome_motion",
    tone: "mono",
    type: "api-key",
    authUrl: "https://www.make.com/en/user/api",
    envKeys: ["MAKE_API_KEY"],
    description: "Turn Make workflows into automation execution surfaces.",
    requirements: ["Make API key"],
    prompts: ["Run a Make scenario for this lead.", "Create a workflow plan in Make."],
  },
  {
    id: "crypto-com",
    name: "Crypto.com",
    logo: "CR",
    icon: "currency_bitcoin",
    tone: "blue",
    type: "api-key",
    authUrl: "https://crypto.com/exchange/user/settings/api-management",
    envKeys: ["CRYPTO_COM_API_KEY", "CRYPTO_COM_API_SECRET"],
    keyMode: "all",
    description: "Stream live market data, prices, volumes, order books, and trends.",
    requirements: ["Crypto.com API key and secret"],
    prompts: ["Track market prices for these assets.", "Summarize exchange order book movement."],
  },
  {
    id: "hugging-face",
    name: "Hugging Face",
    logo: "HF",
    icon: "psychology",
    tone: "yellow",
    type: "api-key",
    authUrl: "https://huggingface.co/settings/tokens",
    envKeys: ["HUGGINGFACE_API_KEY"],
    description: "Explore models, datasets, and inference endpoints.",
    requirements: ["Hugging Face access token"],
    prompts: ["Find models for speech recognition.", "Call this inference endpoint."],
  },
  {
    id: "airtable",
    name: "Airtable",
    logo: "AT",
    icon: "view_kanban",
    tone: "orange",
    type: "api-key",
    authUrl: "https://airtable.com/create/tokens",
    envKeys: ["AIRTABLE_API_KEY"],
    description: "Organize structured data, records, and team workflows.",
    requirements: ["Airtable personal access token"],
    prompts: ["Update this Airtable record.", "Summarize open records by status."],
  },
  {
    id: "coingecko",
    name: "CoinGecko",
    logo: "CG",
    icon: "finance_mode",
    tone: "green",
    type: "api-key",
    authUrl: "https://www.coingecko.com/en/developers/dashboard",
    envKeys: ["COINGECKO_API_KEY"],
    description: "Access real-time market data, prices, trends, and on-chain analytics.",
    requirements: ["CoinGecko API key for higher limits"],
    prompts: ["Compare token prices this week.", "Build a short crypto market summary."],
  },
  {
    id: "line",
    name: "LINE",
    logo: "LN",
    icon: "forum",
    tone: "green",
    type: "api-key",
    authUrl: "https://developers.line.biz/console/",
    envKeys: ["LINE_CHANNEL_ACCESS_TOKEN"],
    description: "Connect LINE Official Accounts for automated messaging.",
    requirements: ["LINE channel access token"],
    prompts: ["Send a LINE reply to this customer.", "Summarize LINE support requests."],
  },
  {
    id: "elevenlabs",
    name: "ElevenLabs",
    logo: "11",
    icon: "graphic_eq",
    tone: "mono",
    type: "api-key",
    authUrl: "https://elevenlabs.io/app/settings/api-keys",
    envKeys: ["ELEVENLABS_API_KEY"],
    description: "Generate, clone, and transcribe lifelike speech with ElevenLabs.",
    requirements: ["ElevenLabs API key"],
    prompts: ["Generate a natural-sounding voiceover.", "Transcribe and clean this audio clip."],
  },
  {
    id: "playwright",
    name: "Playwright",
    logo: "PW",
    icon: "theater_comedy",
    tone: "green",
    type: "built-in",
    surfaceId: "browser",
    description: "Use Vini AI's real browser automation layer for testing, scraping, and workflows.",
    requirements: ["Browser plugin enabled"],
    prompts: ["Test this login flow.", "Extract product names from this page."],
  },
  {
    id: "tldv",
    name: "tl;dv",
    logo: "TV",
    icon: "video_chat",
    tone: "mono",
    type: "oauth",
    authUrl: "https://tldv.io/app/login",
    description: "Open tl;dv for meeting recordings, transcripts, and highlights.",
    requirements: ["tl;dv account permission"],
    prompts: ["Summarize this meeting transcript.", "Create follow-up tasks from a call."],
  },
  {
    id: "wix",
    name: "Wix",
    logo: "WIX",
    icon: "web",
    tone: "mono",
    type: "oauth",
    authUrl: "https://users.wix.com/signin",
    description: "Open Wix for site content and automation workflows.",
    requirements: ["Wix account permission"],
    prompts: ["Update a Wix page draft.", "Review SEO titles for this site."],
  },
  {
    id: "serena",
    name: "Serena",
    logo: "SE",
    icon: "data_object",
    tone: "mono",
    type: "mcp",
    description: "Use Serena's semantic code tools through an external MCP server.",
    requirements: ["Configured MCP server command"],
    prompts: ["Use Serena to inspect this codebase.", "Perform a symbol-aware refactor."],
  },
  {
    id: "asana",
    name: "Asana",
    logo: "AS",
    icon: "task_alt",
    tone: "pink",
    type: "api-key",
    authUrl: "https://app.asana.com/0/my-apps",
    envKeys: ["ASANA_ACCESS_TOKEN"],
    description: "Manage project tasks and status workflows in Asana.",
    requirements: ["Asana personal access token"],
    prompts: ["Create Asana tasks from this plan.", "Summarize overdue tasks."],
  },
  {
    id: "paypal",
    name: "PayPal for Business",
    logo: "PP",
    icon: "account_balance_wallet",
    tone: "blue",
    type: "api-key",
    authUrl: "https://developer.paypal.com/dashboard/",
    envKeys: ["PAYPAL_CLIENT_ID", "PAYPAL_CLIENT_SECRET"],
    keyMode: "all",
    description: "Manage transactions, invoices, and business operations.",
    requirements: ["PayPal client ID and secret"],
    prompts: ["Summarize recent payments.", "Create an invoice checklist."],
  },
  {
    id: "webflow",
    name: "Webflow",
    logo: "WF",
    icon: "web_asset",
    tone: "blue",
    type: "api-key",
    authUrl: "https://webflow.com/dashboard/account/apps",
    envKeys: ["WEBFLOW_API_TOKEN"],
    description: "Manage Webflow sites, pages, and CMS content.",
    requirements: ["Webflow API token"],
    prompts: ["Draft CMS updates for Webflow.", "Audit page metadata."],
  },
  {
    id: "zoho",
    name: "Zoho",
    logo: "ZO",
    icon: "apps",
    tone: "orange",
    type: "oauth",
    authUrl: "https://accounts.zoho.com/signin",
    description: "Open Zoho for CRM, Books, Desk, and other workspace flows.",
    requirements: ["Zoho account permission"],
    prompts: ["Create a CRM follow-up.", "Summarize Zoho Desk tickets."],
  },
  {
    id: "context7",
    name: "Context7",
    logo: "C7",
    icon: "menu_book",
    tone: "green",
    type: "mcp",
    description: "Access current library-specific technical docs through an MCP server.",
    requirements: ["Configured Context7 MCP server"],
    prompts: ["Fetch current React docs for this API.", "Use Context7 examples for this package."],
  },
  {
    id: "linear",
    name: "Linear",
    logo: "LI",
    icon: "track_changes",
    tone: "violet",
    type: "api-key",
    authUrl: "https://linear.app/settings/api",
    envKeys: ["LINEAR_API_KEY"],
    description: "Track issues, manage projects, and organize workflows.",
    requirements: ["Linear API key"],
    prompts: ["Create a Linear issue from this bug.", "Summarize active sprint blockers."],
  },
  {
    id: "fireflies",
    name: "Fireflies",
    logo: "FF",
    icon: "record_voice_over",
    tone: "pink",
    type: "api-key",
    authUrl: "https://app.fireflies.ai/settings/api",
    envKeys: ["FIREFLIES_API_KEY"],
    description: "Automate meeting transcription and conversation insights.",
    requirements: ["Fireflies API key"],
    prompts: ["Summarize this meeting.", "Find decisions from recent calls."],
  },
  {
    id: "neon",
    name: "Neon",
    logo: "NE",
    icon: "database",
    tone: "green",
    type: "api-key",
    authUrl: "https://console.neon.tech/app/settings/api-keys",
    envKeys: ["NEON_API_KEY"],
    description: "Query and manage serverless Postgres projects.",
    requirements: ["Neon API key"],
    prompts: ["Inspect Neon branches.", "Create a Postgres migration summary."],
  },
  {
    id: "box",
    name: "Box",
    logo: "BX",
    icon: "inventory_2",
    tone: "blue",
    type: "oauth",
    authUrl: "https://account.box.com/login",
    description: "Open Box sign-in for document preview and file workflows.",
    requirements: ["Box account permission"],
    prompts: ["Find the latest contract in Box.", "Extract structured data from documents."],
  },
  {
    id: "mercury",
    name: "Mercury",
    logo: "ME",
    icon: "account_balance",
    tone: "mono",
    type: "api-key",
    authUrl: "https://mercury.com/",
    envKeys: ["MERCURY_API_TOKEN"],
    description: "Access online banking workflows for business finance operations.",
    requirements: ["Mercury API token if available for your account"],
    prompts: ["Summarize recent transactions.", "Prepare a cash-flow note."],
  },
  {
    id: "xero",
    name: "Xero",
    logo: "XE",
    icon: "receipt_long",
    tone: "blue",
    type: "oauth",
    authUrl: "https://login.xero.com/",
    description: "Open Xero for financial data, reports, and business insights.",
    requirements: ["Xero account permission"],
    prompts: ["Summarize invoices this month.", "Find unpaid bills."],
  },
  {
    id: "firecrawl",
    name: "Firecrawl",
    logo: "FC",
    icon: "local_fire_department",
    tone: "orange",
    type: "api-key",
    authUrl: "https://www.firecrawl.dev/app/api-keys",
    envKeys: ["FIRECRAWL_API_KEY"],
    description: "Use Firecrawl v2 for fast web search, scrape, crawl, map, batch scrape, and action-based page extraction.",
    requirements: ["Firecrawl API key", "Optional FIRECRAWL_API_URL or FIRECRAWL_BASE_URL for self-hosted Firecrawl"],
    prompts: ["Search the web with Firecrawl and cite source URLs.", "Crawl this site and summarize key pages.", "Extract structured data from this URL."],
  },
  {
    id: "jotform",
    name: "Jotform",
    logo: "JF",
    icon: "dynamic_form",
    tone: "orange",
    type: "api-key",
    authUrl: "https://www.jotform.com/myaccount/api",
    envKeys: ["JOTFORM_API_KEY"],
    description: "Create, manage, and collect online form data.",
    requirements: ["Jotform API key"],
    prompts: ["Summarize recent form submissions.", "Create a form outline."],
  },
  {
    id: "posthog",
    name: "PostHog",
    logo: "PH",
    icon: "insights",
    tone: "mono",
    type: "api-key",
    authUrl: "https://app.posthog.com/settings/project-api-keys",
    envKeys: ["POSTHOG_PERSONAL_API_KEY"],
    description: "Perform product analytics, manage feature flags, and run experiments.",
    requirements: ["PostHog personal API key"],
    prompts: ["Analyze activation drop-off.", "Summarize feature flag performance."],
  },
  {
    id: "morningstar",
    name: "Morningstar",
    logo: "MS",
    icon: "show_chart",
    tone: "red",
    type: "api-key",
    authUrl: "https://developer.morningstar.com/",
    envKeys: ["MORNINGSTAR_API_KEY"],
    description: "Access investment data, research, and global securities analytics.",
    requirements: ["Morningstar API key"],
    prompts: ["Summarize fund performance.", "Compare securities by key metrics."],
  },
  {
    id: "minimax",
    name: "MiniMax",
    logo: "MM",
    icon: "multitrack_audio",
    tone: "red",
    type: "api-key",
    authUrl: "https://platform.minimaxi.com/",
    envKeys: ["MINIMAX_API_KEY"],
    description: "Generate speech, music, images, and videos with MiniMax.",
    requirements: ["MiniMax API key"],
    prompts: ["Generate a short voiceover.", "Create a video prompt."],
  },
  {
    id: "todoist",
    name: "Todoist",
    logo: "TD",
    icon: "checklist",
    tone: "red",
    type: "api-key",
    authUrl: "https://app.todoist.com/app/settings/integrations/developer",
    envKeys: ["TODOIST_API_TOKEN"],
    description: "Organize tasks, projects, and productivity workflows.",
    requirements: ["Todoist API token"],
    prompts: ["Create Todoist tasks from this plan.", "Find overdue tasks."],
  },
  {
    id: "sentry",
    name: "Sentry",
    logo: "SN",
    icon: "bug_report",
    tone: "mono",
    type: "api-key",
    authUrl: "https://sentry.io/settings/account/api/auth-tokens/",
    envKeys: ["SENTRY_AUTH_TOKEN"],
    description: "Review errors, analyze root causes, and triage production issues.",
    requirements: ["Sentry auth token"],
    prompts: ["Summarize new production errors.", "Find the likely root cause."],
  },
  {
    id: "clickup",
    name: "ClickUp",
    logo: "CU",
    icon: "task",
    tone: "canva",
    type: "api-key",
    authUrl: "https://app.clickup.com/settings/apps",
    envKeys: ["CLICKUP_API_TOKEN"],
    description: "Automate task management and project workflows.",
    requirements: ["ClickUp API token"],
    prompts: ["Create ClickUp tasks from this spec.", "Summarize project status."],
  },
  {
    id: "monday",
    name: "monday.com",
    logo: "MO",
    icon: "dashboard_customize",
    tone: "pink",
    type: "api-key",
    authUrl: "https://auth.monday.com/",
    envKeys: ["MONDAY_API_TOKEN"],
    description: "Coordinate tasks, boards, and project workflows.",
    requirements: ["monday.com API token"],
    prompts: ["Update a monday board item.", "Summarize board progress."],
  },
  {
    id: "granola",
    name: "Granola",
    logo: "GR",
    icon: "edit_note",
    tone: "yellow",
    type: "oauth",
    authUrl: "https://app.granola.ai/",
    description: "Open Granola for meeting notes and transcript workflows.",
    requirements: ["Granola account permission"],
    prompts: ["Summarize meeting notes.", "Extract action items from a transcript."],
  },
  {
    id: "resend",
    name: "Resend",
    logo: "RS",
    icon: "outgoing_mail",
    tone: "mono",
    type: "api-key",
    authUrl: "https://resend.com/api-keys",
    envKeys: ["RESEND_API_KEY"],
    description: "Send emails, manage contacts, broadcasts, and domains.",
    requirements: ["Resend API key"],
    prompts: ["Send a transactional email.", "Draft a broadcast campaign."],
  },
  {
    id: "apify",
    name: "Apify",
    logo: "AP",
    icon: "explore",
    tone: "orange",
    type: "api-key",
    authUrl: "https://console.apify.com/account/integrations",
    envKeys: ["APIFY_TOKEN"],
    description: "Discover and run Apify Actors for scraping and automation.",
    requirements: ["Apify API token"],
    prompts: ["Run an Apify actor for this URL.", "Extract leads from this source."],
  },
  {
    id: "cal",
    name: "Cal.com",
    logo: "CA",
    icon: "event_available",
    tone: "mono",
    type: "api-key",
    authUrl: "https://app.cal.com/settings/developer/api-keys",
    envKeys: ["CALCOM_API_KEY"],
    description: "Schedule, reschedule, and manage bookings and event types.",
    requirements: ["Cal.com API key"],
    prompts: ["Create a booking link.", "Check availability for next week."],
  },
  {
    id: "superhuman",
    name: "Superhuman Mail",
    logo: "SH",
    icon: "mail_lock",
    tone: "blue",
    type: "oauth",
    authUrl: "https://mail.superhuman.com/",
    description: "Open Superhuman Mail for search, drafts, and calendar workflows.",
    requirements: ["Superhuman account permission"],
    prompts: ["Draft a fast email reply.", "Find the latest thread from this contact."],
  },
  {
    id: "scite",
    name: "Scite",
    logo: "SC",
    icon: "science",
    tone: "blue",
    type: "api-key",
    authUrl: "https://scite.ai/",
    envKeys: ["SCITE_API_KEY"],
    description: "Ground answers in peer-reviewed research and Smart Citations.",
    requirements: ["Scite API key if available"],
    prompts: ["Find papers supporting this claim.", "Summarize citation context."],
  },
  {
    id: "consensus",
    name: "Consensus",
    logo: "CS",
    icon: "school",
    tone: "green",
    type: "oauth",
    authUrl: "https://consensus.app/",
    description: "Search academic research and summarize evidence.",
    requirements: ["Consensus account permission"],
    prompts: ["Find consensus on this research question.", "Summarize the strongest evidence."],
  },
  {
    id: "panda-doc",
    name: "PandaDoc",
    logo: "PD",
    icon: "contract",
    tone: "green",
    type: "api-key",
    authUrl: "https://app.pandadoc.com/a/#/settings/integrations/api",
    envKeys: ["PANDADOC_API_KEY"],
    description: "Create, send, and eSign documents directly from PandaDoc.",
    requirements: ["PandaDoc API key"],
    prompts: ["Create a proposal from this outline.", "Summarize document status."],
  },
  {
    id: "lumin-pdf",
    name: "Lumin PDF",
    logo: "LP",
    icon: "picture_as_pdf",
    tone: "red",
    type: "oauth",
    authUrl: "https://www.luminpdf.com/login",
    description: "Manage PDFs, signature requests, and workspaces.",
    requirements: ["Lumin account permission"],
    prompts: ["Review this PDF for missing fields.", "Prepare a signature request."],
  },
  {
    id: "mem",
    name: "Mem",
    logo: "ME",
    icon: "notes",
    tone: "orange",
    type: "oauth",
    authUrl: "https://mem.ai/login",
    description: "Search, create, and organize notes and collections.",
    requirements: ["Mem account permission"],
    prompts: ["Save this summary as a note.", "Find notes about this client."],
  },
  {
    id: "motherduck",
    name: "MotherDuck",
    logo: "MD",
    icon: "database",
    tone: "orange",
    type: "api-key",
    authUrl: "https://app.motherduck.com/",
    envKeys: ["MOTHERDUCK_TOKEN"],
    description: "Query data warehouses and build interactive analytics.",
    requirements: ["MotherDuck token"],
    prompts: ["Run an analytics query.", "Summarize warehouse tables."],
  },
  {
    id: "guru",
    name: "Guru",
    logo: "GU",
    icon: "workspace_premium",
    tone: "mono",
    type: "api-key",
    authUrl: "https://app.getguru.com/",
    envKeys: ["GURU_API_KEY"],
    description: "Search, ask, and update Guru knowledge bases.",
    requirements: ["Guru API credentials"],
    prompts: ["Find the current policy in Guru.", "Create a Guru card from this answer."],
  },
  {
    id: "hex",
    name: "Hex",
    logo: "HX",
    icon: "table_chart",
    tone: "violet",
    type: "api-key",
    authUrl: "https://app.hex.tech/",
    envKeys: ["HEX_API_TOKEN"],
    description: "Search Hex projects and ask data questions.",
    requirements: ["Hex API token"],
    prompts: ["Find a Hex notebook for revenue.", "Explain this chart."],
  },
  {
    id: "pop-hive",
    name: "PopHIVE",
    logo: "PH",
    icon: "health_and_safety",
    tone: "mono",
    type: "oauth",
    authUrl: "https://www.pophive.org/",
    description: "Access public health dashboards and data sources.",
    requirements: ["PopHIVE account or public dashboard access"],
    prompts: ["Summarize public health indicators.", "Find trends in this dashboard."],
  },
];

const CONNECTOR_ICON_DOMAINS = {
  "my-browser": "google.com/chrome",
  gmail: "mail.google.com",
  github: "github.com",
  "google-drive": "drive.google.com",
  "google-calendar": "calendar.google.com",
  instagram: "instagram.com",
  "meta-ads": "business.facebook.com",
  notion: "notion.so",
  "outlook-mail": "outlook.live.com",
  whatsapp: "whatsapp.com",
  telegram: "telegram.org",
  email: "gmail.com",
  codex: "openai.com",
  similarweb: "similarweb.com",
  dify: "dify.ai",
  ahrefs: "ahrefs.com",
  canva: "canva.com",
  supabase: "supabase.com",
  vercel: "vercel.com",
  zapier: "zapier.com",
  "prisma-postgres": "prisma.io",
  heygen: "heygen.com",
  slack: "slack.com",
  cloudflare: "cloudflare.com",
  metabase: "metabase.com",
  stripe: "stripe.com",
  make: "make.com",
  "crypto-com": "crypto.com",
  "hugging-face": "huggingface.co",
  airtable: "airtable.com",
  coingecko: "coingecko.com",
  line: "line.me",
  elevenlabs: "elevenlabs.io",
  playwright: "playwright.dev",
  tldv: "tldv.io",
  wix: "wix.com",
  serena: "github.com/oraios/serena",
  asana: "asana.com",
  paypal: "paypal.com",
  webflow: "webflow.com",
  zoho: "zoho.com",
  context7: "context7.com",
  linear: "linear.app",
  fireflies: "fireflies.ai",
  neon: "neon.tech",
  box: "box.com",
  mercury: "mercury.com",
  xero: "xero.com",
  firecrawl: "firecrawl.dev",
  jotform: "jotform.com",
  posthog: "posthog.com",
  morningstar: "morningstar.com",
  minimax: "minimax.io",
  todoist: "todoist.com",
  sentry: "sentry.io",
  clickup: "clickup.com",
  monday: "monday.com",
  granola: "granola.ai",
  resend: "resend.com",
  apify: "apify.com",
  cal: "cal.com",
  superhuman: "superhuman.com",
  scite: "scite.ai",
  consensus: "consensus.app",
  "panda-doc": "pandadoc.com",
  "lumin-pdf": "luminpdf.com",
  mem: "mem.ai",
  motherduck: "motherduck.com",
  guru: "getguru.com",
  hex: "hex.tech",
  "pop-hive": "pophive.org",
};

const MCP_PRESET_CONNECTORS = new Set(["gmail", "google-drive", "google-calendar"]);
const GOOGLE_WORKSPACE_EMAIL_STORAGE_KEY = "vini.googleWorkspaceEmail";

function normalizeQuery(value) {
  return String(value || "").trim().toLowerCase();
}

function urlFromConnectorDomain(domain = "") {
  const value = String(domain || "").trim();
  if (!value) return "";
  return /^https?:\/\//i.test(value) ? value : `https://${value}`;
}

function domainFromAuthUrl(url = "") {
  try {
    return new URL(url).hostname;
  } catch {
    return "";
  }
}

function hostFromUrl(url = "") {
  try {
    return new URL(url).hostname || url;
  } catch {
    return url;
  }
}

function connectorIconSource(connector, size = 96) {
  if (!connector?.id) return "";
  const domain = connector.iconDomain || CONNECTOR_ICON_DOMAINS[connector.id] || domainFromAuthUrl(connector.authUrl);
  const iconUrl = urlFromConnectorDomain(domain);
  if (!iconUrl) return "";
  return `https://www.google.com/s2/favicons?domain_url=${encodeURIComponent(iconUrl)}&sz=${Number(size) || 96}`;
}

function envNameFrom(value) {
  return String(value || "CUSTOM_API")
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 48) || "CUSTOM_API";
}

function parseEnvKeys(text = "") {
  const keys = new Set();
  for (const line of String(text || "").split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const match = trimmed.match(/^([A-Za-z_][A-Za-z0-9_]*)\s*=/);
    if (match) keys.add(match[1]);
  }
  return keys;
}

function upsertEnvValue(text = "", key, value) {
  const lines = String(text || "").split(/\r?\n/);
  let updated = false;
  const next = lines.map((line) => {
    const match = line.match(/^([A-Za-z_][A-Za-z0-9_]*)\s*=/);
    if (match?.[1] === key) {
      updated = true;
      return `${key}=${value}`;
    }
    return line;
  });
  if (!updated) {
    if (next.length && next[next.length - 1].trim()) next.push("");
    next.push(`${key}=${value}`);
  }
  return next.join("\n").replace(/\n{3,}/g, "\n\n");
}

const model = {
  connectors: CONNECTORS,
  search: "",
  tab: "apps",
  selectedId: "my-browser",
  apiKeyValue: "",
  apiSecretValue: "",
  customApiName: "",
  customApiBaseUrl: "",
  customApiHeader: "Authorization",
  customApiKey: "",
  statusMessage: "",
  statusTone: "info",
  secretKeys: new Set(),
  connectorStatuses: {},
  loadingSecrets: false,
  loadingConnectorStatuses: false,
  enablingMcpConnector: false,
  savingKey: false,

  async onOpen() {
    this.statusMessage = "";
    this.apiKeyValue = "";
    this.apiSecretValue = "";
    await Promise.all([this.refreshSecretPresence(), this.refreshConnectorStatuses()]);
  },

  get selectedConnector() {
    return this.connectors.find((item) => item.id === this.selectedId) || this.filteredConnectors[0] || this.connectors[0];
  },

  get filteredConnectors() {
    const query = normalizeQuery(this.search);
    if (!query) return this.connectors;
    return this.connectors.filter((item) => {
      const haystack = `${item.name} ${item.description} ${(item.envKeys || []).join(" ")} ${item.type}`.toLowerCase();
      return haystack.includes(query);
    });
  },

  get apiKeyConnectors() {
    return this.connectors.filter((item) => item.type === "api-key");
  },

  get mcpConnectors() {
    return this.connectors.filter((item) => item.type === "mcp");
  },

  connectorIconSource(connector, size = 96) {
    return connectorIconSource(connector, size);
  },

  connectorButtonIcon(connector) {
    const status = this.connectorBackendStatus(connector);
    if (status?.status === "verified") return "check";
    if (status?.status === "configured") return "vpn_key";
    if (this.hasMcpPreset(connector)) return "settings_ethernet";
    if (connector.type === "plugin") return "tune";
    if (connector.type === "built-in") return "open_in_new";
    if (connector.type === "mcp") return "settings_ethernet";
    if (connector.type === "api-key") return "add";
    return "open_in_new";
  },

  connectorActionLabel(connector = this.selectedConnector) {
    if (!connector) return "Connect";
    if (connector.type === "plugin") return "Open setup";
    if (connector.type === "built-in") return "Open";
    if (this.hasMcpPreset(connector)) {
      const status = this.connectorBackendStatus(connector);
      if (this.needsGoogleWorkspaceAuth(connector, status)) return "Start Google sign-in";
      if (status?.status === "verified" || status?.status === "configured") return "Refresh Workspace MCP";
      return "Enable Workspace MCP";
    }
    if (connector.type === "mcp") {
      const status = this.connectorBackendStatus(connector);
      if (status?.status === "verified" || status?.status === "configured") return "Refresh MCP";
      return "Enable MCP";
    }
    if (connector.type === "api-key") return this.hasConnectorCredentials(connector) ? "Update key" : "Add API key";
    return "Open in system browser";
  },

  connectorStatus(connector = this.selectedConnector) {
    if (!connector) return "Not configured";
    const status = this.connectorBackendStatus(connector);
    if (status?.label) return status.label;
    if (this.isConnectorConfigured(connector)) return "Configured";
    if (connector.type === "plugin") return "Built-in setup";
    if (connector.type === "built-in") return "Available";
    if (connector.type === "mcp") return "MCP setup needed";
    if (connector.type === "api-key") return "API key needed";
    return "Sign-in needed";
  },

  connectorStatusClass(connector) {
    const status = this.connectorBackendStatus(connector);
    if (status?.status === "verified") return "is-ready";
    if (status?.status === "configured" || status?.status === "browser_session_only" || status?.label === "Browser session only") return "is-available";
    if (this.isConnectorConfigured(connector)) return "is-ready";
    if (connector?.type === "built-in" || connector?.type === "plugin") return "is-available";
    return "is-needed";
  },

  isConnectorConfigured(connector) {
    const status = this.connectorBackendStatus(connector);
    if (status?.status === "verified") return true;
    return false;
  },

  hasConnectorCredentials(connector) {
    const status = this.connectorBackendStatus(connector);
    if (status?.status === "configured" || status?.status === "verified") return true;
    if (!connector) return false;
    if (connector.type === "built-in") return true;
    if (connector.type === "plugin") return false;
    if (connector.type !== "api-key" || !connector.envKeys?.length) return false;
    const hasKey = (key) => this.secretKeys.has(key);
    return connector.keyMode === "all"
      ? connector.envKeys.every(hasKey)
      : connector.envKeys.some(hasKey);
  },

  connectorBackendStatus(connector) {
    if (!connector?.id) return null;
    return this.connectorStatuses?.[connector.id] || null;
  },

  hasMcpPreset(connector) {
    return MCP_PRESET_CONNECTORS.has(connector?.id);
  },

  needsGoogleWorkspaceAuth(connector, status = this.connectorBackendStatus(connector)) {
    return this.hasMcpPreset(connector) && status?.label === "OAuth sign-in needed";
  },

  selectConnector(connector) {
    if (!connector?.id) return;
    this.selectedId = connector.id;
    this.statusMessage = "";
    this.apiKeyValue = "";
    this.apiSecretValue = "";
  },

  async connect(connector = this.selectedConnector) {
    if (!connector) return;
    this.selectConnector(connector);
    if (connector.pluginName) {
      await this.openPluginConfig(connector.pluginName);
      return;
    }
    if (connector.surfaceId) {
      await this.openSurface(connector.surfaceId);
      return;
    }
    if (this.hasMcpPreset(connector)) {
      const status = this.connectorBackendStatus(connector);
      if (this.needsGoogleWorkspaceAuth(connector, status)) {
        await this.startGoogleWorkspaceAuth(connector);
        return;
      }
      await this.enableMcpConnector(connector);
      return;
    }
    if (connector.type === "mcp") {
      await this.enableMcpConnector(connector);
      return;
    }
    if (connector.type === "api-key") {
      this.statusMessage = `${connector.name} needs ${this.keyLabel(connector)}. Paste it below or open the official key page.`;
      this.statusTone = "info";
      return;
    }
    if (connector.authUrl) {
      await this.openOAuthSignIn(connector);
    }
  },

  async openOAuthSignIn(connector) {
    const url = String(connector?.authUrl || "").trim();
    if (!url) return;
    this.statusMessage = `Opening ${connector.name} sign-in in your Windows browser.`;
    this.statusTone = "info";
    try {
      await this.openExternal(url);
      this.statusMessage = `Opened ${connector.name} sign-in in your Windows browser (${hostFromUrl(url)}). Finish permission there; Vini AI will not mark it connected until a real OAuth token, API key, or service session exists.`;
      this.statusTone = "info";
      await this.refreshConnectorStatuses();
    } catch (error) {
      this.statusMessage = error?.message || `Could not open ${connector.name} sign-in in your Windows browser.`;
      this.statusTone = "error";
    }
  },

  async openPluginConfig(pluginName) {
    const pluginStore = globalThis.Alpine?.store?.("pluginSettingsPrototype");
    if (!pluginStore?.openConfig) {
      this.statusMessage = "Plugin settings are unavailable in this runtime.";
      this.statusTone = "error";
      return;
    }
    try {
      await pluginStore.openConfig(pluginName);
    } catch (error) {
      this.statusMessage = error?.message || "Could not open plugin setup.";
      this.statusTone = "error";
    }
  },

  async openSurface(surfaceId) {
    const surfaceStore = globalThis.Alpine?.store?.("rightCanvas");
    if (!surfaceStore?.open) {
      this.statusMessage = "Vini AI Computer is unavailable in this runtime.";
      this.statusTone = "error";
      return;
    }
    const opened = await surfaceStore.open(surfaceId);
    this.statusMessage = opened
      ? "Opened Vini AI Computer with the requested surface."
      : "Could not open this surface. Check the Vini AI Computer runtime.";
    this.statusTone = opened ? "success" : "error";
  },

  async openMcpSettings() {
    try {
      history.replaceState(null, "", "#section-mcp-client");
    } catch {}
    await globalThis.openModal?.("settings/settings.html");
  },

  async enableMcpConnector(connector = this.selectedConnector) {
    if (!connector?.id) return;
    this.enablingMcpConnector = true;
    this.statusMessage = `Checking ${connector.name} MCP preset and runtime dependencies.`;
    this.statusTone = "info";
    try {
      const status = this.connectorBackendStatus(connector);
      const operation = status?.status === "verified" || status?.status === "configured" ? "refresh" : "enable";
      const response = await API.callJsonApi("/plugins/_connectors/mcp_preset", {
        connector_id: connector.id,
        operation,
        force: true,
      });
      await this.refreshConnectorStatuses();
      const next = this.connectorBackendStatus(connector) || response?.connector;
      if (response?.ok && next?.status === "verified") {
        this.statusMessage = `${connector.name} MCP is ready for agent actions. ${next.message || ""}`.trim();
        this.statusTone = "success";
        return;
      }
      if (response?.ok) {
        this.statusMessage = response.message || `${connector.name} MCP settings were refreshed.`;
        this.statusTone = next?.status === "expired" ? "error" : "info";
        return;
      }
      this.statusMessage = response?.message || `${connector.name} MCP could not be enabled.`;
      this.statusTone = "error";
      if (response?.status === "unsupported_action") {
        await this.openMcpSettings();
      }
    } catch (error) {
      this.statusMessage = error?.message || `Could not enable ${connector.name} MCP.`;
      this.statusTone = "error";
    } finally {
      this.enablingMcpConnector = false;
    }
  },

  googleWorkspaceServiceName(connector) {
    if (connector?.id === "google-drive") return "Drive";
    if (connector?.id === "google-calendar") return "Calendar";
    return "Gmail";
  },

  googleWorkspaceStoredEmail(connector) {
    const users = this.connectorBackendStatus(connector)?.details?.google_credentials?.stored_users;
    if (Array.isArray(users) && users[0]) return String(users[0]);
    try {
      return String(globalThis.localStorage?.getItem(GOOGLE_WORKSPACE_EMAIL_STORAGE_KEY) || "");
    } catch {
      return "";
    }
  },

  askGoogleWorkspaceEmail(connector) {
    const existing = this.googleWorkspaceStoredEmail(connector);
    const value = globalThis.prompt?.(`Google email for ${this.googleWorkspaceServiceName(connector)} OAuth`, existing) || "";
    const email = value.trim();
    if (email) {
      try {
        globalThis.localStorage?.setItem(GOOGLE_WORKSPACE_EMAIL_STORAGE_KEY, email);
      } catch {}
    }
    return email;
  },

  async startGoogleWorkspaceAuth(connector = this.selectedConnector) {
    if (!connector?.id) return;
    const userGoogleEmail = this.askGoogleWorkspaceEmail(connector);
    if (!userGoogleEmail) {
      this.statusMessage = "Google OAuth needs the Google account email before Vini AI can open consent.";
      this.statusTone = "error";
      return;
    }
    this.enablingMcpConnector = true;
    this.statusMessage = `Starting ${connector.name} Google OAuth in your Windows browser.`;
    this.statusTone = "info";
    try {
      const response = await API.callJsonApi("/plugins/_connectors/mcp_preset", {
        connector_id: connector.id,
        operation: "start_auth",
        user_google_email: userGoogleEmail,
        force: true,
      });
      const authUrl = String(response?.auth_url || "").trim();
      if (authUrl) {
        await this.openExternal(authUrl);
        this.statusMessage = `Opened Google OAuth for ${connector.name} in your Windows browser. Complete consent there, then refresh this connector.`;
        this.statusTone = "info";
        await this.refreshConnectorStatuses();
        return;
      }
      this.statusMessage = response?.message || `Google OAuth did not return a sign-in URL for ${connector.name}.`;
      this.statusTone = response?.ok ? "info" : "error";
      await this.refreshConnectorStatuses();
    } catch (error) {
      this.statusMessage = error?.message || `Could not start Google OAuth for ${connector.name}.`;
      this.statusTone = "error";
    } finally {
      this.enablingMcpConnector = false;
    }
  },

  async openExternal(url) {
    if (!url) return;
    if (globalThis.vini?.app?.openExternal) {
      await globalThis.vini.app.openExternal(url);
      return;
    }
    globalThis.open(url, "_blank", "noopener,noreferrer");
  },

  keyLabel(connector = this.selectedConnector) {
    return (connector?.envKeys || []).join(" and ") || "an API key";
  },

  async refreshSecretPresence() {
    this.loadingSecrets = true;
    try {
      const response = await API.callJsonApi("settings_get", null);
      const settings = response?.settings || {};
      this.secretKeys = new Set([
        ...parseEnvKeys(settings.secrets),
        ...parseEnvKeys(settings.variables),
      ]);
    } catch (error) {
      console.warn("Failed to load connector secret status", error);
    } finally {
      this.loadingSecrets = false;
    }
  },

  async refreshConnectorStatuses() {
    this.loadingConnectorStatuses = true;
    try {
      const response = await API.callJsonApi("/plugins/_connectors/status", {});
      const statuses = {};
      for (const item of response?.connectors || []) {
        if (item?.id) statuses[item.id] = item;
      }
      this.connectorStatuses = statuses;
    } catch (error) {
      console.warn("Failed to load connector registry status", error);
      this.connectorStatuses = {};
    } finally {
      this.loadingConnectorStatuses = false;
    }
  },

  async saveApiKey() {
    const connector = this.selectedConnector;
    if (!connector?.envKeys?.length) return;
    const firstKey = connector.envKeys[0];
    const secondKey = connector.envKeys[1];
    if (!this.apiKeyValue.trim()) {
      this.statusMessage = `Paste ${firstKey} before saving.`;
      this.statusTone = "error";
      return;
    }
    if (connector.keyMode === "all" && secondKey && !this.apiSecretValue.trim()) {
      this.statusMessage = `Paste ${secondKey} before saving.`;
      this.statusTone = "error";
      return;
    }
    this.savingKey = true;
    try {
      const response = await API.callJsonApi("settings_get", null);
      const settings = response?.settings || {};
      settings.secrets = upsertEnvValue(settings.secrets || "", firstKey, this.apiKeyValue.trim());
      if (connector.keyMode === "all" && secondKey) {
        settings.secrets = upsertEnvValue(settings.secrets || "", secondKey, this.apiSecretValue.trim());
      }
      const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || "auto";
      await API.callJsonApi("settings_set", { settings, browser_timezone: timezone });
      this.secretKeys.add(firstKey);
      if (connector.keyMode === "all" && secondKey) this.secretKeys.add(secondKey);
      this.apiKeyValue = "";
      this.apiSecretValue = "";
      await this.refreshConnectorStatuses();
      this.statusMessage = `${connector.name} credential saved to Vini AI secrets. Vini AI will mark it verified only after a real service-specific check succeeds.`;
      this.statusTone = "success";
    } catch (error) {
      this.statusMessage = error?.message || "Failed to save API key.";
      this.statusTone = "error";
    } finally {
      this.savingKey = false;
    }
  },

  async saveCustomApi() {
    const name = this.customApiName.trim();
    const baseUrl = this.customApiBaseUrl.trim();
    const key = this.customApiKey.trim();
    if (!name || !baseUrl || !key) {
      this.statusMessage = "Custom API needs a name, base URL, and API key.";
      this.statusTone = "error";
      return;
    }
    const prefix = envNameFrom(name);
    try {
      const response = await API.callJsonApi("settings_get", null);
      const settings = response?.settings || {};
      settings.variables = upsertEnvValue(settings.variables || "", `${prefix}_BASE_URL`, baseUrl);
      settings.variables = upsertEnvValue(settings.variables || "", `${prefix}_AUTH_HEADER`, this.customApiHeader.trim() || "Authorization");
      settings.secrets = upsertEnvValue(settings.secrets || "", `${prefix}_API_KEY`, key);
      const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || "auto";
      await API.callJsonApi("settings_set", { settings, browser_timezone: timezone });
      this.secretKeys.add(`${prefix}_API_KEY`);
      this.customApiKey = "";
      await this.refreshConnectorStatuses();
      this.statusMessage = `Saved ${prefix}_BASE_URL, ${prefix}_AUTH_HEADER, and ${prefix}_API_KEY to Vini AI settings.`;
      this.statusTone = "success";
    } catch (error) {
      this.statusMessage = error?.message || "Failed to save custom API settings.";
      this.statusTone = "error";
    }
  },
};

export const store = createStore("connectorsStore", model);
