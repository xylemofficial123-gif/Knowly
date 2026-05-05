# Xylem — Product Pitch

> Living institutional brain for company knowledge.
> Demo target: 10–12 min · Audience: leadership / founders / product

---

## 30-second pitch (memorize this)

> "Every team re-asks the same questions every quarter. 'Why didn't we go with Adyen?' 'What did we decide about the auth migration?' Today the answer is 'check the wiki' — it's outdated — or 'ask Krithin' — he's on PTO. **Xylem is the company's memory.** It ingests Slack, Drive, ClickUp, and meeting transcripts; extracts decisions, rationale, and trade-offs; and answers any question with citations in under 8 seconds. It also pushes back — when someone re-opens a settled debate, Xylem replies in the thread with the original decision and the reason."

That's the whole product in three sentences. Lead with it.

---

## The pain → solution narrative

Open the demo by **naming the problem**, not the product.

| Pain (everyone feels this) | What Xylem does |
|---|---|
| "I asked the same question twice" | Catches it before you ask — Anti-Amnesia alert |
| "The doc is somewhere in Drive" | Indexed, semantic search, sub-10s answer |
| "Old decisions get re-opened" | Drift detection + re-litigation alerts |
| "New hires drown" | Acronym auto-define, decision timeline |
| "Docs go stale" | Freshness score + feedback retraining |

Frame the problem **before** opening the app. People need to feel the cost first.

---

## Demo flow — 5 acts (10–12 min)

### Act 1 — Open with pain (1 min)
Don't show the app yet. Show a screenshot or open a real Slack thread.

> "Here's a thread from our #general channel last quarter. Three people are debating whether to switch payment providers. The same debate happened in Q1. Same conclusion. Five engineer-hours, repeated. This isn't a Slack problem — it's a memory problem. **Companies don't remember.** I built Xylem so they can."

### Act 2 — The hero moment (2 min)
Open the chat. Type **one** pre-tested query. Don't improvise.

**Use this exact query:**
```
Why did we choose Stripe over Adyen?
```

When the answer renders:
- Read **one sentence** aloud (the rationale)
- Click a citation badge → it opens the source

> "Eight seconds. Cited. Names the people involved. Captures the rationale. This single answer covers three of the PRD's core features: semantic search, decision extraction, and synthesized summaries."

**Don't talk over the answer rendering.** Let people read it.

### Act 3 — The connective tissue (2 min)
Click sidebar → **Knowledge graph** → toggle to **Mind map**.

Wait 5 seconds. Let them see the radial layout in silence.

> "Every project, person, tool, and acronym mentioned across Slack, Drive, ClickUp — Xylem links them automatically. If I ask about 'Atlas', it doesn't just search for the word — it pulls the Slack thread, the spec doc, and the ClickUp task that all reference Atlas, even when none of them used the same wording."

Hover **one** entity to show the popup. **Don't deep-dive.**

> "60 entities, 200 cross-source connections — built passively from yesterday's data. The PRD calls this 'the connective tissue.' This is the part most knowledge tools fundamentally don't do."

### Act 4 — Anti-amnesia (2 min)
Two micro-demos:

**(a) Acronym auto-define** — type:
```
What is ICP and how does it relate to our product?
```
Point at the answer's first paragraph: definition is auto-injected.

> "I never asked for a definition. The system noticed an acronym and added it to the answer."

**(b) Re-litigation alert** — show the Decision Log (`/decisions`).

> "Seventeen decisions, all active. Every one has its rationale captured. If three months from now someone in Slack asks 'should we revisit Stripe?', Xylem replies in the thread: 'You decided Stripe in May. Reason: developer velocity. Has new data emerged?' We're not just answering questions — we're preventing them."

> ⚠ **Pre-trigger before the demo:** post a Slack message in a connected channel matching a known decision. Wait for the alert. Screenshot it. Show the screenshot here. **Don't try to live-trigger** — Guardian latency is unpredictable.

