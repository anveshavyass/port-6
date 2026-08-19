from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "sample_docs"
OUTPUT_DIR.mkdir(exist_ok=True)

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="DocTitle", fontSize=18, leading=22, spaceAfter=6, fontName="Helvetica-Bold"))
styles.add(ParagraphStyle(name="DocSubtitle", fontSize=11, leading=14, spaceAfter=16, textColor=colors.HexColor("#555555")))
styles.add(ParagraphStyle(name="H1", fontSize=14, leading=18, spaceBefore=16, spaceAfter=8, fontName="Helvetica-Bold", textColor=colors.HexColor("#1a3c5e")))
styles.add(ParagraphStyle(name="H2", fontSize=12, leading=15, spaceBefore=10, spaceAfter=6, fontName="Helvetica-Bold"))
styles.add(ParagraphStyle(name="Body", fontSize=10, leading=14, spaceAfter=8))
styles.add(ParagraphStyle(name="SmartBullet", fontSize=10, leading=14, leftIndent=12))


def doc_control_table(doc_id, version, effective_date, owner):
    data = [
        ["Document ID", doc_id, "Version", version],
        ["Effective Date", effective_date, "Owner", owner],
    ]
    t = Table(data, colWidths=[1.2 * inch, 1.9 * inch, 1.1 * inch, 1.7 * inch])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef2f7")),
                ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#eef2f7")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return t


def bullets(items):
    return ListFlowable(
        [ListItem(Paragraph(i, styles["SmartBullet"]), bulletColor=colors.HexColor("#1a3c5e")) for i in items],
        bulletType="bullet",
        start="circle",
        leftIndent=18,
    )


def build_pdf(filename, title, subtitle, doc_id, version, effective_date, owner, flowables):
    path = OUTPUT_DIR / filename
    doc = SimpleDocTemplate(
        str(path),
        pagesize=LETTER,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        leftMargin=0.85 * inch,
        rightMargin=0.85 * inch,
        title=title,
    )
    story = [
        Paragraph(title, styles["DocTitle"]),
        Paragraph(subtitle, styles["DocSubtitle"]),
        doc_control_table(doc_id, version, effective_date, owner),
        Spacer(1, 14),
        *flowables,
    ]
    doc.build(story)
    print(f"  wrote {path}")


