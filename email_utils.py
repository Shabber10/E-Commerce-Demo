import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import Config


def send_otp_email(recipient_email, otp_code, purpose="verification"):
    """
    Sends a 6-digit verification OTP email via SMTP.
    Returns (True, None) on success or (False, error_message) on failure.
    """
    subject = f"{otp_code} is your E-Commerce Verification Code"
    sender = Config.MAIL_DEFAULT_SENDER

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f"E-Commerce Store <{sender}>"
    msg['To'] = recipient_email

    # Plain-text alternative
    plain_text = f"""Hello,

Your 6-digit verification code for {purpose} is: {otp_code}

This code will expire in 10 minutes. 
If you did not initiate this request, please ignore this email.

Best regards,
E-Commerce Store Team
"""
    part1 = MIMEText(plain_text, 'plain')
    msg.attach(part1)
    # msg.attach(part2)

    try:
        server = smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT, timeout=15)
        if Config.MAIL_USE_TLS:
            server.starttls()
        server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
        server.sendmail(sender, [recipient_email], msg.as_string())
        server.quit()
        return True, None
    except Exception as err:
        print(f"Failed to send email to {recipient_email}: {err}")
        return False, str(err)
