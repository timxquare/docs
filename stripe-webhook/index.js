import express from "express";
import Stripe from "stripe";
import { google } from "googleapis";

const app = express();
const stripe = new Stripe(process.env.STRIPE_SECRET_KEY);

const oauth2Client = new google.auth.OAuth2(
  process.env.GMAIL_CLIENT_ID,
  process.env.GMAIL_CLIENT_SECRET,
  "https://developers.google.com/oauthplayground"
);
oauth2Client.setCredentials({ refresh_token: process.env.GMAIL_REFRESH_TOKEN });

const gmail = google.gmail({ version: "v1", auth: oauth2Client });

// Raw body required for Stripe signature verification
app.post(
  "/webhook",
  express.raw({ type: "application/json" }),
  async (req, res) => {
    const sig = req.headers["stripe-signature"];
    let event;

    try {
      event = stripe.webhooks.constructEvent(
        req.body,
        sig,
        process.env.STRIPE_WEBHOOK_SECRET
      );
    } catch (err) {
      console.error("Webhook signature verification failed:", err.message);
      return res.status(400).send(`Webhook Error: ${err.message}`);
    }

    if (event.type === "customer.created") {
      const customer = event.data.object;
      const toEmail = customer.email;
      const toName = customer.name || toEmail;

      if (!toEmail) {
        console.log("Customer has no email, skipping.");
        return res.json({ received: true });
      }

      try {
        await sendFounderEmail(toEmail, toName);
        console.log(`Welcome email sent to ${toEmail}`);
      } catch (err) {
        console.error(`Failed to send email to ${toEmail}:`, err.message);
        // Return 200 so Stripe doesn't retry — log and handle separately
      }
    }

    res.json({ received: true });
  }
);

async function sendFounderEmail(toEmail, toName) {
  const firstName = toName.split(" ")[0];

  const subject = `Welcome — glad you're here`;

  const body = [
    `Hi ${firstName},`,
    ``,
    `I'm Tim, founder of [Your Company]. I wanted to reach out personally to welcome you.`,
    ``,
    `A few things I'd love to know:`,
    `- What brought you to us?`,
    `- What are you hoping to get done?`,
    `- Is there anything that felt confusing or unclear?`,
    ``,
    `I read every reply. If you run into anything, just hit reply here and it comes straight to me.`,
    ``,
    `Tim`,
    `Founder, [Your Company]`,
  ].join("\n");

  const rawMessage = [
    `From: Tim <${process.env.GMAIL_SENDER_ADDRESS}>`,
    `To: ${toEmail}`,
    `Subject: ${subject}`,
    `Content-Type: text/plain; charset=utf-8`,
    ``,
    body,
  ].join("\n");

  const encoded = Buffer.from(rawMessage)
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");

  await gmail.users.messages.send({
    userId: "me",
    requestBody: { raw: encoded },
  });
}

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`Webhook server listening on port ${PORT}`));
