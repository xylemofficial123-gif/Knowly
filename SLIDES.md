# Xylem — Capstone Slide Content + Image Prompts

> Final slide-ready content for the 10-slide capstone deck, plus every image prompt you'll need for visuals. Generated after the product hit 25/26 PRD coverage with drift sweep, Drive ACL inheritance, scoped Quick Onboarding, and full demo seed data.
>
> Use the slide content directly in the template at `Copy of Capstone Project Template.pptx` (rename to `Agent-Xylem-SeedlingLabs-2026`).

---

# Part 1 — Slide-by-slide content

## SLIDE 1 — INSTRUCTIONS
Skip. Renames file only.

---

## SLIDE 2 — TEAM

**Title:** Team Xylem

**Subtitle:**
> Building organizational memory for Seedling Labs

**Body:** [Photo + Sachin Kurup] · [Teammate photo + name]

**Speaker notes (10s):**
> *"We're team Xylem. We built an AI agent that gives companies a memory."*

---

## SLIDE 3 — AGENT NAME

**Title:** Xylem

**Subtitle:**
> The agent that carries your company's knowledge

**Visual:** Mascot illustration (see image prompt 5)

**One-liner under mascot:**
> Named after the plant tissue that carries water and nutrients to every cell — Xylem carries knowledge to every person.

**Speaker notes (15s):**
> *"Meet Xylem. Before we show you what it does, let me show you why it exists."*

---

## SLIDE 4 — PROBLEM STATEMENT *(STORY OPENS)*

**Title:** Companies forget. People pay the price.

**Visual:** Image 1 — Overwhelmed Riya (left side)

**Three pain points (right column):**
- 🔁 **Repeated questions** — same answer, different person, every quarter
- 📉 **Lost decisions** — *"Why did we pick Postgres?"* buried in a Meet from 6 months ago
- 🗂 **Source sprawl** — knowledge split across Slack, Drive, Calendar, Meet, ClickUp

**Bottom callout (large, attention-grabbing):**
> *"Riya joined two weeks ago. By Day 5, she's pinged 23 questions in Slack, gotten 6 vague answers, and senior engineers are starting to dodge her DMs."*

**Speaker notes (60s — memorize this opening):**
> *"Meet Riya. She's two weeks in. By her fifth day she's asked 23 questions and three engineers are dodging her DMs. She's not slow — she just doesn't have the context that lives in your Drive, your Meet recordings, your Slack threads from six months ago. Senior engineers lose 1–2 hours a day to repeated context-setting. Decisions get re-litigated because nobody remembers the rationale. We built Xylem so Riya — and every Riya after her — can ship on Day 5 instead of Day 15."*

---

## SLIDE 5 — AGENT ARCHITECTURE

**Title:** Xylem — Architecture Overview

**Visual:** Generated architecture diagram (see image prompt 4)

**4 callouts beneath the diagram:**
- **5 sources** ingested with native ACL: Slack · Drive · Meet · Calendar · ClickUp
- **Multi-agent core**: Router → Research / Onboarding / Guardian agents
- **Local embeddings** (BAAI/bge-small, 384d) — chunk content never leaves our infra
- **Free-tier LLM fallback chain**: Gemini → Groq → OpenRouter (production cost: $0)

**Bottom strip (small text):**
Railway · Vercel · Postgres · Qdrant · Redis · Clerk Auth

**Speaker notes (90s):**
> *"Five layers. Sources at the top — five connectors with ACL preservation. Ingest pipeline does chunking and local embedding. Storage is Qdrant for semantic search and Postgres for ACL, decisions, entity graph. The agent core routes to Research, Onboarding, or Guardian based on query type. LLM tier is a three-provider free-tier fallback. Frontend is Next.js with Clerk auth — three-tier RBAC: Admin, Team Lead, Member."*

---

## SLIDE 6 — AGENT DEMO *(STORY CONTINUES)*

**Title:** Riya's Monday morning

**Visual:** Image 2 — Riya discovering Xylem (left, smaller)

