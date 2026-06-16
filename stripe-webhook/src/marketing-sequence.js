// Marketing Sequence — 9 emails, one per week starting at Day 12 (week after signup flow ends)
// Order: prewarmed (1-3) → whitelabel (1-3) → bestpractices (1-3)
// Sender: Timothy <tim@icemail.ai>
export const MARKETING_SEQUENCE = [
  {
    id: "prewarmed-01",
    week: 2,
    day: 12,
    subject: "your mailboxes came pre-warmed — here's what that actually means",
    text: `Hey {{firstName}},

Every mailbox you provision through icemail ships with warmup already done. Not a warmup tool running in the background — actual two-way email traffic that's been running through your inboxes before you touched them.

Why this matters: Google and Microsoft treat new mailboxes the way banks treat new customers. No history, no trust. Start sending 30 cold emails on day one and the filters have no context for it — so they flag the pattern. Pre-warming builds that sending history in advance, so by the time you import a mailbox into Instantly or Smartlead, it already looks like a normal active mailbox to the filter.

What this means practically for your setup:

— You can start real sends sooner than you could from a fresh mailbox
— Your ramp period is shorter because the baseline reputation is already there
— You're less likely to hit early flags that burn a domain in the first two weeks

You don't need to configure anything extra. Every mailbox ships warmed. Just keep Day 1 sends conservative — under 20 per mailbox — and ramp from there.

If you want to see exactly where your mailboxes stand before you start, reply and I'll pull the warmup stats for your account.

Timothy
Founder, icemail.ai

P.S. This was sent through a third-party tool, not our own infra. The cobbler's children, etc.`,
  },
  {
    id: "prewarmed-02",
    week: 3,
    day: 19,
    subject: "the warmup mistake that wastes your head start",
    text: `Hey {{firstName}},

One thing I see happen a lot with pre-warmed mailboxes: someone imports them into Instantly, sees they're already warmed, and immediately sets volume to 40 sends per mailbox per day. The warmup history is there, so it should be fine — right?

Not quite. Warmup builds reputation, but reputation isn't a score you spend down — it's a signal that stays healthy as long as your sending behaviour looks consistent. Jumping from 0 to 40 sends in one shot still looks like an anomaly, even on a mailbox with warmup history.

What actually holds up over time:

— Day 1–3: 10–15 real sends per mailbox per day
— Day 4–7: push to 20–25
— Week 2 onward: ramp toward your target, adding ~5/day
— Cap out around 30–40 max, not higher

One thing worth double-checking in Instantly or Smartlead: your campaign-level daily cap and your warmup tool cap are separate settings. The campaign cap is what actually controls how many real emails go out. A lot of people set the warmup limit correctly and miss the campaign cap entirely. Worth a look before you go live.

Reply if you want me to look at your ramp settings before you start sending.

Timothy
Founder, icemail.ai`,
  },
  {
    id: "prewarmed-03",
    week: 4,
    day: 26,
    subject: "two weeks in — worth checking these things",
    text: `Hey {{firstName}},

You've been live for a couple of weeks. A few things worth checking now that you have some data:

Open rates dropping?
Usually means the mailbox has drifted into Promotions or Spam. Run a quick test at mail-tester.com — it's free and will tell you exactly what's happening with your domain score and authentication. If your score dropped from when you first set up, the domain is the problem, not the copy.

Bounce rate above 3%?
Pause that mailbox before sending another batch. High bounces are the fastest way to burn a domain. Clean the list first — re-verify against Millionverifier or NeverBounce — then resume.

Reply rates flat despite decent open rates?
That's a copy issue, not infrastructure. But if multiple mailboxes on the same domain are underperforming simultaneously, check the domain's blacklist status. MXToolbox is a good free starting point.

If any of this matches what you're seeing, reply and tell me what the numbers look like. I'd rather help you course-correct at two weeks than have you burn domains you just set up.

Timothy
Founder, icemail.ai

P.S. If everything's running clean, ignore this. Good sending.`,
  },
  {
    id: "whitelabel-01",
    week: 5,
    day: 33,
    subject: "if you manage clients, there's a part of icemail you should know about",
    text: `Hey {{firstName}},

If you're running an agency, reselling outreach services, or managing cold email infrastructure for multiple clients — there's a setup inside icemail that's probably relevant to you.

It's called whitelabel. The short version: you provision and manage all your clients' mailboxes from one dashboard, under your own brand. Your clients see your platform, your logo, your domain name. icemail runs everything in the background and never shows up in the client-facing interface.

What this gives you practically:

— You control the client relationship, not a shared vendor they can go shop around
— You set your own pricing and margin on mailboxes
— When a client offboards, the mailboxes stay under your account
— You manage all clients from one view, not separate logins

A few agencies use this to offer mailbox provisioning as a standalone service line. Others just use it to keep their stack clean and not expose vendor relationships to clients. Either way, it's on the plan you're already on — no upgrade needed.

If this sounds like something you'd use, reply and I'll walk you through how other agencies have set it up.

Timothy
Founder, icemail.ai`,
  },
  {
    id: "whitelabel-02",
    week: 6,
    day: 40,
    subject: "what to say when a client asks what you're using",
    text: `Hey {{firstName}},

One question I get from agencies on the whitelabel setup: what do I tell clients if they ask what tool I'm using?

Honest answer: most clients don't ask. They care about two things — do the mailboxes land in Primary, and how fast can you get them set up. If both of those are clean, the infrastructure conversation never comes up.

But for the ones who do ask: you're an official Google Workspace and Microsoft 365 reseller. That's completely accurate — icemail is a reseller, and so are you by extension when you're operating through the whitelabel setup. That's the answer most clients need.

If a technical client pushes further, walk them through the authentication stack — DKIM, SPF, DMARC pre-configured on every mailbox. The admin panel is under your brand. It is your offering. You're the one provisioning it, managing it, and responsible for it.

The whitelabel isn't about hiding things. It's about owning the client relationship instead of building your agency on top of a vendor name your clients can type directly into Google.

If you want help setting up the client-facing side — custom domain, branded confirmation emails, client subdomain — reply and I'll help you configure it.

Timothy
Founder, icemail.ai`,
  },
  {
    id: "whitelabel-03",
    week: 7,
    day: 47,
    subject: "what agencies actually see when they move to whitelabel",
    text: `Hey {{firstName}},

Last one on this topic — wanted to share what the whitelabel setup actually looks like in practice for agencies that have moved over.

Setup time per client dropped significantly. Most of the time that used to go into onboarding a new client was DNS coordination, waiting for propagation, chasing someone to log into a domain registrar. icemail handles all of that automatically. Most agencies are now fully provisioning a new client in under 30 minutes.

Mailbox cost per month came down for most of them. Partly our pricing, partly because they stopped paying for inactive seats. When a client pauses a campaign, they're not sitting on a fixed subscription — they just stop provisioning mailboxes for that period.

The one that surprised a few people: client retention on the mailbox side went up. When the infrastructure is under your brand, the switching cost for the client goes up — they're on your platform, not a shared vendor they can go replicate directly.

If you're managing 5 or more clients with active cold email campaigns, reply with how many clients you're running and I can put together a rough comparison of what the numbers look like for your setup.

Timothy
Founder, icemail.ai

P.S. If the whitelabel isn't relevant to your setup, ignore this thread entirely. Not every feature is for every use case.`,
  },
  {
    id: "bestpractices-01",
    week: 8,
    day: 54,
    subject: "the part of cold email most people already know and still get wrong",
    text: `Hey {{firstName}},

Good infrastructure gets you to the inbox. What you send from there is what determines whether you stay.

Plain text over HTML.
Every time, for cold email. HTML emails with tracking pixels, unsubscribe footers, and styled buttons look like marketing software to spam filters — because they are. A plain text email from an unknown sender looks like a human sent it. That distinction matters a lot to filters.

One link max, if you need one at all.
Multiple links signal promotional intent. On a first touch, you almost certainly don't need a link. The goal of email one is to get a reply, not a click. Save the link for the follow-up.

Under 150 words for first touches.
Long emails from unknown senders don't get read — they get archived. Write like you're texting someone who's busy, not drafting a proposal.

A first line that's actually specific.
Not "I saw your LinkedIn" — that's been wallpaper for two years. Something that shows you looked at the company: a recent hire, a product change, a job posting, a funding announcement. Generic personalisation signals automation to someone who's seen a thousand of these.

The problem isn't that people don't know this. It's that the sending tool defaults to HTML, the template has three links, and the first line is a merge field. Check all four of those before your next campaign goes live.

Timothy
Founder, icemail.ai`,
  },
  {
    id: "bestpractices-02",
    week: 9,
    day: 61,
    subject: "when reply rates drop mid-campaign — what to check first",
    text: `Hey {{firstName}},

Reply rates almost always drop mid-campaign. It happens to everyone. The question is whether it's a copy problem, an infrastructure problem, or a list problem — because the fix is completely different depending on which one it is.

How to tell:
Run mail-tester.com on your current sending domain. If your score dropped from when you first set up, the domain is the problem. If the score is still clean, the issue is copy or list quality.

If it's infrastructure:
Pull the mailbox off the campaign immediately. Continuing to send from a mailbox that's landing in spam accelerates the damage. Provision a fresh batch from icemail and rotate in. If multiple domains are drifting at the same time, check whether they were provisioned around the same date — sometimes it's a pattern Google catches across a cohort.

If it's copy:
Rotate subject lines. Open rates dropping usually means the subject got pattern-matched as promotional. Also check your send days — Tuesday and Wednesday mornings in the recipient's local timezone still meaningfully outperform Thursday afternoon and Friday.

If it's the list:
Lists age faster than most people expect. A list that was solid four months ago might have 15–20% more invalid addresses now, especially in high-turnover industries. Re-verify before blaming the email or the infrastructure.

Reply if any of this matches what you're seeing — happy to dig into it.

Timothy
Founder, icemail.ai`,
  },
  {
    id: "bestpractices-03",
    week: 10,
    day: 68,
    subject: "the infrastructure decision that costs the most when it goes wrong",
    text: `Hey {{firstName}},

Last thing I want to cover — and it's the one I see cause the most damage when people get it wrong.

Most people calculate infrastructure like this: I want to send 500 emails a day, I'll use 17 mailboxes at 30 sends each. The math is right. The risk model is wrong.

When you concentrate a lot of mailboxes on a small number of domains, you're putting all your sending capacity on a small number of reputations. If one domain takes a hit — a spam complaint spike, a blacklist entry, an algorithm flag — you don't lose one mailbox. You lose six or eight at once, because they all share that domain's reputation.

The model that holds up better over time:

— 2–3 mailboxes per domain, not 6–8
— 20–25 sends per mailbox per day, not 30–40
— More domains, spread across the volume
— Keep your main brand domain completely off cold sending

This way, when one domain takes a hit, you rotate it out, provision a replacement from icemail, and your overall sending capacity barely moves. Domains are cheap. Rebuilding your entire sending infrastructure is not.

If you want me to look at how your current setup is distributed, reply with how many domains and mailboxes you're running. Happy to give you a read on it.

Timothy
Founder, icemail.ai

P.S. That's the last email in this sequence. My email stays the same if you have questions at any point.`,
  },
];
