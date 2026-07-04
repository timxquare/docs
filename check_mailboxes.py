#!/usr/bin/env python3
import csv, imaplib, smtplib, ssl, socket, sys, concurrent.futures

CSV_PATH = sys.argv[1] if len(sys.argv) > 1 else "mailboxes.csv"
TIMEOUT = 30

def check_imap(host, port, user, pw):
    try:
        ctx = ssl.create_default_context()
        with imaplib.IMAP4_SSL(host, int(port), ssl_context=ctx, timeout=TIMEOUT) as M:
            M.login(user, pw)
            M.select("INBOX")
            return ("OK", "")
    except Exception as e:
        return ("FAIL", f"{type(e).__name__}: {e}")

def check_smtp(host, port, user, pw):
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, int(port), timeout=TIMEOUT, context=ctx) as S:
            S.login(user, pw)
            return ("OK", "")
    except Exception as e:
        return ("FAIL", f"{type(e).__name__}: {e}")

def process(row):
    email = row["Email"]
    ir = check_imap(row["IMAP Host"], row["IMAP Port"], row["IMAP Username"], row["IMAP Password"])
    sr = check_smtp(row["SMTP Host"], row["SMTP Port"], row["SMTP Username"], row["SMTP Password"])
    return (email, ir, sr)

def main():
    with open(CSV_PATH, newline="") as f:
        rows = [r for r in csv.DictReader(f) if r.get("Email")]

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        for res in ex.map(process, rows):
            results.append(res)

    print(f"{'Email':40} {'IMAP':6} {'SMTP':6}")
    print("-" * 60)
    for email, ir, sr in results:
        print(f"{email:40} {ir[0]:6} {sr[0]:6}")
    print()
    for email, ir, sr in results:
        if ir[0] != "OK":
            print(f"IMAP FAIL {email}: {ir[1]}")
        if sr[0] != "OK":
            print(f"SMTP FAIL {email}: {sr[1]}")

if __name__ == "__main__":
    main()