**Demo flow (right side, numbered):**
1. **Riya asks** *"Why Stripe over Adyen?"* → 8-second cited answer with 4 sources
2. **Riya asks** *"What is ICP?"* → Acronym Buster auto-injects definition inline
3. **A new decision drifts** → Drift sweep flags weekly vs bi-weekly oncall as contradictory
4. **Riya opens Quick Onboarding** → only Sprout card (her team); click → instant briefing
5. **A meeting ends** → Xylem DMs the host: *"Should we record these decisions?"*

**Caption beneath:**
> Five PRD features in one continuous user journey.

**Speaker notes (5 min — live demo):**
> *"It's Riya's Monday, week three. Watch what she does instead of pinging Slack."*
> Then walk through the 5 demo moments above. Pause after each so the answer renders.

---

## SLIDE 7 — TEST RESULTS & METRICS

**Title:** Measured against the PRD's own success criteria

**Top row — three metric cards:**

| Metric | Value | PRD target |
|---|---|---|
| **Avg retrieval time** | 7.7s | <30s ✅ |
| **Decision adherence** | 100% | — ✅ |
| **Cited answers rate** | 100% | 100% ✅ |

**Bottom row — proof bullets:**
- ✅ **5 PRD features** verified end-to-end via Playwright in production
- ✅ **25 / 26 PRD requirements** fully implemented
- ✅ **$0 production cost** (free LLM tier + local embeddings)
- ✅ **Drive ACL inheritance** — file permissions enforced at ingestion
- ✅ **Decision drift sweep** — periodic contradiction detection across the full log

**Speaker notes (60s):**
> *"We didn't just build it — we measured it. Retrieval at 7.7 seconds against the PRD's 30-second target. 100 percent of answers carry citations or refuse. 25 of 26 PRD requirements live; the one outstanding is a scoping decision — sources we don't use. Today's production cost: zero dollars."*

---

## SLIDE 8 — LEARNINGS & KEY TAKEAWAYS

**Title:** Five things we learned the hard way

**Bullet list:**
1. **Free-tier-first works.** A 3-provider fallback chain (Gemini → Groq → OpenRouter) handles real load at $0 — don't reach for paid APIs until you've proven you need them.
2. **ACL at ingest, not at query.** Preserving permissions when documents *enter* the system is 10× simpler than enforcing them at retrieval time.
3. **Hybrid extraction beats pure LLM.** Gazetteer-first entity linking + LLM fallback was 50× cheaper than per-chunk LLM extraction.
4. **Per-service env scoping bites.** Railway worker is a separate service from the API — every secret has to be set twice. We learned this when the worker silently produced zero results.
5. **One persona > five features.** When we framed the product around Riya's onboarding, every design decision got easier.

**Speaker notes (45s):**
> *"Five things we wish someone had told us. Free tier handles real workloads if you stack three providers. ACL at ingest beats ACL at query. Hybrid entity extraction beats pure LLM. Watch your per-service env scoping — Railway bit us. And: one persona unlocked every design decision."*

---

## SLIDE 9 — WHAT NEXT & HELP NEEDED *(STORY CLOSES)*

**Title:** What we'd build next — and what we need

**Visual:** Image 3 — Confident Riya (left side)

**Two columns (right side):**

**What's next:**
- Move free → paid LLM tier (Claude Haiku) for production reliability
- Real-time Slack ingestion via Events API (currently 30-min sync)
- Proactive briefings — *"You have a meeting in 30 min — here's relevant context"*
- Eval harness across all agents to catch citation drift before deploy
- Drift-sweep history dashboard with admin acknowledgment workflow

**Help from Seedling Labs:**
- Production Clerk org + SSO setup
- Paid LLM API budget for production scale (~$30–50/month at our usage)
- Pilot users across teams to validate Decision Adherence in the wild
- Compliance review for storing Meet transcripts long-term

**Bottom callout (large):**
> *"It's three months later. Riya shipped her first feature on Day 5 instead of Day 15. She's now answering questions for the next new joiner — through Xylem."*

**Speaker notes (60s — bring Riya back):**
> *"It's three months later. Riya shipped her first feature on Day 5. She hasn't pinged a senior engineer in two weeks. She's now answering questions for the next new joiner — through Xylem. To get there for every team at Seedling Labs, we need paid LLM budget, real-time Slack events, and pilot users to validate decision adherence at scale."*

