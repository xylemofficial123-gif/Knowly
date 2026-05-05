# Xylem — Demo Day Q&A Prep

> Study sheet for capstone judges. Read before going on stage. Each answer is short enough to memorize, specific enough to defend. Skim the **bold question lead** to find the topic; the answer is what to say.

---

## 🏗 Architecture & Stack

**Q1 — Walk me through the request flow when a user asks a question.**
> Frontend sends to `/api/oracle/ask` with a Clerk Bearer token. The router classifies the query type via LLM. For "why" questions it goes to the Research agent which generates 3-5 search angles, embeds each via local fastembed, queries Qdrant for top chunks, ACL-filters by the user's email, then synthesizes an answer with inline citations using the Gemini → Groq → OpenRouter free fallback chain. Total: ~7 seconds end-to-end without cache, sub-100ms with cache.

**Q2 — Why local embeddings instead of OpenAI's?**
> Three reasons: free, privacy (every chunk would otherwise leave our infra), and benchmarks within 5% of paid options on retrieval quality. We use BAAI/bge-small-en-v1.5, 384 dimensions, runs on CPU in ~80ms per chunk. There's a documented decision record on this.

**Q3 — How do you handle ACL across all five sources?**
> Each chunk carries an `acl` array. Slack chunks inherit channel members; Drive inherits file permissions; Meet inherits attendee list; ClickUp inherits assignees. At query time, we filter retrieved chunks against the requesting user's email before passing to the LLM. If you can't see the source, you can't see the answer.

**Q4 — Why a multi-agent architecture instead of one big LLM call?**
> Different query types need different strategies. Comparison questions ("Stripe vs Adyen") need parallel retrieval across multiple terms. Onboarding questions ("tell me about project X") need diverse, structured output. Single-shot synthesis blends them poorly. The router classifies intent and dispatches to specialists. Each agent has a focused prompt — better quality than one mega-prompt.

**Q5 — What's running on Railway versus Vercel?**
> Vercel hosts the Next.js frontend. Railway runs three services: the FastAPI backend, a Celery worker for async ingestion, and Postgres + Qdrant + Redis. The worker is separate from the API so a long Drive sync doesn't block live queries.

---

## 🤖 LLM & Reasoning

**Q6 — How do you prevent hallucinations?**
> Three layers. (1) Synthesis prompt forbids facts not in the sources. (2) Every claim must cite a SOURCE_N — we extract the actually-cited ones via regex; uncited claims surface only when sources are unavailable. (3) When retrieval returns nothing, the agent returns a fixed string: *"I cannot find a documented record of this in the company's knowledge base."* Never invents.

**Q7 — What if the LLM cites a source that doesn't actually support the claim?**
> Honest answer — that can happen. We can't prevent it 100% with current LLMs. But citations are clickable, so a user can verify in two seconds. We also store full chunk text on the citation card so the user doesn't need to leave the chat to check. We've seen ~5% citation drift in testing.

**Q8 — You're using free-tier LLMs — won't quality suffer?**
> We benchmark Gemini 1.5 Flash and Groq Llama 3.1 70B against the paid tier for our retrieval-augmented use case. The gap is small because most of the work is retrieval, not generation. Paid models would help on edge cases — that's why the architecture is provider-agnostic. Swap in Claude or GPT with a single env var.

**Q9 — How does the contradiction detection work?**
> It's not a special module — it falls out of citation discipline. When retrieval pulls in two chunks that disagree (Stripe was decided / Paytm was proposed), the LLM sees both, and the prompt explicitly instructs: *"If sources conflict, note the conflict and cite both."* The Anti-Amnesia Guardian agent escalates this to Slack DMs when a settled decision is being re-litigated.

**Q10 — Why the 3-tier free fallback chain?**
> Free-tier providers all have rate limits — Gemini 60/min, Groq 30/min, OpenRouter ~20/min. One provider going down or hitting quota would kill the product. With three providers, the failure rate drops to the product of three independent quotas, not just one. We've measured ~95% chain availability over a week.

---

## 🔒 Privacy & Security

**Q11 — What stops a member from querying salary data?**
> Two locks. **Lock 1** — ACL filtering at retrieval: if the user can't see the source doc in Drive, the chunk is filtered out before the LLM ever sees it. **Lock 2** — No-Index Zones: admins can mark specific folder/channel/space IDs as never-ingest. Combined, even an admin who accidentally enables HR drive-folder sync can't leak it via Xylem.

**Q12 — Where does the data live?**
> Postgres + Qdrant on Railway, behind Clerk auth. No customer data leaves our infra for embeddings — we use fastembed locally. LLM calls do send chunk text to providers, but those chunks are already ACL-filtered to what the asking user is permitted to see.

**Q13 — What about audit logs — can an admin secretly query 'layoff plans'?**
> No. Every query writes to the `audit_log` table with the user's email, query text, timestamp, and chunks returned. Admins see this in `/audit`. It's a deliberate anti-espionage check from the PRD — the PRD specifically calls out *"no employee silently querying layoff plans."*