### Act 5 — Numbers that prove it (1 min)
Open **Admin → Metrics → PRD Success Metrics**.

Read the three cards aloud:

> "**100% decision adherence** — 17 of 17 decisions still active.
> **7.7-second average retrieval** — PRD target was 30 seconds.
> **Deflection rate** climbs as the team starts using it — every Slack message is checked against prior context."

Close on this. Numbers > narrative for execs.

---

## Bonus: things to mention that other demos forget

These are PRD requirements that ARE built and that **decision-makers always ask about**:

| Feature | One-liner to drop |
|---|---|
| **Freshness Score + thumbs-up/down feedback** | "Outdated docs get auto-deprioritized. Users can flag bad answers — chunks get re-ranked." |
| **Decision reversal history** | "When a decision flips, we keep the old record linked. The PRD calls this 'Living History' — past versions never disappear." |
| **No-Index Zones** | "Admins can mark Slack channels or Drive folders as off-limits — HR, M&A, salary discussions." |
| **Audit logs** | "Admins see every query. PRD specifically calls this out as anti-espionage — no employee silently querying 'layoff plans'." |
| **Strict ACL mirroring** | "If you can't see the doc in Drive, the agent won't summarize it for you. Permission-aware end to end." |

Sprinkle these into Q&A — don't pile them up in one slide.

---

## PRD coverage scorecard

> **25 of 26 PRD requirements fully implemented · 1 partial · 0 missing.**

| PRD section | Done | Partial | Missing |
|---|---|---|---|
| 1. Omni-Channel Ingestion | 2/3 | 1 (sources scoped to our stack) | 0 |
| 2. Decision Extraction | 3/3 | — | — |
| 3. Oracle (Query Interface) | 3/3 | — | — |
| 4. Anti-Amnesia | 2/2 | — | — |
| 5. Onboarding Time Machine | 2/2 | — | — |
| Success Metrics | 3/3 | — | — |
| Risk Mitigations | 3/3 | — | — |
| Interaction Principles | 4/4 | — | — |
| Privacy & Ethics | 3/3 | — | — |

**The one remaining partial is a scoping decision, not a gap:**

1. **Connective Tissue sources.** PRD lists 10 sources (Slack/Teams/Notion/Confluence/Drive/SharePoint/Jira/Linear/Zoom/Meet). We integrated the **5 that our company actually uses** — Slack, Drive, Calendar, Meet, ClickUp. The architecture is source-agnostic — adding any of the others is one ingestion script.