---

## SLIDE 10 — THANK YOU

**Title:** Thank you

**Body (centered):**
- 🌐 Live: `https://project-zi57a.vercel.app`
- 💻 Repo: `https://github.com/xylemofficial123-gif/Knowly`
- 📧 Contact: Sachin.Kurup@leadsquared.com

**Mascot:** Bottom-right corner

**Closing line (memorize):**
> *"Companies forget. Xylem makes them remember. Every decision, every rationale, every conversation — searchable, cited, instantly accessible. The PRD listed 26 requirements. 25 are live, 1 is a scoping decision — integrations our company doesn't use. The product is in production today."*

**Pause. Take questions.**

---

# Part 2 — Pacing reference

| Slide | Time | Cumulative |
|---|---|---|
| 2 — Team | 10 sec | 0:10 |
| 3 — Mascot | 15 sec | 0:25 |
| 4 — Problem | 60 sec | 1:25 |
| 5 — Architecture | 90 sec | 2:55 |
| 6 — Demo | 5 min | 7:55 |
| 7 — Metrics | 60 sec | 8:55 |
| 8 — Learnings | 45 sec | 9:40 |
| 9 — What Next | 60 sec | 10:40 |
| 10 — Thank You | 10 sec | 10:50 |

**Target: 10:30 spoken.** Leaves ~5 minutes Q&A in a 15-minute slot.

---

# Part 3 — The 4 lines worth memorizing word-for-word

1. **Opener (Slide 4):**
   > *"Meet Riya. She's two weeks in. By her fifth day she's asked 23 questions and three engineers are dodging her DMs."*

2. **Transition into demo (Slide 5 → 6):**
   > *"Now let's see Riya use it."*

3. **Riya close (Slide 9):**
   > *"Three months later. Riya shipped her first feature on Day 5 instead of Day 15. She's now answering questions for the next new joiner — through Xylem."*

4. **Closing line (Slide 10):**
   > *"Companies forget. Xylem makes them remember. The PRD listed 26 requirements. 25 are live, 1 is a scoping decision. The product is in production today."*

Everything else: bullets are prompts; improvise around them. **Don't read off slides. Run the product.**

---

# Part 4 — Image prompts

## How to use this section

Generate each image with **Gemini Nano Banana** (or Imagen / DALL-E / Midjourney). For the three Riya illustrations, **use the same base style prompt** so the character looks consistent across slides 4 / 6 / 9. Generate them as a batch if your tool supports it.

If text labels come out garbled, generate WITHOUT text and add labels in Keynote / Google Slides yourself.

---

## 🖼️ Image 1 — Overwhelmed Riya (Slide 4 — Problem)

**Where:** Slide 4, left side, takes up ~40% of the slide

**Mood:** Lost, overwhelmed, slightly stressed but not despairing

**Prompt:**
```
A flat lo-fi illustration in Notion / Linear / Excalidraw style.
Hand-drawn aesthetic with soft pastel colors (sage green, dusty
peach, cream, slate). Thin uneven outlines, no shading, no
gradients. Friendly minimalist style. Off-white background (#FAF9F6).
Generous whitespace.

Subject: A young South Asian woman in her mid-20s named Riya. Casual
hoodie (sage green or oatmeal), round glasses, hair pulled back.
Sitting at a small desk with her laptop open in front of her.

Scene: Riya looks confused and slightly stressed, head tilted, one
hand on her temple. Around her head, 5–6 small floating speech
bubbles with question marks ("?") and tiny icons of Slack, Google
Drive, Calendar, ClickUp scattered around. A few loose paper sheets
floating mid-air. Subtle visual cue of "too much information."

Mood: lost, overwhelmed, but human and relatable — not despairing.

Negative prompt: realistic photo, 3D render, glossy, ornate,
cluttered, aggressive colors, dark, dramatic lighting.
```

---

## 🖼️ Image 2 — Riya discovering Xylem (Slide 6 — Demo)

**Where:** Slide 6, left side, slightly smaller than Image 1

**Mood:** Curious, hopeful, the moment of recognition