**Q14 — What if an attendee doesn't want their meeting transcribed?**
> Two paths. (1) Don't enable transcripts on the Meet — Xylem can't ingest what doesn't exist. (2) If transcripts ARE generated but you want the content private, the host (whose Drive holds the file) can revoke Xylem's read scope or delete the transcript. The pipeline is opt-in at the Workspace level — only admins and team leads can connect Google.

**Q15 — How is auth enforced on every endpoint?**
> FastAPI dependencies. Every API route declares `Depends(get_current_user_email)` or `Depends(require_admin)`. The dependency verifies the Clerk JWT, looks up the user in our DB, and either returns the email or raises 401/403. There's no path that skips this — we audited it.

---

## 💰 Cost & Scaling

**Q16 — What does this cost to run today?**
> $0. Railway free tier for compute, fastembed local for embeddings, free LLM tier across three providers. The only real cost is the developers' time.

**Q17 — At scale — say 100 users, 1000 queries/day — what happens?**
> Free tier breaks. 1000 queries × 4 LLM calls each = 4000 daily calls per day, which exceeds Gemini's 1500/day. The architecture is designed to switch to paid: each provider has a paid tier, swap one env var. At paid Claude Haiku rates, 4000 calls = roughly $1/day. Embeddings stay free regardless.

**Q18 — How fast can you onboard a new source like Notion?**
> ~4 hours of work. The ingestion module is 200-300 lines per source — auth, fetch, format, ACL, chunk-and-store. Notion has a clean API and webhooks. The hard part isn't the ingestion — it's tuning chunk size and entity extraction for the new format.

**Q19 — What's the failure mode if Qdrant goes down?**
> Retrieval throws, caught at the API layer, returns a graceful degradation message: *"I can reach your knowledge sources, but the answer model is temporarily unavailable."* Frontend shows this message; user can retry. We don't 500. Postgres being down is harder — that takes auth and ACL with it. We'd need a circuit-breaker fallback for that, which we haven't built.

---

## 🆚 Differentiation

**Q20 — How is this different from ChatGPT or Notion AI?**
> Two structural differences. **(1) Cross-source** — ChatGPT doesn't see your Slack threads, your Drive doc, and your ClickUp ticket together; Xylem does, with one cited answer. **(2) Decision-aware** — Xylem knows which decisions are active, which were reversed, which are draft. ChatGPT doesn't know your company's history. We're not competing with ChatGPT for general knowledge; we're competing for institutional memory.

**Q21 — Glean exists. Aren't you reinventing it?**
> Glean is enterprise-priced, $12-20/seat/month. We built this as a free, internal-first agent for a small org. The architectural overlap is real — but our differentiator is decision extraction and ghost-documentation, which Glean doesn't do. They're a search engine; we're a memory.

**Q22 — Why an agent and not just a chatbot?**
> The router decides between three agents: Research for cross-source synthesis, Onboarding for structured briefings, Guardian for proactive Slack alerts. A flat chatbot would do all three poorly. Especially Guardian — it's not query-driven; it watches Slack events and replies in-thread when a settled debate gets reopened. That's not a chat interaction at all.

---

## 🐛 Sharp / Adversarial

**Q23 — I see your decision log says only 25 decisions. Are you confident this is production-ready?**
> That's our seeded demo data plus what got extracted from real Slack threads — small data, not architecture. The decision-extraction pipeline is content-volume agnostic; it'll handle 25 or 25,000. We focused on correctness over volume because hallucinated decisions are worse than missing ones.

**Q24 — I asked the same question twice and got slightly different answers. Why?**
> LLM non-determinism, plus we don't pin temperature to 0. We've added a 30-minute response cache so identical questions return identical answers within the window — that addresses the demo flow. For production, we'd lower temperature to 0.2 or use deterministic decoding. We chose stability over creativity for a knowledge tool.

**Q25 — Your contradiction detection just caught Stripe vs Paytm. What if both are wrong?**
> Then both are recorded, both are cited, and both will show up the next time someone asks. Xylem doesn't claim to be the source of truth — it claims to be the company's *memory* of what was said. The truth-finding is a human responsibility. We surface conflict; humans resolve it. The PRD calls this *Living History.*

**Q26 — Can I trust an answer that cites a Slack message from a private channel?**
> You'd never see that answer. ACL filtering happens before retrieval, before the LLM. If your Slack user isn't a member of the private channel, those chunks are discarded. We don't *know about* content you can't see. Verifiable: log in as a non-member, ask the same question, and you'll get a different answer or a *no record* response.

**Q27 — What's the worst thing that can happen if Xylem is wrong?**
> Re-litigated decisions, wasted meeting time. The risk is *quality*, not *security*. Citations make every claim auditable in seconds. The downside scenario is: someone trusts a hallucinated answer without clicking the citation. Mitigation: every answer requires a citation; uncited claims aren't allowed. We accept some quality risk; we don't accept silent fabrication.

---

## 🆕 Onboarding & Group Scoping

