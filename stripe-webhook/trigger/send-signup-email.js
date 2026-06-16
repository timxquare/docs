import { task } from "@trigger.dev/sdk/v3";
import { SIGNUP_FLOW_SEQUENCE } from "../src/sequences.js";

export const sendSignupEmail = task({
  id: "send-signup-email",
  maxDuration: 60,
  run: async (payload) => {
    const { toEmail, toName, day } = payload;

    const sequence = SIGNUP_FLOW_SEQUENCE.find((s) => s.day === day);
    if (!sequence) throw new Error(`No sequence found for day ${day}`);

    const firstName =
      toName && toName !== toEmail ? toName.split(" ")[0] : "there";
    const bodyText = sequence.getBody(firstName);

    const res = await fetch("https://api.sendgrid.com/v3/mail/send", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${process.env.SENDGRID_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        personalizations: [{ to: [{ email: toEmail, name: toName }] }],
        from: { email: "tim@icemail.ai", name: "Tim from Icemail" },
        reply_to: { email: "tim@icemail.ai", name: "Tim from Icemail" },
        subject: sequence.subject,
        content: [{ type: "text/plain", value: bodyText }],
      }),
    });

    if (!res.ok) {
      throw new Error(`SendGrid failed: ${res.status} ${await res.text()}`);
    }

    return { sent: true, email: toEmail, day };
  },
});