**Prompt:**
```
A flat lo-fi illustration in Notion / Linear / Excalidraw style.
Hand-drawn aesthetic with soft pastel colors (sage green, dusty
peach, cream, slate). Thin uneven outlines, no shading, no
gradients. Friendly minimalist style. Off-white background (#FAF9F6).
SAME CHARACTER as the previous Riya illustration — same hoodie,
glasses, hair, face — for visual continuity.

Scene: Riya at the same desk, now leaning slightly toward her
laptop screen which glows softly. She is looking curious, eyebrows
raised, a small smile starting. Beside the laptop screen, a small
mascot character labeled "Xylem" — a friendly minimalist plant or
leaf sprite (small green creature with two leafy arms, big simple
eyes, no scary features). The mascot has a small speech bubble that
reads "Ask me anything." in a clean sans-serif font. The previous
floating question marks are starting to settle / disappear.

Mood: curious, hopeful, the moment of recognition.

Negative prompt: realistic photo, 3D render, glossy, ornate,
cluttered, aggressive colors.
```

---

## 🖼️ Image 3 — Confident Riya (Slide 9 — What Next)

**Where:** Slide 9, left side

**Mood:** Confident, calm, shipping

**Prompt:**
```
A flat lo-fi illustration in Notion / Linear / Excalidraw style.
Hand-drawn aesthetic with soft pastel colors (sage green, dusty
peach, cream, slate). Thin uneven outlines, no shading, no
gradients. Friendly minimalist style. Off-white background (#FAF9F6).
SAME CHARACTER as the previous two Riya illustrations — same hoodie,
glasses, hair, face.

Scene: Riya at the same desk, smiling, headphones now on her ears,
sitting up straight. Laptop open, screen showing a small green
checkmark. The Xylem mascot from the previous illustration is beside
her, also looking content. The earlier floating question marks have
been replaced with small green checkmarks (✓) drifting away in the
background.

Mood: confident, calm, shipping. The visual contrast with Image 1
should be obvious — same person, same desk, opposite emotional
state.

Negative prompt: realistic photo, 3D render, glossy, ornate,
celebration confetti, exaggerated emotion.
```

---

## 🖼️ Image 4 — Architecture Diagram (Slide 5)

**Where:** Slide 5, fills most of the slide

**Mood:** Clean, technical, confident

**Prompt:**
```
A minimalist technical architecture diagram for an AI agent called
"Xylem". Style: ultra-clean, Stripe / Linear / Vercel aesthetic.
Pure white background. Thin 1px borders, no drop shadows, no
gradients. Generous whitespace between elements. Monochrome base
(slate gray #475569) with ONE accent color: emerald green (#10B981)
used only for the agent core. Typography: Inter, small caps for
layer labels, regular weight for nodes. Connector lines: thin,
straight, slate gray, with small arrowheads.

LAYOUT — vertical flow, 4 zones top to bottom, centered:

ZONE 1 — SOURCES (top)
  Single row of 5 small monochrome icons:
  Drive · Meet · Calendar · Slack · ClickUp
  Caption beneath: "ingestion with ACL preservation"

ZONE 2 — INGEST
  Horizontal pill: "Connectors → Chunker + ACL → Embeddings (bge-small,
  384d, local)"
  Below it, two small cylinders side by side: "Qdrant" and "Postgres"
  Tiny third cylinder offset right: "Redis"
  Caption: "Celery workers + Beat scheduler"

ZONE 3 — AGENT CORE (centerpiece, larger, emerald accent)
  Centered "Router" node at top.
  Three thin lines branching down to: "Research"  "Onboarding"  "Guardian"
  Two side modules connected to Router:
    Left: "Knowledge Graph"
    Right: "Acronym Buster"
  Caption: "FastAPI · Multi-Agent Orchestration"

ZONE 4 — LLM (bottom)
  Three small pills with arrows: "Gemini → Groq → OpenRouter"
  Caption: "free-tier fallback chain"

RIGHT SIDE COLUMN (parallel to zones 2-4):
  Three stacked outlined boxes:
    "Next.js 14"
    "Clerk · RBAC (Admin / Lead / Member)"
    "Chat · Graph · Admin"
  One arrow from this column into Router.

OUTPUT (bottom right exit arrow):
  "answer + [1][2] citations + Slack ghost-doc"

FOOTER (small centered text):
  "Railway · Vercel · Docker"

TITLE (top, large bold): "Xylem"
SUBTITLE (top, regular weight, slate): "Internal Knowledge & Decision Memory Agent"

Rules:
- No emojis, no 3D, no isometric, no shadows, no gradients.
- Maximum 12 visible boxes total.
- All text horizontal, never rotated.
- Whitespace is the design — let elements breathe.

Negative prompt: cluttered, dense, ornamental, 3D, glossy, shadows,
gradients, decorative, busy, crowded.
```

