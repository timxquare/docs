import { task } from "@trigger.dev/sdk/v3";

// Trigger.dev is only the scheduler — actual sending is handled by the Cloudflare Worker.
export const sendSignupEmail = task({
  id: "send-signup-email",
  maxDuration: 60,
  run: async (payload) => {
    const { toEmail, toName, day, workerUrl } = payload;

    const res = await fetch(`${workerUrl}/send-email`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${process.env.SEED_TOKEN}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ type: "signup", toEmail, toName, day }),
    });

    if (!res.ok) {
      throw new Error(`Worker /send-email failed: ${res.status} ${await res.text()}`);
    }

    return { sent: true, email: toEmail, day };
  },
});
