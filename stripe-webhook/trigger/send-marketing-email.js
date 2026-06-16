import { task } from "@trigger.dev/sdk/v3";
import { MARKETING_SEQUENCE } from "../src/marketing-sequence.js";

export const sendMarketingEmail = task({
  id: "send-marketing-email",
  maxDuration: 60,
  run: async (payload) => {
    const { toEmail, toName, emailId } = payload;

    const email = MARKETING_SEQUENCE.find((e) => e.id === emailId);
    if (!email) throw new Error(`Marketing email "${emailId}" not found`);

    const firstName =
      toName && toName !== toEmail ? toName.split(" ")[0] : "there";
    const bodyText = email.text.replace(/\{\{firstName\}\}/g, firstName);

    const res = await fetch("https://api.sendgrid.com/v3/mail/send", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${process.env.SENDGRID_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        personalizations: [{ to: [{ email: toEmail, name: toName }] }],
        from: { email: "tim@icemail.ai", name: "Timothy" },
        reply_to: { email: "tim@icemail.ai", name: "Timothy" },
        subject: email.subject,
        content: [{ type: "text/plain", value: bodyText }],
      }),
    });

    if (!res.ok) {
      throw new Error(`SendGrid failed: ${res.status} ${await res.text()}`);
    }

    return { sent: true, email: toEmail, emailId };
  },
});
