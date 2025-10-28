import resend
import logging
from app.configs.app_settings import settings
from typing import Optional

logger = logging.getLogger(__name__)

# Initialize Resend with API key
resend.api_key = settings.RESEND_API_KEY


class EmailService:
    """Service for sending emails via Resend"""

    @staticmethod
    def send_new_job_notification(
        job_id: str,
        job_title: str,
        job_type: str,
        job_budget: str,
        location_address: str,
        city: str,
        description: str,
        buyer_email: str,
    ) -> bool:
        """
        Send email notification to internal team when a new job is posted
        Returns True if email sent successfully, False otherwise
        """
        try:
            # Email HTML template
            html_content = f"""
            <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <h2 style="color: #2563eb;">🆕 New Job Posted on Bidquotes</h2>
                    
                    <div style="background-color: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <h3 style="margin-top: 0; color: #1f2937;">Job Details</h3>
                        
                        <p><strong>Job ID:</strong> {job_id}</p>
                        <p><strong>Title:</strong> {job_title}</p>
                        <p><strong>Type:</strong> {job_type}</p>
                        <p><strong>Budget:</strong> {job_budget}</p>
                        <p><strong>Location:</strong> {location_address}, {city}</p>
                        
                        <h4 style="margin-top: 20px; color: #1f2937;">Description:</h4>
                        <p style="background-color: white; padding: 15px; border-radius: 4px;">{description}</p>
                        
                        <h4 style="color: #1f2937;">Homeowner Contact:</h4>
                        <p><strong>Email:</strong> {buyer_email}</p>
                    </div>
                    
                    <p style="color: #6b7280; font-size: 14px; margin-top: 30px;">
                        This is an automated notification from Bidquotes platform.
                    </p>
                </body>
            </html>
            """

            # Send email using Resend
            params = {
                "from": "Bidquotes <noreply@bidquotecanada.com>",
                "to": ["info@bidquotecanada.com"],
                "subject": f"New Job Posted: {job_title}",
                "html": html_content,
            }

            email = resend.Emails.send(params)
            logger.info(f"✅ Email notification sent for job {job_id}: {email}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to send email notification for job {job_id}: {str(e)}")
            # Don't raise exception - we don't want email failure to block job creation
            return False