**Q23a — How do I add or remove a project?**
> Projects map to Groups in the admin panel — Ingest tab → Groups. An admin creates a Group, names it, optionally seeds members. The Group's name and ACL flow into Quick Onboarding automatically; new joiners assigned to that group see it as a project card. Removing the group removes the project. Same plumbing the rest of the ACL system uses, so there's nothing project-specific to maintain.

**Q23b — A new joiner hasn't been assigned to a team yet. What do they see?**
> A clear empty state: *"Not assigned to a project yet — ask an admin to add you to a team in the Groups tab."* They can still query the Oracle for any public knowledge, but the personalized onboarding view doesn't show fake or generic projects. Once an admin adds them via the Groups tab, the relevant project card appears next time they reload.

**Q23c — A user is in three teams. Do they see them all together or separately?**
> Quick Onboarding shows one card per team — they pick which project to dive into. Decisions and documents in the chat view are merged across all teams the user has visibility into, with team-tag chips on each decision (👥 Engineering, 👥 Sprout) so the source team is always clear. Search follows the user, not the team — Slack-style.

**Q23d — As an admin, do I see every team's onboarding view?**
> Yes — admins bypass the per-membership filter so they can preview any project's onboarding. We treat admin as the operator role; if you want a project hidden from admins, the right tool is No-Index Zones (don't ingest the source), not ACL.

---

## 🚀 Future / Production

**Q28 — What's missing for production?**
> Three things. (1) Paid LLM fallback for accuracy and reliability. (2) Real-time Slack event ingestion (currently scheduled). (3) Per-team isolation if Seedling Labs sells this externally. Architecturally, all three are 1-2 weeks. The hard work — agent design, ACL, contradiction detection — is done.

**Q29 — How would you measure success in production?**
> Three metrics, already on the dashboard. **Deflection Rate** — % of queries answered without escalation to a human. **Decision Adherence** — % of recorded decisions still being cited (vs ignored or contradicted). **Avg Retrieval Time**. Currently 7.7s, target <30s, achieved. Adherence is at 100%, but that's small data. Real test is at 6 months of usage.

**Q30 — What would you build next?**
> Proactive briefings. Today Xylem is reactive — you ask, it answers. The next step is push: *"You have a meeting in 30 minutes — here's the relevant context, the relevant decisions, the open action items."* That requires Calendar event hooks and personalization. Roughly 2 weeks of work, but it's the thing that turns Xylem from a tool into a teammate.

---

## 🎯 Wildcards (oddball questions)

**Q31 — Why call it Xylem?**
> Xylem is the part of a plant that carries water and nutrients to every cell. We carry knowledge to every person in the company. We're at Seedling Labs — vascular tissue felt right.

**Q32 — If your teammate disappeared tomorrow, could you keep building this?**
> Yes. Standard FastAPI + Next.js + Postgres. Every architectural decision is in `PROJECT_STATUS.md`. Every PRD requirement maps to a specific file. We've documented the pipeline at every layer. Anyone with two years of full-stack experience picks this up in a day.

**Q33 — What would you change if you started over?**
> Cut the multi-agent router earlier and prove the single-agent path first. We over-engineered before we knew where the real value was. The decision-extraction module — that's where the differentiation lives — got attention later than it should have. Build the simplest version first; layer agents on once you've proven the simple thing works.

---

## 💡 The "I don't know" answers — use these honestly

Some questions you should NOT bullshit. Practice saying:

- *"I don't know — I'd want to test before committing to an answer."*
- *"That's a real gap. We haven't built it yet because [reason]."*
- *"That's a fair concern. Here's the mitigation we have, here's what's still open."*

**Confident "I don't know" > confident bullshit.** Judges remember bullshit; they respect *I don't know*.

---

## 🎤 Memorize first — these get asked the most

If you only have time to deeply memorize a few, prioritize:

1. **Q1** (request flow) — they always ask "how does it work"
2. **Q6** (hallucinations) — every AI demo gets this
3. **Q11** (privacy) — first question from any security-minded judge
4. **Q17** (cost at scale) — investors / PMs ask this
5. **Q20** (vs ChatGPT) — comparison is inevitable
6. **Q28** (what's missing) — closing-question energy
7. **Q31** (the name) — easy warm-up question

Read each one out loud three times before demo day. Don't read them off the page during the talk — phrase them in your own words.

---

## 📖 Reference — key numbers to recall

| Number | Meaning |
|---|---|
| **5** | Connected sources (Slack, Drive, Calendar, Meet, ClickUp) |
| **25/26** | PRD requirements implemented |
| **7.7s** | Avg retrieval time (target: <30s) |
| **100%** | Citation rate — every claim has a source |
| **200+** | Cross-source entity links |
| **17** | Active decisions (pre-seed) — climbs as you ingest more |
| **3-tier** | LLM fallback (Gemini → Groq → OpenRouter) |
| **$0** | Production cost today |
| **384** | Embedding dimensions (BAAI/bge-small-en-v1.5) |
