import Stripe from "stripe";

export default {
  async fetch(request, env, ctx) {
    if (request.method !== "POST") {
      return new Response("Method not allowed", { status: 405 });
    }

    const stripe = new Stripe(env.STRIPE_SECRET_KEY, {
      httpClient: Stripe.createFetchHttpClient(),
    });
    const cryptoProvider = Stripe.createSubtleCryptoProvider();

    const sig = request.headers.get("stripe-signature");
    const body = await request.text();

    let event;
    try {
      event = await stripe.webhooks.constructEventAsync(
        body,
        sig,
        env.STRIPE_WEBHOOK_SECRET,
        undefined,
        cryptoProvider
      );
    } catch (err) {
      console.error("Signature verification failed:", err.message);
      return new Response(`Webhook Error: ${err.message}`, { status: 400 });
    }

    if (event.type === "customer.created") {
      const customer = event.data.object;
      const toEmail = customer.email;
      const toName = customer.name || toEmail;

      if (toEmail) {
        // Send in the background so we ACK Stripe immediately
        ctx.waitUntil(
          sendFounderEmail(env, toEmail, toName).catch((err) =>
            console.error(`Failed to email ${toEmail}:`, err.message)
          )
        );
      }
    }

    return new Response(JSON.stringify({ received: true }), {
      headers: { "Content-Type": "application/json" },
    });
  },
};

async function sendFounderEmail(env, toEmail, toName) {
  const firstName = toName.split(" ")[0];

  const bodyText = [
    `Hi ${firstName},`,
    ``,
    `I'm Tim, founder of Icemail. I wanted to reach out personally to welcome you.`,
    ``,
    `A few things I'd love to know:`,
    `- What brought you to Icemail?`,
    `- What are you hoping to get done?`,
    `- Is there anything that felt confusing or unclear?`,
    ``,
    `I read every reply. If you run into anything, just hit reply here and it comes straight to me.`,
    ``,
    `Timothy Vadde`,
    `Founder @ Icemail`,
    `icemail.ai`,
  ].join("\n");

  const payload = {
    personalizations: [{ to: [{ email: toEmail, name: toName }] }],
    from: { email: "tim@icemail.ai", name: "Timothy Vadde" },
    reply_to: { email: "tim@icemail.ai", name: "Timothy Vadde" },
    subject: "Welcome - glad you're here",
    content: [{ type: "text/plain", value: bodyText }],
  };

  const res = await fetch("https://api.sendgrid.com/v3/mail/send", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.SENDGRID_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    throw new Error(`SendGrid send failed: ${res.status} ${await res.text()}`);
  }
}
