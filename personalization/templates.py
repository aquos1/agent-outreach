"""Static per-path email templates and pure assembly.

No network calls, no I/O, static string templates only -- three verbatim
per-path templates (03-CONTEXT.md `<specifics>`, user-approved) and a pure
merge-field substitution function. No templating engine (Jinja2, etc.);
plain str.format only.

D-04/D-05 (Phase 4): assemble_email() also accepts optional override
subject/body text -- when supplied, the override wins over PATH_TEMPLATES.
This module still never touches SQLite; db/templates_store.py owns
persistence and passes the override text in as plain strings.
"""
from __future__ import annotations

import re

# Keys reuse the exact three slugs already defined in discovery/logic.py's
# PATH_CONFIG -- not re-invented here.
PATH_TEMPLATES = {
    "club_sponsorship": {
        "subject": "Partner with Product Space UW — {company} Annual Sponsorship",
        "body": (
            "Hello {first_name}!\n\n"
            "{opening_line}\n\n"
            "I hope this email finds you well! My name is Yash Kulkarni, and I "
            "am reaching out on behalf of Product Space UW, the premier "
            "product management and tech community at the University of "
            "Washington, affiliated with the Foster School of Business, with "
            "chapters at UCLA, Stanford, UPenn, UC Berkeley, and more.\n\n"
            "Our community includes 11 exec members, 45 core members, and "
            "250+ students across the wider community, spanning majors like "
            "Computer Science, Informatics, Human-Centered Design & "
            "Engineering, Data Science, Engineering, Business, Economics, and "
            "Design. Throughout the year, we ship real projects with company "
            "partners, host workshops and speaker symposiums, and run "
            "recruiting events for our members.\n\n"
            "Given {company}'s leadership in technology and innovation, we'd "
            "love to explore an annual sponsorship partnership. Here's what "
            "Product Space UW sponsors receive:\n"
            "- Recruiting Pipeline: An opt-in resume book updated each "
            "quarter, curated introductions based on your role criteria, and "
            "event RSVPs with attendee skill tags.\n"
            "- Brand & Thought Leadership: Logo placement on our website, "
            "slides, and printed materials, plus speaker slots (tech talks, "
            "workshops, panels) and social/newsletter features.\n"
            "- Project Delivery: A dedicated 5-7 student team (PM/design/eng "
            "mix) with a faculty or alumni advisor, weekly standups, and a "
            "final report/prototype/hand-off with a sponsor debrief.\n\n"
            "Here's our sponsorship prospectus with our full tier breakdown: "
            "[SPONSORSHIP_LINK]. Would you be open to a brief 10-minute call "
            "this week to discuss a partnership that aligns with {company}'s "
            "recruiting and branding goals?\n\n"
            "Thank you so much for your time and support of student "
            "innovation!\n\n"
            "Best regards,\n"
            "Yash Kulkarni\n"
            "Director of Internal, Product Space at the University of "
            "Washington"
        ),
    },
    "productthon": {
        "subject": (
            "Sponsorship Opportunity — UW Product Space: The Product Games "
            "(Productthon)"
        ),
        "body": (
            "Hello {first_name}!\n\n"
            "{opening_line}\n\n"
            "I hope this email finds you well! My name is Yash Kulkarni, and I "
            "am reaching out on behalf of Product Space UW, the premier "
            "product management and tech community at the University of "
            "Washington, affiliated with the Foster School of Business.\n\n"
            "We are currently gearing up for our annual competition, The "
            "Product Games — a one-day product-thon blending the strategy of "
            "a case competition with the implementation of a hackathon. "
            "During the event, top UW students tackle a real-world "
            "innovation challenge, research product opportunities, build "
            "MVPs using AI tools, and pitch their solutions to a panel of "
            "expert judges.\n\n"
            "Given {company}'s leadership in technology and innovation, we "
            "would love to feature you as an official sponsor for the "
            "event.\n\n"
            "Here's an outline of what Product Space UW can offer you:\n"
            "- Direct Recruiting Access: Access to our comprehensive resume "
            "book and exclusive networking opportunities with "
            "participants.\n"
            "- Brand Visibility: Company logos featured on our website, "
            "marketing collateral, and social media channels.\n"
            "- Custom Challenges & Mentorship: Opportunities to provide the "
            "official event prompt, send company judges/mentors, or "
            "participate in a fireside chat.\n\n"
            "Here's our sponsorship package with general information and "
            "sponsorship breakdowns: [SPONSORSHIP_LINK]. Would you be open to "
            "a brief 10-minute call this week to discuss how we can tailor a "
            "package that aligns with {company}'s recruiting and branding "
            "goals?\n\n"
            "Thank you so much for your time and support of student "
            "innovation!\n\n"
            "Best regards,\n"
            "Yash Kulkarni\n"
            "Director of Internal, Product Space at the University of "
            "Washington"
        ),
    },
    "client_sourcing": {
        "subject": "Partner with Product Space UW on Your Next Product Initiative",
        "body": (
            "Hi {first_name},\n\n"
            "{opening_line}\n\n"
            "Have a feature idea or internal product initiative that keeps "
            "getting pushed down the roadmap?\n\n"
            "We are Product Space UW, a branch of the national Product Space "
            "organization that has chapters at UCLA, Stanford, UPenn, UC "
            "Berkeley, and more!\n\n"
            "At Product Space UW, we help companies like {company} move those "
            "projects forward—by pairing you with a dedicated team of "
            "product-minded students from the University of Washington. Our "
            "teams are made up of ambitious individuals from various "
            "backgrounds such as computer science, design, engineering, "
            "informatics, and finance, and they are eager to apply their "
            "skills to real-world challenges and deliver tangible impact.\n\n"
            "The value for you:\n"
            "- Fresh, diverse perspectives on your product or process\n"
            "- Momentum on a project that you've been wanting to tackle\n"
            "- A meaningful way to give back by mentoring the next "
            "generation of product leaders\n\n"
            "We've worked with companies such as Amazon, Microsoft, and "
            "Refer.me on user research, competitor analysis, product "
            "documentation, prototyping, and more, and we would love to "
            "bring our experience and passion to you and your team! This "
            "could be a great way to de-risk an idea, test a new feature, or "
            "explore improvements without pulling your team off core "
            "priorities.\n\n"
            "If this opportunity sounds interesting, please let us know and "
            "we can schedule a 15-minute call to explore whether we'd be a "
            "good fit!\n\n"
            "Best regards,\n"
            "Yash Kulkarni\n"
            "Director of Internal, Product Space at the University of "
            "Washington"
        ),
    },
}


