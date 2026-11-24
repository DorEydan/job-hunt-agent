#!/usr/bin/env python3
"""Match a job posting to the resume without AI: which of your skills it asks for, in what order, and what's missing.

Used by the control panel's "Prepare a resume for a job" when no AI is set up (and as a first pass when one is).
Pure keyword matching: it never adds a skill, it only orders the ones already on the resume.

    python tools/match.py posting.txt            # uses the configured resume version
"""
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote_plus

# Common skills per field, to spot what a posting asks for that the resume doesn't mention.
KNOWN = {
    "software": ["JavaScript", "TypeScript", "Python", "Java", "C#", ".NET", "Go", "Kotlin", "PHP", "Ruby", "React",
                 "Angular", "Vue", "Next.js", "Node.js", "Express", "Spring", "Django", "Flask", "REST API", "GraphQL",
                 "SQL", "PostgreSQL", "MySQL", "MongoDB", "Redis", "Git", "Docker", "Microservices", "HTML", "CSS"],
    "devops": ["Linux", "Bash", "Docker", "Kubernetes", "Helm", "Terraform", "Ansible", "CI/CD", "Jenkins",
               "GitHub Actions", "GitLab CI", "ArgoCD", "AWS", "Azure", "GCP", "Prometheus", "Grafana", "Python",
               "Networking", "Nginx", "ELK"],
    "data": ["SQL", "Python", "Pandas", "NumPy", "Excel", "Power BI", "Tableau", "Looker", "ETL", "Airflow", "Spark",
             "Snowflake", "BigQuery", "dbt", "Statistics", "Machine Learning", "R"],
    "qa": ["Selenium", "Cypress", "Playwright", "Postman", "API testing", "Jira", "TestRail", "Python", "Java", "SQL",
           "CI/CD", "Test automation"],
    "it": ["Windows Server", "Active Directory", "Microsoft 365", "Azure AD", "Networking", "TCP/IP", "DNS", "DHCP",
           "VMware", "Linux", "PowerShell", "Intune", "ITIL"],
    "security": ["SIEM", "Splunk", "SOC", "Incident response", "Firewalls", "Networking", "Linux", "Python",
                 "Vulnerability management", "IAM", "OWASP"],
    "design": ["Figma", "Sketch", "Adobe XD", "Prototyping", "User research", "Wireframing", "Design systems",
               "Usability testing", "Accessibility"],
    "product": ["Jira", "Roadmap", "A/B testing", "Analytics", "SQL", "Agile", "Scrum", "User stories", "KPIs"],
    "marketing": ["SEO", "SEM", "Google Ads", "Google Analytics", "Meta Ads", "Content marketing", "Email marketing",
                  "HubSpot", "Copywriting", "Social media", "CRM"],
    "sales": ["CRM", "Salesforce", "HubSpot", "Lead generation", "Cold calling", "Negotiation", "B2B", "SaaS"],
}


def term_re(term):
    """Whole-word match that also works for C#, .NET, Node.js, CI/CD."""
    t = re.escape(term.lower()).replace(r"\ ", r"[\s-]?")
    return re.compile(r"(?<![\w.#+])" + t + r"(?![\w#+])")


def count(term, text):
    variants = {term, term.replace(".js", "js"), term.replace(" ", "")} if len(term) > 1 else {term}
    return max(len(term_re(v).findall(text)) for v in variants)


def match(skills, posting, field=None):
    """skills: {label: [items]} from the resume. Returns the order to use, matches, gaps and a 1-10 score."""
    text = posting.lower()[:100_000]
    hits = {lbl: {i: count(i, text) for i in items} for lbl, items in skills.items()}
    first = {lbl: [i for i in sorted(items, key=lambda x: -hits[lbl][x]) if hits[lbl][i]] for lbl, items in skills.items()}
    line_order = sorted(skills, key=lambda l: -sum(hits[l].values()))
    matched = [i for lbl in skills for i in skills[lbl] if hits[lbl][i]]
    have = {i.lower() for items in skills.values() for i in items}
    pool = list(dict.fromkeys(KNOWN.get(field, []) + [k for v in KNOWN.values() for k in v]))  # field first
    gaps = [k for k in pool if k.lower() not in have and count(k, text)]
    asked = len(matched) + len(gaps)
    score = round(1 + 9 * len(matched) / asked) if asked else 5
    return {"first": {l: v for l, v in first.items() if v}, "line_order": line_order, "matched": matched,
            "gaps": gaps, "score": score}


def learning_links(skill):
    """Course search links per platform, for when no AI agent can research courses."""
    q = quote_plus(skill)
    return {
        "youtube": f"https://www.youtube.com/results?search_query={q}+full+course",
        "udemy": f"https://www.udemy.com/courses/search/?q={q}&sort=highest-rated",
        "coursera": f"https://www.coursera.org/search?query={q}",
        "edx": f"https://www.edx.org/search?q={q}",
        "freecodecamp": f"https://www.freecodecamp.org/news/search/?query={q}",
        "pluralsight": f"https://www.pluralsight.com/search?q={q}",
        "linkedin-learning": f"https://www.linkedin.com/learning/search?keywords={q}",
        "official-docs": f"https://duckduckgo.com/?q={q}+official+documentation+getting+started",
    }


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import subprocess
    out = subprocess.run([sys.executable, str(Path(__file__).with_name("tailor_resume.py")), "--list"],
                         capture_output=True, text=True, encoding="utf-8", check=True).stdout
    print(json.dumps(match(json.loads(out), Path(sys.argv[1]).read_text(encoding="utf-8")), ensure_ascii=False, indent=2))
