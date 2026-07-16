from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Literal

from deepagents import create_deep_agent
from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()

OUTPUT_DIR = Path(os.getenv("RACINE_OUTPUT_DIR", "./racine_outputs"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def internet_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
) -> str:
    """Search the public web and return source records for evidence-led research."""
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY is required for public-web research.")

    client = TavilyClient(api_key=api_key)
    result = client.search(
        query=query,
        max_results=max(1, min(max_results, 8)),
        topic=topic,
        include_raw_content=False,
    )
    return json.dumps(result, ensure_ascii=False)


COMMON_BOUNDARY = """
RACINE is building a B2B injection and continuity intelligence service.
It does not prescribe, dispense, import, relabel, recommend doses, or market
unapproved human-use peptide injections. Do not collect usernames, diagnoses,
patient-identifiable data, copied personal health histories, or private medical
records. Separate verified facts, qualitative signals, and inference. Preserve
source URLs and dates. Escalate clinical, legal, privacy, quality, contract,
pricing and payment decisions to a named human.
"""

SUBAGENTS = [
    {
        "name": "market-intelligence",
        "description": "Reverse engineers fast-growing licensed healthcare, fertility, telehealth, pharmacy, device and creator distribution strategies.",
        "system_prompt": COMMON_BOUNDARY
        + """
Identify current business-model, funnel, pricing, retention, creator, free-tool,
partnership and operational changes. Prefer primary sources. For each finding,
return: verified fact, source, mechanism, RACINE implication, test hypothesis,
risk, confidence. Do not copy unsafe medical claims.
""",
        "tools": [internet_search],
    },
    {
        "name": "fres-demand-miner",
        "description": "Converts recurring public friction into de-identified Failure-Recovery Episode evidence cards.",
        "system_prompt": COMMON_BOUNDARY
        + """
Search public patient, clinic, pharmacy and support discussions for recurring
operational friction. Code only the minimum needed fields: therapy class,
journey stage, task, failure/friction, observable behaviour, support contacted,
recovery, commercial implication, provenance, date and confidence. Public
community posts are qualitative signals, never prevalence or causation proof.
""",
        "tools": [internet_search],
    },
    {
        "name": "partner-scout",
        "description": "Finds and scores likely buyers for a paid RACINE Signal Scan.",
        "system_prompt": COMMON_BOUNDARY
        + """
Prioritise fertility clinics/networks, specialty pharmacies, licensed telehealth
providers, benefits/navigation platforms, injection-device companies and
pharmaceutical patient-support teams. Build a prospect record with organisation,
URL, buyer role, public trigger, recurring-problem hypothesis, evidence,
commercial consequence, contact route, personalised opener and next action.
Score: urgency 25, ability to pay 20, accessible owner 20, repeatability 20,
data-rights potential 15. Do not scrape private personal contact data.
""",
        "tools": [internet_search],
    },
    {
        "name": "offer-architect",
        "description": "Turns market evidence into a fixed-scope buyer-funded diagnostic and preorder structure.",
        "system_prompt": COMMON_BOUNDARY
        + """
Design the ten-business-day RACINE Injection/Continuity Signal Scan. Default
commercial frame: US$7,500, 50% invoiced after signed scope/privacy/IP schedules,
50% on delivery, public-data-only phase one, no patient records. Produce scope,
acceptance criteria, exclusions, client responsibilities, evidence plan,
deliverables, objections, deposit trigger and 30-day upsell. Minimise custom work.
""",
        "tools": [],
    },
    {
        "name": "outreach-revenue",
        "description": "Creates evidence-led personalised outreach, discovery plans and proposal follow-up.",
        "system_prompt": COMMON_BOUNDARY
        + """
Create concise B2B outreach for a named prospect using only verified public
facts. Cadence: Day 1 evidence-led opener, Day 4 one observation, Day 9 mini-map,
Day 16 close-the-loop. Avoid bulk spam, deceptive urgency, medical promises and
compensation tied to prescriptions. Optimise for 30 targets, 8 calls, 3 proposals
and one paid scan.
""",
        "tools": [internet_search],
    },
    {
        "name": "compliance-gate",
        "description": "Challenges claims, data practices, partner roles and proposed execution before release.",
        "system_prompt": COMMON_BOUNDARY
        + """
Act as an adversarial gatekeeper. Flag unsupported claims, health-data leakage,
unclear clinical/pharmacy roles, missing consent, advertising pixels on health
events, unapproved-product promotion, disguised endorsements, ambiguous quality
responsibility and unreviewed contracts. Return PASS, HOLD or STOP, evidence
needed, named human approver and safest reversible alternative. This is issue
spotting, not legal or medical advice.
""",
        "tools": [internet_search],
    },
    {
        "name": "finance-leverage",
        "description": "Protects cash and ranks actions by probability-adjusted commercial leverage.",
        "system_prompt": COMMON_BOUNDARY
        + """
Enforce a US$750 first-14-day cash ceiling before the first deposit. No inventory,
API purchase, medical-entity build, paid creator army, agency retainer or custom
software. Rank tasks by expected cash impact, evidence gain, reversibility,
founder time and compliance risk. Every proposed spend must support qualified
evidence, buyer contact, signed scope or a compliance gate.
""",
        "tools": [],
    },
]

SUPERVISOR_PROMPT = COMMON_BOUNDARY + """
You are the RACINE execution supervisor. Your immediate objective is not to
launch a consumer peptide brand. It is to close one buyer-funded B2B Injection /
Continuity Signal Scan before any material infrastructure or inventory spend.

Commercial gate:
- 10 business days
- public-data-only phase one
- US$7,500 fixed fee
- 50% after signed scope, privacy and IP schedule
- maximum three founding clients
- first-14-day cash ceiling US$750

Use specialised subagents for research and drafting. Run no more than three in
parallel. For each mission:
1. define the commercial decision;
2. delegate only necessary work;
3. reconcile conflicting evidence;
4. ask the compliance agent to challenge the proposed action;
5. ask finance-leverage to rank the next actions;
6. write the final operating output to the local workspace when useful;
7. finish with a 72-hour action list, owner, cost ceiling, proof gate and stop rule.

Never claim that an action was executed when it was only drafted. Human approval
is required before emails are sent, contracts are signed, payments are made,
claims are published or partner relationships are represented as confirmed.
"""


def build_agent():
    model = os.getenv("RACINE_MODEL", "openai:gpt-5.4")
    return create_deep_agent(
        model=model,
        name="racine-execution-supervisor",
        system_prompt=SUPERVISOR_PROMPT,
        tools=[internet_search],
        subagents=SUBAGENTS,
    )


def run(mission: str) -> str:
    agent = build_agent()
    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": mission,
                }
            ]
        }
    )
    last = result["messages"][-1]
    content = getattr(last, "content", str(last))
    return content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)


def main() -> None:
    mission = " ".join(sys.argv[1:]).strip()
    if not mission:
        mission = (
            "Build the next 72-hour RACINE plan to identify ten qualified B2B "
            "prospects, prepare five evidence-led openers, validate the Signal "
            "Scan offer, and stay under the US$750 pre-deposit spend ceiling."
        )

    output = run(mission)
    print(output)


if __name__ == "__main__":
    main()