# The complete and only set of merge fields a teammate-edited template may
# use (D-06). Checked against the combined subject+body text before a save.
REQUIRED_FIELDS = {"first_name", "company", "opening_line"}


def assemble_email(
    path_slug: str,
    first_name: str,
    company: str,
    opening_line: str,
    subject_template: str | None = None,
    body_template: str | None = None,
) -> tuple[str, str]:
    """Merge the opening line and Apollo fields into a ready-to-send email.

    D-09: {opening_line} sits on its own standalone line directly after the
    greeting in every template's body, before the intro paragraph. Pure
    function -- no I/O, no logging.

    D-04/D-05: subject_template/body_template are optional override text
    (loaded by the caller from db/templates_store.get_template). When
    either is None, falls back to PATH_TEMPLATES[path_slug] -- the override,
    when supplied, wins over PATH_TEMPLATES. This module still never touches
    SQLite. The subject is now formatted with all three merge fields (not
    just company as before) since a teammate may legitimately put
    {first_name} or {opening_line} in a subject line.
    """
    template = PATH_TEMPLATES[path_slug]
    subject = subject_template if subject_template is not None else template["subject"]
    body = body_template if body_template is not None else template["body"]
    subject = subject.format(
        first_name=first_name, company=company, opening_line=opening_line
    )
    body = body.format(
        first_name=first_name, company=company, opening_line=opening_line
    )
    return subject, body


def validate_template_fields(subject: str, body: str) -> tuple[bool, str]:
    """Confirm all 3 required merge fields are present, and no others, before
    a save (D-06). Validation runs over the combined subject+body text -- a
    field present only in the subject (or only in the body) still counts.

    Pure function -- no I/O. Missing/misspelled placeholders block the save
    in review_queue_page.py rather than shipping a literal '{first_name}' or
    a silently generic email to a real contact. An unknown placeholder (e.g.
    a stray {last_name}) would raise KeyError at assembly time and must
    never reach a real contact, so it is rejected here too.
    """
    present = set(re.findall(r"\{(\w+)\}", f"{subject}\n{body}"))
    missing = REQUIRED_FIELDS - present
    if missing:
        return False, (
            f"Missing merge field(s): {', '.join(sorted(missing))}. Add them "
            "back before saving — without them, contacts would receive a "
            "broken or generic email."
        )
    unknown = present - REQUIRED_FIELDS
    if unknown:
        return False, (
            f"Unknown merge field(s): {', '.join(sorted(unknown))}. Only "
            "{first_name}, {company} and {opening_line} are available."
        )
    return True, "OK"