**Onboarding Time Machine — both halves now live:**
- **Acronym Buster** ships in the Oracle: any query containing internal acronyms (ICP, GTM-Q3, etc.) auto-injects a definition glossary into the answer.
- **Topic Catch-Up** ships as the **New Joiner** screen: admins create projects via the Groups tab; project cards render dynamically per user (only the projects they're a member of); clicking a card fires an ACL-scoped briefing with cited decisions, owners, and rationale; brand-new joiners with no group memberships see a clear empty state ("ask an admin to add you to a team"). Routing avoids the half-baked OnboardingAgent prompt and uses the reliable Research agent instead.

State openly when asked. Don't apologize.

---

## Anticipated Q&A

| Likely question | Best answer |
|---|---|
| "Where does the data sit? Is it secure?" | Postgres + Qdrant on Railway, all behind Clerk auth. ACL-filtered per user end to end — if you can't see the source doc, you can't see the answer. |
| "What about hallucinations?" | Every claim cites a source. If nothing matches, the agent says exactly: 'I cannot find a record of this in the company's knowledge base.' Never invents. We can demo this. |
| "How is this different from ChatGPT or Notion AI?" | Two things: (1) cross-source — it's the only one that pulls Slack + Drive + ClickUp into one cited answer. (2) decision-aware — it knows what was decided, what was reversed, what's a draft vs final. ChatGPT doesn't know your company's history. |
| "What's the cost?" | $0 today — runs on free tiers (Gemini, Groq, OpenRouter). At scale, ~10c per 1,000 queries on paid models. The architecture is cost-flexible by design. |
| "What if a key person leaves?" | Standard FastAPI + Next.js + Postgres. PROJECT_STATUS.md tracks every architectural decision. Anyone with backend experience picks it up in a day. |
| "Can it be wrong about decisions?" | Yes, and that's why every decision is editable, reversible, and shows the source it was extracted from. We also auto-flag low-confidence extractions for human review before saving. |
| "How does it handle private content?" | No-Index Zones — admins mark channels/folders as off-limits. Combined with ACL mirroring, the agent simply refuses to ingest or surface those. |
| "Will this replace docs?" | No — it's the layer above docs. Docs are still the source of truth. Xylem makes them findable + connects them. |

---

## Pre-flight checklist (run 30 min before demo)

- [ ] **Warm up every tab.** Cold-start latency on Vercel/Railway is ugly. Open `/`, `/graph`, `/decisions`, `/activity`, `/ingest` once.
- [ ] **Run all 3 demo queries** with the actual account. If any flakes, swap the query.
- [ ] **Pre-trigger a Guardian alert** by posting in a connected Slack channel. Screenshot the alert. Use it as backup for Act 4(b).
- [ ] **Take fallback screenshots** for: mind map, citations, decision log, metrics tab. Have them in a folder. Network dies, you keep going.
- [ ] **Browser zoom 110–120%** so people in the back can read.
- [ ] **Disable notifications.** No accidental Slack popups.
- [ ] **Close all unrelated tabs.** Tab-switching during the demo is amateurish.
- [ ] **Have PROJECT_STATUS.md open in another window** for any deep-dive question.
- [ ] **Test on the actual room's display.** Colors and contrast change.
- [ ] **Charge your laptop.**

---

## What NOT to do

- ❌ **Don't show the architecture diagram first.** They don't care until they care. Save it for slide-after-demo or Q&A.
- ❌ **Don't show ingestion/upload UI.** It's plumbing. Boring.
- ❌ **Don't show the entire feature list.** Pick 5 moments. Cut everything else.
- ❌ **Don't ask the Oracle a question you haven't tested.** LLM answers can flake. Pre-validate every query you'll demo.
- ❌ **Don't show empty states.** If a tab looks empty, skip it.
- ❌ **Don't apologize for partials.** The 2 gaps are scoping decisions, not failures. State them as facts.
- ❌ **Don't read off slides.** This is a product, not a slide deck. Run the product.
- ❌ **Don't go over time.** Better to leave them wanting more than to bore them with everything.

---

## If you only have 5 minutes

Cut to: **Act 2 + Act 3 + Act 5**.

- Act 2 — Stripe/Adyen query (the hero answer)
- Act 3 — Mind map (the visual stunner)
- Act 5 — Metrics dashboard (the proof)

Skip the pain narrative; skip Anti-Amnesia. Those three acts tell the whole story.

---

## The closing line (memorize this)

> "Companies forget. Xylem makes them remember. Every decision, every rationale, every conversation — searchable, cited, and instantly accessible. **The PRD listed 26 requirements. 25 are live, 1 is a scoping decision — integrations our company doesn't use. The product is in production today.**"

Pause. Then take questions.

---

## Quick reference — production URLs

- Frontend: `https://project-zi57a.vercel.app`
- Backend: `https://knowledge-system-production.up.railway.app`
- Repo: `https://github.com/xylemofficial123-gif/Knowly`

## Quick reference — the killer numbers

- **75 documents** ingested across Slack + Drive + Uploads
- **65 searchable chunks** indexed in Qdrant
- **17 decisions** extracted automatically
- **60 entities** in the knowledge graph
- **200 cross-source links** between entities
- **7.7 seconds** average retrieval (PRD target: under 30s)
- **100%** decision adherence
- **0** console errors during E2E test of all 5 features

---

# PART 2 — Capstone Deck (10 slides)

> Use this section for the **Seedling Labs capstone presentation** (slide-based, judges in the room, ~10 min). The Part 1 demo flow above is for leadership/founder pitches. Part 2 is structured around storytelling + persona, mapped to the official 10-slide template.

---

## Storytelling strategy

Judges remember **stories, not architecture**. Open with a human, close with the same human transformed.

**Rule of thumb:**
- Open with a 30-second story (Slide 4)
- Frame the demo as that person's day (Slide 6)
- Close by bringing them back, transformed (Slide 9)

Don't introduce multiple personas — one is enough. Don't over-illustrate — 3 lo-fi images carry the entire arc.

---

## The persona — Riya, the new joiner

```
Name:     Riya Sharma
Role:     Software Engineer, Week 2 at Seedling Labs
Age:      24
Goal:     Ship her first feature without bothering the team
Pain:     "Why did we pick Postgres over Mongo?"
          "What does 'GTM-Q3' mean?"
          "Where's the onboarding doc?"
          → She asks Slack, gets ignored or vague answers
          → Senior engineers get 15 pings/day from new joiners
Quote:    "I feel like I'm interrupting everyone just to do my job."
```

**Why Riya works:**
- Onboarding pain is universally relatable — every judge has been a new joiner
- Hits all 5 PRD features naturally (search, decisions, acronyms, ghost docs, RBAC)
- Lets you frame Xylem as "Riya's onboarding buddy" not "an AI tool"

---

## Lo-fi illustrations — 3 images, same character

**Why lo-fi:** flat, hand-drawn illustrations (Notion / Linear / Excalidraw style) feel intentional, don't compete with the architecture diagram, and are more emotionally engaging than corporate stock photos. Avoid realistic AI photos and 3D renders — they look generic.

### Base style prompt (use for all 3 images for visual consistency)

```
A flat lo-fi illustration in Notion / Linear / Excalidraw style.
Hand-drawn aesthetic with soft pastel colors (sage green, dusty
peach, cream, slate). Thin uneven outlines, no shading, no
gradients. Friendly minimalist style. Single subject per image,
generous whitespace, off-white background (#FAF9F6).

Character: a young South Asian woman in her mid-20s named Riya.
Casual hoodie, glasses, laptop nearby. Same face/outfit across
all images for consistency.

[CHANGE THE SCENE BELOW PER IMAGE]
```

### Image 1 — "Overwhelmed Riya" (Slide 4 — Problem)
```
Scene: Riya sitting at a desk with her laptop open, looking
confused and slightly stressed. Around her head, 5–6 small
floating speech bubbles with question marks and small icons
of Slack, Drive, ClickUp, Calendar. A small thought bubble
saying "?". Cluttered floating papers. Mood: lost, overwhelmed.
```

### Image 2 — "Riya discovering Xylem" (Slide 6 — Demo intro)
```
Scene: Riya at the same desk, now looking curiously at her
laptop screen which glows softly. A small mascot character
("Xylem") next to the screen — a friendly minimalist creature,
maybe a small leaf or plant sprite (matching the "Seedling Labs"
theme). Speech bubble from Xylem: "Ask me anything."
Mood: curious, hopeful.
```

### Image 3 — "Confident Riya" (Slide 9 — What Next)
```
Scene: Riya at the same desk, smiling, headphones on, laptop
open showing a checkmark. The Xylem mascot beside her. The
floating question marks from Image 1 are now floating away
or replaced with small green checkmarks. Mood: confident,
shipping, calm.
```

---

## Slide-by-slide content + speaker script

> Format per slide: **what's on the slide**, then the **opener** (first sentence), the **body** (what to say), and the **closer** (transition to next slide). Memorize the opener and closer of each — improvise the body.

---

### Slide 1 — Instructions
Skip. Rename file to `Agent-Xylem-SeedlingLabs-2026`.

---

### Slide 2 — Team

**On slide:** Team name, member names, photos, one-line tagline.

**Tagline:** *"Building organizational memory for Seedling Labs."*

**Opener (10 sec):**
> "We're team Xylem. We built an AI agent that gives companies a memory."

**Closer:**
> "Let me introduce you to the agent itself."

---

### Slide 3 — Agent Name & Mascot

**On slide:** "Xylem" + mascot illustration (the leaf sprite from Image 2).

**Opener (15 sec):**
> "Meet Xylem. Named after the part of a plant that carries water and nutrients to every cell — Xylem carries knowledge to every person in your company."

**Closer:**
> "But before we show you what it does, let me show you why it exists."

---

### Slide 4 — Problem Statement *(STORY OPENS HERE)*

**On slide:**
- Image 1 (Overwhelmed Riya) on the left
- 3 short pain bullets on the right:
  - "Repeated questions — same answers, different person"
  - "Lost decisions — buried in old Meet recordings"
  - "Source sprawl — knowledge split across 5 tools"

**Opener (30 sec — memorize this):**
> "Meet Riya. She joined Seedling Labs two weeks ago. By her fifth day she's asked Slack 23 questions, gotten 6 vague answers, and 3 senior engineers are starting to dodge her DMs. She's not slow — she just doesn't have the context that lives in your Drive, your Meet recordings, your decision threads from 6 months ago."

**Body:**
- Riya isn't unusual — every new joiner is Riya
- Senior engineers lose 1–2 hours/day to repeated context-setting
- Decisions made 6 months ago get re-litigated because nobody remembers the rationale
- The knowledge exists — it's just unfindable

**Closer:**
> "We built Xylem so Riya — and every Riya after her — can ship on Day 5 instead of Day 15."

---

### Slide 5 — Agent Architecture

**On slide:** the minimalist architecture diagram (4 zones: Sources → Ingest → Agent Core → LLM, with Frontend column on right).

**Opener (10 sec):**
> "Here's how it works under the hood — five layers, all running on free tiers today."

**Body (90 sec — walk top to bottom):**
1. **Sources:** Drive, Meet, Calendar, Slack, ClickUp — ingested with ACL preservation
2. **Ingest pipeline:** Celery workers chunk, tag with permissions, embed locally with bge-small (zero API cost)
3. **Storage:** Qdrant for semantic search, Postgres for metadata + entity graph, Redis for the queue
4. **Agent core:** Router dispatches to Research, Onboarding, or Guardian agents — plus Knowledge Graph and Acronym Buster modules
5. **LLM fallback:** Gemini → Groq → OpenRouter (free tier, $0 cost)
6. **Frontend:** Next.js + Clerk auth with 3-tier RBAC (Admin / Team Lead / Member)

**Closer:**
> "Now let's see Riya use it."

---

### Slide 6 — Agent Demo *(STORY CONTINUES)*

**On slide:** Image 2 (Riya discovering Xylem) on the left, demo placeholder (live or video) on the right.

**Opener (15 sec):**
> "It's Riya's Monday morning, week three. Watch what she does instead of pinging Slack."

**Demo flow (5 acts, ~5 min — frame each as a Riya question):**

1. **Riya asks: "Why did we pick Stripe over Adyen?"** → Oracle returns cited answer in 8 sec
2. **Riya asks: "What is ICP?"** → Acronym Buster auto-injects definition
3. **Riya opens the Knowledge Graph** → sees how Atlas, Stripe, ICP all connect across Slack/Drive/ClickUp
4. **A meeting ends** → Xylem DMs the lead in Slack: "Should we record these decisions?" (ghost documentation)
5. **Riya logs in as a member** → only sees content her ACL permits — no leaks

**Closer:**
> "Five features, one continuous flow. Now let's look at the numbers."

---

### Slide 7 — Test Results & Metrics

**On slide:** screenshot of Admin → Metrics dashboard, plus a test summary box.

**Opener (10 sec):**
> "We didn't just build it — we measured it against the PRD's own success criteria."

**Body — read these out:**
- **Deflection Rate** — % of queries answered without human follow-up
- **Decision Adherence** — 17 of 17 decisions still active = **100%**
- **Retrieval Time** — 7.7 seconds average (PRD target: 30 seconds)
- **E2E test** — all 5 PRD features verified end-to-end with Playwright in production
- **Cost** — **$0** in production today (free LLM tier + local embeddings)

**Closer:**
> "These metrics ship as a real admin dashboard, not a slide. Here's what we learned building it."

---

### Slide 8 — Learnings & Key Takeaways

**On slide:** 4–5 punchy takeaways, no images.

**Opener (10 sec):**
> "Five things we learned that we wish someone had told us on day one."

**Takeaways:**
1. **Free-tier-first works.** Gemini → Groq → OpenRouter handles real load at $0 — don't reach for paid APIs until you've hit a wall
2. **ACL at ingest, not at query.** Preserving permissions when documents enter the system is 10× simpler than enforcing them at retrieval time
3. **Hybrid extraction beats pure LLM.** Gazetteer-first entity linking (regex) + LLM fallback was 50× cheaper than LLM-per-chunk
4. **Per-service env scoping bites.** Railway worker is a separate service from API — every secret has to be set twice. We learned this the hard way
5. **One persona > five features.** When we framed the product around "Riya's onboarding," every design decision got easier

**Closer:**
> "And here's where we go next."

---

### Slide 9 — What Next & Help Needed *(STORY CLOSES HERE)*

**On slide:** Image 3 (Confident Riya) on the left, two columns on the right:

**What's next:**
- Move from free LLM tier → paid (Claude/GPT) for production accuracy
- Add Notion + Jira ingestion
- Proactive briefings ("you have a meeting in 30 min — here's relevant context")
- Per-group knowledge graphs

**Help needed from Seedling Labs:**
- Production Clerk org + SSO setup
- Paid LLM API budget for production scale
- Pilot users across teams to validate Decision Adherence in the wild
- Compliance review for storing Meet transcripts long-term

**Opener (15 sec — bring Riya back):**
> "It's three months later. Riya shipped her first feature on Day 5 instead of Day 15. She hasn't pinged a senior engineer in two weeks. She's now answering questions for the *next* new joiner — through Xylem."

**Closer:**
> "That's what we want for every team at Seedling Labs."

---

### Slide 10 — Thank You

**On slide:** "Thank You" + project URL + GitHub repo + your contact info + the mascot.

**Closing line (memorize this):**
> "Companies forget. Xylem makes them remember. Every decision, every rationale, every conversation — searchable, cited, instantly accessible. The PRD listed 26 requirements. 25 are live, 1 is a scoping decision — integrations our company doesn't use. The product is in production today."

Pause. Take questions.

---

## Pacing reference (10-min talk)

| Slide | Time | Cumulative |
|---|---|---|
| 2 — Team | 10 sec | 0:10 |
| 3 — Mascot | 15 sec | 0:25 |
| 4 — Problem (Riya intro) | 60 sec | 1:25 |
| 5 — Architecture | 90 sec | 2:55 |
| 6 — Demo | 5 min | 7:55 |
| 7 — Metrics | 60 sec | 8:55 |
| 8 — Learnings | 45 sec | 9:40 |
| 9 — What Next + Riya close | 60 sec | 10:40 |
| 10 — Thank you | 10 sec | 10:50 |

Aim for 10:30 spoken — leaves ~5 min for Q&A in a 15-min slot.

---

## Storytelling checklist

- [ ] Riya introduced on Slide 4 with Image 1
- [ ] Demo on Slide 6 framed as Riya's Monday, with Image 2
- [ ] Riya transformation closes Slide 9 with Image 3
- [ ] Same character, same outfit, same style across all 3 images
- [ ] Speaker openers + closers memorized (not body text)
- [ ] No second persona introduced
- [ ] Pause after the closing line on Slide 10 — let it land