def leave_policy():
    f = []
    f.append(Paragraph("1. Purpose and Scope", styles["H1"]))
    f.append(Paragraph(
        "This policy defines paid time off (PTO), sick leave, holiday, parental leave, and "
        "bereavement leave entitlements for all full-time employees of Clearwave Technologies, "
        "Inc. (“Clearwave”). It does not apply to interns, contractors, or part-time staff "
        "working fewer than 30 hours per week, who are covered under separate agreements.",
        styles["Body"],
    ))

    f.append(Paragraph("2. Paid Time Off (PTO) Accrual", styles["H1"]))
    f.append(Paragraph(
        "PTO accrues monthly based on tenure, prorated from the employee's hire date. Accrual "
        "rates are as follows:", styles["Body"],
    ))
    table_data = [
        ["Years of Service", "Annual PTO Days", "Monthly Accrual"],
        ["0–2 years", "15 days", "1.25 days"],
        ["3–5 years", "20 days", "1.67 days"],
        ["6+ years", "25 days", "2.08 days"],
    ]
    t = Table(table_data, colWidths=[2 * inch, 2 * inch, 2 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3c5e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f7fa")]),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    f.append(t)
    f.append(Spacer(1, 8))
    f.append(Paragraph(
        "A maximum of 5 unused PTO days may be carried over into the next calendar year. "
        "Any PTO balance exceeding this carryover cap is forfeited on December 31. PTO does "
        "not accrue during unpaid leave of absence.", styles["Body"],
    ))

    f.append(Paragraph("3. Sick Leave", styles["H1"]))
    f.append(bullets([
        "Employees receive 8 paid sick days per calendar year, credited in full on January 1.",
        "Sick leave does not carry over and is not paid out upon termination.",
        "A doctor's note is required for absences exceeding 3 consecutive workdays.",
        "Sick leave may be used for the employee's own illness or to care for an immediate family member.",
    ]))

    f.append(Paragraph("4. Company Holidays", styles["H1"]))
    f.append(Paragraph(
        "Clearwave observes 10 paid holidays annually: New Year's Day, Martin Luther King Jr. Day, "
        "Memorial Day, Juneteenth, Independence Day, Labor Day, Thanksgiving Day, the day after "
        "Thanksgiving, Christmas Eve, and Christmas Day. The finalized holiday calendar is "
        "published each December on the People Operations intranet page.", styles["Body"],
    ))

    f.append(Paragraph("5. Parental Leave", styles["H1"]))
    f.append(bullets([
        "Primary caregivers receive 12 weeks of fully paid parental leave.",
        "Secondary caregivers receive 6 weeks of fully paid parental leave.",
        "Leave must be taken within 12 months of the birth, adoption, or foster placement.",
        "Leave may be taken continuously or split into two blocks with People Operations approval.",
    ]))

    f.append(Paragraph("6. Bereavement Leave", styles["H1"]))
    f.append(Paragraph(
        "Employees receive 5 paid days of bereavement leave for the death of an immediate family "
        "member (spouse, child, parent, or sibling) and 2 paid days for extended family members "
        "(grandparent, grandchild, aunt, uncle, or in-law).", styles["Body"],
    ))

    f.append(Paragraph("7. Requesting Time Off", styles["H1"]))
    f.append(bullets([
        "All PTO requests must be submitted through Workday.",
        "Requests for more than 3 consecutive PTO days require at least 2 weeks' advance notice.",
        "Managers must approve or deny PTO requests within 3 business days of submission.",
        "Unapproved absences are recorded as unpaid time off and may result in disciplinary action.",
    ]))

    f.append(Paragraph("8. Questions", styles["H1"]))
    f.append(Paragraph(
        "Direct questions about this policy to the People Operations team at "
        "peopleops@clearwavetech.com or via the #ask-people-ops Slack channel.", styles["Body"],
    ))

    build_pdf(
        "01_HR_Time_Off_Leave_Policy.pdf",
        "Time Off &amp; Leave Policy",
        "Clearwave Technologies, Inc. — Human Resources Policy",
        "HR-PL-002", "3.2", "January 1, 2025", "People Operations",
        f,
    )


def conduct_policy():
    f = []
    f.append(Paragraph("1. Purpose", styles["H1"]))
    f.append(Paragraph(
        "This Code of Conduct establishes the standards of professional behavior expected of "
        "every Clearwave Technologies employee, contractor, and officer, regardless of role or "
        "location.", styles["Body"],
    ))

    f.append(Paragraph("2. Professional Conduct Standards", styles["H1"]))
    f.append(bullets([
        "Treat colleagues, customers, and partners with respect and courtesy at all times.",
        "Perform job duties honestly, competently, and in compliance with applicable laws.",
        "Avoid conduct that could damage Clearwave's reputation, on or off company premises.",
    ]))

    f.append(Paragraph("3. Anti-Harassment and Anti-Discrimination", styles["H1"]))
    f.append(Paragraph(
        "Clearwave maintains a zero-tolerance policy toward harassment or discrimination based on "
        "race, color, religion, sex, national origin, age, disability, sexual orientation, gender "
        "identity, veteran status, or any other legally protected characteristic. This applies to "
        "in-person, written, and electronic communication.", styles["Body"],
    ))

    f.append(Paragraph("4. Reporting Procedure", styles["H1"]))
    f.append(bullets([
        "Report concerns to your manager, any HR Business Partner, or the anonymous Ethics "
        "Hotline at 1-800-555-0143 (available 24/7, staffed by a third-party provider).",
        "Reports may be made anonymously and will be investigated within 10 business days.",
        "Retaliation against anyone who reports a concern in good faith is strictly prohibited "
        "and is itself grounds for disciplinary action, up to and including termination.",
    ]))

    f.append(Paragraph("5. Conflicts of Interest", styles["H1"]))
    f.append(Paragraph(
        "Employees must disclose any actual or potential conflict of interest — including "
        "outside employment, financial interests in vendors or competitors, or close personal "
        "relationships with direct reports — to their manager and HR within 5 business days "
        "of becoming aware of it.", styles["Body"],
    ))

    f.append(Paragraph("6. Gifts and Entertainment", styles["H1"]))
    f.append(Paragraph(
        "Employees may accept or offer business gifts or entertainment valued up to $75 per "
        "occurrence. Anything above this threshold requires prior written approval from a "
        "director-level manager and must be logged with Finance.", styles["Body"],
    ))

    f.append(Paragraph("7. Confidentiality and Data Handling", styles["H1"]))
    f.append(Paragraph(
        "Confidential company, customer, and employee information must not be disclosed outside "
        "Clearwave without authorization, and must be handled in accordance with the Information "
        "Security Policy (SEC-POL-004). This obligation survives termination of employment.",
        styles["Body"],
    ))

    f.append(Paragraph("8. Social Media Guidelines", styles["H1"]))
    f.append(Paragraph(
        "Employees speaking publicly about Clearwave in a personal capacity must clearly state "
        "that views expressed are their own and must not share confidential, financial, or "
        "unreleased product information.", styles["Body"],
    ))

    f.append(Paragraph("9. Disciplinary Process", styles["H1"]))
    f.append(Paragraph(
        "Violations of this Code are addressed through a progressive process: verbal warning, "
        "written warning, formal Performance Improvement Plan (PIP), and termination. Serious "
        "violations — including harassment, fraud, or safety violations — may result in "
        "immediate termination without progressing through earlier steps.", styles["Body"],
    ))

    f.append(Paragraph("10. Dress Code", styles["H1"]))
    f.append(Paragraph(
        "Standard office attire is business casual. Employee-facing client meetings, executive "
        "briefings, and investor events require business formal attire unless otherwise "
        "specified by the meeting organizer.", styles["Body"],
    ))

    build_pdf(
        "02_HR_Code_of_Conduct_Policy.pdf",
        "Code of Conduct &amp; Workplace Standards",
        "Clearwave Technologies, Inc. — Human Resources Policy",
        "HR-CD-010", "2.0", "March 1, 2024", "People Operations &amp; Legal",
        f,
    )


def product_manual():
    f = []
    f.append(Paragraph("1. Overview", styles["H1"]))
    f.append(Paragraph(
        "TicketDesk is a cloud-based customer support and ticketing platform used by Clearwave's "
        "internal support teams to manage customer inquiries, incidents, and service requests. "
        "This guide covers administrator-level configuration for TicketDesk version 4.2.",
        styles["Body"],
    ))

    f.append(Paragraph("2. System Requirements", styles["H1"]))
    f.append(bullets([
        "Supported browsers: Chrome 100+, Microsoft Edge 100+, Safari 15+, Firefox 100+.",
        "Business plan: up to 500 concurrent agent seats.",
        "Enterprise plan: up to 2,000 concurrent agent seats and dedicated infrastructure.",
        "Minimum recommended network bandwidth: 5 Mbps per active agent session.",
    ]))

    f.append(Paragraph("3. Account Roles and Permissions", styles["H1"]))
    table_data = [
        ["Role", "Manage Billing", "Manage Users", "Edit SLA Rules", "View Reports"],
        ["Owner", "Yes", "Yes", "Yes", "Yes"],
        ["Admin", "No", "Yes", "Yes", "Yes"],
        ["Agent", "No", "No", "No", "Limited (own tickets)"],
        ["Viewer", "No", "No", "No", "Yes"],
    ]
    t = Table(table_data, colWidths=[1.1 * inch, 1.1 * inch, 1.1 * inch, 1.1 * inch, 1.6 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3c5e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f7fa")]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    f.append(t)

    f.append(Paragraph("4. Setting Up Your Workspace", styles["H1"]))
    f.append(bullets([
        "Verify your organization's domain under Settings → Domains before inviting agents.",
        "Single sign-on (SSO) is supported via SAML 2.0; configure the identity provider under "
        "Settings → Security → SSO.",
        "Custom ticket fields (up to 40 per workspace) can be created under Settings → Fields.",
    ]))

    f.append(Paragraph("5. Ticket Routing and SLA Rules", styles["H1"]))
    f.append(Paragraph(
        "Tickets are auto-assigned using round-robin or load-based rules configured under "
        "Automations → Routing. SLA breach warnings are triggered automatically once 80% of "
        "the allotted SLA time has elapsed, notifying the assigned agent and their manager.",
        styles["Body"],
    ))

    f.append(Paragraph("6. Integrations", styles["H1"]))
    f.append(bullets([
        "Slack: two-way ticket notifications and reply-from-Slack support.",
        "Email-to-ticket: inbound emails to support@yourdomain.com auto-create tickets.",
        "Zapier: connect TicketDesk to 3,000+ third-party apps without custom code.",
        "REST API: rate-limited to 100 requests per minute per API key; returns HTTP 429 when exceeded.",
    ]))

    f.append(Paragraph("7. Troubleshooting Common Issues", styles["H1"]))
    table_data = [
        ["Error Code", "Meaning", "Resolution"],
        ["TD-401", "Authentication failed", "Regenerate the API key under Settings → API"],
        ["TD-403", "Insufficient permissions", "Confirm the agent's role has the required access"],
        ["TD-503", "Rate limit exceeded", "Reduce request frequency or request a limit increase"],
        ["TD-522", "Webhook delivery timeout", "Verify the receiving endpoint responds within 10s"],
    ]
    t2 = Table(table_data, colWidths=[1.1 * inch, 2 * inch, 2.9 * inch])
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3c5e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f7fa")]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    f.append(t2)

    f.append(Paragraph("8. Data Export and Retention", styles["H1"]))
    f.append(Paragraph(
        "Tickets can be exported as CSV or JSON under Reports → Export. Business plan tickets "
        "are retained for 2 years; Enterprise plan tickets are retained for 7 years to support "
        "compliance requirements.", styles["Body"],
    ))

    f.append(Paragraph("9. Support", styles["H1"]))
    f.append(Paragraph(
        "For further assistance, contact support@ticketdesk.io. Enterprise customers have access "
        "to a dedicated priority support line with a 1-hour response SLA.", styles["Body"],
    ))

    build_pdf(
        "03_Product_Manual_TicketDesk_Admin_Guide.pdf",
        "TicketDesk Administrator Guide",
        "TicketDesk v4.2 — Internal Product Manual (Clearwave Technologies)",
        "PM-TD-042", "4.2", "February 15, 2025", "Product &amp; Support Engineering",
        f,
    )


def onboarding_guide():
    f = []
    f.append(Paragraph("Welcome to Clearwave!", styles["H1"]))
    f.append(Paragraph(
        "This guide walks you through your first day, first week, and first 90 days at Clearwave "
        "Technologies. Bookmark it — you'll want to refer back to it during your first month.",
        styles["Body"],
    ))

    f.append(Paragraph("1. Before Your First Day", styles["H1"]))
    f.append(bullets([
        "Complete your I-9 and W-4 forms in Workday (link sent by People Operations).",
        "Your laptop will ship to your home address 3–5 business days before your start date.",
        "Background check completion is required before systems access is granted.",
    ]))

    f.append(Paragraph("2. Your First Day Schedule", styles["H1"]))
    table_data = [
        ["Time", "Activity"],
        ["9:00 AM", "Company orientation (People Operations, virtual)"],
        ["10:30 AM", "IT equipment setup and account provisioning"],
        ["1:00 PM", "Benefits overview session"],
        ["3:00 PM", "Team introduction and welcome lunch"],
    ]
    t = Table(table_data, colWidths=[1.3 * inch, 4.7 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3c5e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f7fa")]),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    f.append(t)

    f.append(Paragraph("3. First Week Checklist", styles["H1"]))
    f.append(bullets([
        "Meet 1:1 with your manager to review your 30-60-90 day plan.",
        "Complete mandatory compliance training (Code of Conduct, Security Awareness) within 5 "
        "business days of your start date.",
        "Set up Slack, email, and calendar; join your team's and department's channels.",
        "Meet your assigned Onboarding Buddy, who will help answer day-to-day questions.",
    ]))

    f.append(Paragraph("4. Benefits Enrollment", styles["H1"]))
    f.append(Paragraph(
        "You have 30 days from your start date to enroll in medical, dental, and vision coverage "
        "through the Benefits portal. Clearwave matches 401(k) contributions up to 4% of salary, "
        "and matching begins after your first 90 days of employment.", styles["Body"],
    ))

    f.append(Paragraph("5. IT and Equipment", styles["H1"]))
    f.append(bullets([
        "Laptops are provisioned and shipped within 24 hours of your background check clearing.",
        "VPN access is required for all internal systems when working outside the office network.",
        "Password policy: minimum 12 characters, and multi-factor authentication (MFA) is "
        "mandatory for all accounts.",
    ]))

    f.append(Paragraph("6. Your 30-60-90 Day Plan", styles["H1"]))
    f.append(bullets([
        "Day 30: Complete all required training and be fully set up on core team tools.",
        "Day 60: Take ownership of your first independent project or workstream.",
        "Day 90: Complete your first performance check-in with your manager.",
    ]))

    f.append(Paragraph("7. Who to Contact", styles["H1"]))
    f.append(bullets([
        "People Operations questions: peopleops@clearwavetech.com",
        "IT Helpdesk (equipment, access, VPN): ithelpdesk@clearwavetech.com or Slack #it-helpdesk",
        "Payroll and benefits: benefits@clearwavetech.com",
        "General onboarding questions: your assigned Onboarding Buddy or manager",
    ]))

    build_pdf(
        "04_New_Hire_Onboarding_Guide.pdf",
        "New Hire Onboarding Guide",
        "Clearwave Technologies, Inc. — People Operations",
        "HR-OB-007", "1.4", "January 1, 2025", "People Operations",
        f,
    )


def escalation_sop():
    f = []
    f.append(Paragraph("1. Purpose and Scope", styles["H1"]))
    f.append(Paragraph(
        "This Standard Operating Procedure defines how the IT Helpdesk classifies, escalates, and "
        "resolves reported incidents, from an individual user's login issue to a company-wide "
        "system outage. It applies to all Tier 1, Tier 2, and Tier 3 support staff.", styles["Body"],
    ))

    f.append(Paragraph("2. Severity Definitions and Targets", styles["H1"]))
    table_data = [
        ["Severity", "Description", "Response Time", "Resolution Target"],
        ["Sev 1 – Critical", "System down; all users affected", "15 minutes", "4 hours"],
        ["Sev 2 – High", "Major feature broken; many users affected", "1 hour", "8 business hours"],
        ["Sev 3 – Medium", "Issue has a workaround", "4 business hours", "3 business days"],
        ["Sev 4 – Low", "Cosmetic or minor issue", "1 business day", "10 business days"],
    ]
    t = Table(table_data, colWidths=[1.3 * inch, 2.2 * inch, 1.2 * inch, 1.3 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3c5e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f7fa")]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    f.append(t)
    f.append(Spacer(1, 8))
    f.append(Paragraph(
        "If a Sev 1 incident is not resolved within 2 hours of initial report, it must be "
        "automatically escalated to the IT Director.", styles["Body"],
    ))

    f.append(Paragraph("3. Escalation Path", styles["H1"]))
    f.append(Paragraph(
        "Tier 1 Helpdesk → Tier 2 Systems Engineer → Tier 3 Senior Engineer / Vendor Support "
        "→ IT Director. Each tier must attempt resolution within its allotted response window "
        "before escalating further.", styles["Body"],
    ))

    f.append(Paragraph("4. Step-by-Step Procedure", styles["H1"]))
    f.append(bullets([
        "Step 1: Log the incident in TicketDesk immediately upon report, capturing affected "
        "systems and number of users impacted.",
        "Step 2: Classify severity using the table in Section 2.",
        "Step 3: Tier 1 attempts initial triage and resolution using the internal knowledge base.",
        "Step 4: If unresolved at 80% of the response time window, escalate to the next tier.",
        "Step 5: For Sev 1 and Sev 2 incidents, post a status update to the internal status page "
        "and notify affected department leads.",
        "Step 6: Upon resolution, document root cause and remediation steps in the ticket.",
        "Step 7: For every Sev 1 incident, conduct a blameless post-incident review within 5 "
        "business days of resolution.",
    ]))

    f.append(Paragraph("5. Communication Cadence", styles["H1"]))
    f.append(bullets([
        "Sev 1: status update every 30 minutes until resolved.",
        "Sev 2: status update every hour until resolved.",
        "Sev 3 and Sev 4: status update upon any material change, or at minimum once per business day.",
    ]))

    f.append(Paragraph("6. Roles and Responsibilities", styles["H1"]))
    f.append(bullets([
        "Tier 1 Helpdesk: initial triage, classification, and first-line resolution.",
        "Tier 2 Systems Engineer: deeper technical investigation and infrastructure-level fixes.",
        "Tier 3 Senior Engineer / Vendor: root-cause resolution for complex or vendor-dependent issues.",
        "IT Director: executive communication and resourcing decisions for unresolved Sev 1 incidents.",
    ]))

    build_pdf(
        "05_SOP_IT_Helpdesk_Incident_Escalation.pdf",
        "SOP: IT Helpdesk Incident Escalation",
        "Clearwave Technologies, Inc. — IT Service Management",
        "SOP-IT-014", "1.5", "July 1, 2024", "IT Service Management",
        f,
    )


if __name__ == "__main__":
    print(f"Generating sample PDFs into {OUTPUT_DIR}...")
    leave_policy()
    conduct_policy()
    product_manual()
    onboarding_guide()
    escalation_sop()
    print("Done.")