---

## 🖼️ Image 5 — Xylem Mascot (Slide 3, recurring on Slides 6 / 9 / 10)

**Where:** Slide 3 (large, central), Slide 6 / 9 (small, beside Riya), Slide 10 (bottom right corner accent)

**Mood:** Friendly, plant-themed, distinctive

**Prompt:**
```
A flat illustration of a friendly minimalist mascot character for
an AI knowledge agent called "Xylem". Style: hand-drawn lo-fi, in
the spirit of Notion / Linear / Duolingo's mascot. Soft pastel
colors. Thin uneven outlines. No 3D, no shading, no gradients,
no glossy effects. Off-white background (#FAF9F6).

Character description:
- A small plant sprite or stylized leaf creature, sage green color
  with hints of dusty peach in the cheeks
- Two simple leaf-shaped arms (or small twig arms with little
  leaves at the ends)
- Two big round simple eyes with a single white highlight pixel —
  friendly, alert, curious. NOT scary or uncanny.
- Small smiling mouth, no teeth
- Optional: tiny sprout or leaf growing from the top of its head
- Stands on small rounded feet or floats slightly above ground

Pose for slide 3 (the hero pose): standing facing forward, slight
wave with one arm raised, friendly welcoming posture.

Concept: it carries knowledge through the company the way real
xylem carries water and nutrients through a plant. Should look
like the character would be at home in a Notion sidebar or as a
cute company emoji.

Negative prompt: realistic, 3D, anime, scary, sharp teeth, uncanny
valley, photorealistic, glossy, dark, dramatic, weapon, robot.
```

---

# Part 5 — Generation tips

## Use the same image-gen tool throughout
Don't mix DALL-E and Imagen across the three Riya illustrations — they have different style fingerprints and the character won't look like the same person. Pick one and stick with it.

## If text labels come out garbled
- Append: *"render labels as crisp vector text, high resolution"*
- Or generate WITHOUT text and add labels in Keynote / Google Slides
- Architecture diagram: text labels almost always struggle. Add labels manually.

## If the Riya character drifts between images
Generate Image 1 first, get a result you like, then **paste a screenshot of that result into the prompt** for images 2 and 3 with: *"Match the character in this reference image exactly."*

## Backup plan
If image generation fails, use **Excalidraw** for the architecture diagram (looks intentional-rough, very on-trend). For Riya, use a stock illustration site filtered for Notion-style line art (Storyset, Iconscout, unDraw with custom color).

## Recommended generation order
1. **Mascot first** (Image 5) — establishes the visual language for the leaf creature
2. **Riya 1** (Overwhelmed) — establishes Riya's appearance
3. **Riya 2** (Discovering) — uses Mascot + Riya references
4. **Riya 3** (Confident) — uses both prior Riya references for consistency
5. **Architecture diagram** (Image 4) — independent, generate last when you have time

---

# Part 6 — Asset checklist (print this and tick as you go)

- [ ] Image 1: Overwhelmed Riya — generated and saved
- [ ] Image 2: Riya discovering Xylem — generated and saved
- [ ] Image 3: Confident Riya — generated and saved
- [ ] Image 4: Architecture diagram — generated, labels readable
- [ ] Image 5: Xylem mascot — generated, used on Slides 3, 6, 9, 10
- [ ] All slides drafted in template
- [ ] Speaker notes pasted into PowerPoint notes panel
- [ ] Memorized 4 key lines (opener, transition, Riya close, closing)
- [ ] Pacing rehearsed under 10:30
- [ ] Backup screenshots of every demo answer saved to a folder
- [ ] Cache pre-warmed within 30 min of stage time
