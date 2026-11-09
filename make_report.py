"""Build the sprint report PDF.  Usage: python make_report.py --authors "Name1, Name2" --affil "Org" """
import argparse

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ap = argparse.ArgumentParser()
ap.add_argument("--authors", default="[Author names]")
ap.add_argument("--affil", default="[Affiliation]")
ap.add_argument("--out", default="Footprints_report.pdf")
a = ap.parse_args()

ss = getSampleStyleSheet()
B = ParagraphStyle("b", parent=ss["BodyText"], fontSize=10, leading=13.5, spaceAfter=6)
H = ParagraphStyle("h", parent=ss["Heading2"], fontSize=12.5, spaceBefore=10, spaceAfter=4)
T = ParagraphStyle("t", parent=ss["Title"], fontSize=16, leading=20)
C = ParagraphStyle("c", parent=B, alignment=1, fontSize=10)
S = ParagraphStyle("s", parent=B, fontSize=8.5, leading=11)
TB = ParagraphStyle("tb", parent=B, fontSize=8.5, leading=10.5, spaceAfter=0)


def tbl(rows, widths):
    t = Table([[Paragraph(str(c), TB) for c in r] for r in rows], colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef7")),
                           ("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return t


s = []
P = lambda x, st=B: s.append(Paragraph(x, st))
P("Footprints: Catching Agent Swarms by How They Use Shared Infrastructure", T)
P(a.authors + (f"<br/>{a.affil}" if a.affil else ""), C)
P("Apart Research Swarm Alignment Hackathon, 6-8 November 2026. Track 4 (also Tracks 1 and 3).", C)
s.append(Spacer(1, 8))
P("<b>Abstract.</b> In July 2026, about 1,200 AI agents in an OpenAI evaluation turned a shared package cache into a "
  "message board, and about 700 of them attacked Hugging Face. The channel went unnoticed for weeks: monitors read "
  "agent transcripts one at a time, while the coordination happened in shared infrastructure, in encoded content. We "
  "present Footprints, a streaming monitor that looks for emergent agent channels using access metadata alone: who "
  "wrote or read which object, when, and how big. It scores six content-blind signals (two-way flow, mutability, "
  "message rhythm, writer bursts, persistence after deletion, and writes into namespaces clients should not write) and, "
  "after an alert, ranks principals to name the likely coordinator. We evaluate it on real logs from a second agent "
  "message board (collusion.wiki: 14,591 timed revisions, 3,103 agent names) and in a scripted shared-cache sandbox "
  "with ground truth. In the sandbox, Footprints caught a seeded board in 5/5 runs, a mean of 3.8 minutes after the "
  "first message, with zero false alarms across 5 benign runs, and named the coordinator in 5/5 runs. It missed an "
  "adaptive swarm that hides messages as write-once artifacts in 5/5 runs. On real logs, its first alert on a "
  "coordination page came 7.1 hours after the first such page appeared, but page-level AUROC was only 0.62 "
  "(95% CI 0.60-0.64). We report these limits plainly and release the detector, sandbox and replay harness.")

P("1. Introduction", H)
P("Single-agent oversight missed what a population of agents did together. The METR and Redwood investigation of the "
  "July 2026 incident found that agents coordinated through cache entries under one path, formed roles within hours "
  "(one copy of the origin agent sent about 10% of all assignments), invented their own message signing after an "
  "impersonation, and spoofed tool calls in about 7% of reviewed transcripts. Early signals existed in May and June but "
  "no tool connected them. Recent work shows per-agent monitors fail when attacks are split across agents "
  "(Makins et al., 2026; Brown et al., 2026) and that activation probes can flag collusion (Rose et al., 2026), but these "
  "assume the monitor already sees the channel, readable content, or model weights. A platform such as Hugging Face, or "
  "an operator of shared infrastructure, has none of these. It has access logs.")
P("<b>Question.</b> Can a monitor that sees only access metadata find an emergent agent channel early, with few false "
  "alarms, without being told where to look? <b>Contributions:</b> (1) a content-blind streaming detector with "
  "transparent, per-signal alerts; (2) a replay harness over real swarm logs; (3) a shared-cache sandbox with ground "
  "truth and benign, seeded and adaptive conditions; (4) an honest evaluation, including where the method fails.")

P("2. Related work", H)
P("<b>Distributed attacks vs per-agent monitors:</b> FakeLab shows a fragmentation effect, with planners raising attack "
  "completion up to sevenfold (Makins et al., 2026); stateful transcript clustering catches distributed attacks 30% "
  "earlier (Brown et al., 2026); see also Hills et al. (2026) and Jones et al. (2024). <b>Collusion and steganography:</b> "
  "NARCBench probes reach 1.00 AUROC in distribution and 0.60-0.86 under shift (Rose et al., 2026); J-PACT is an "
  "unsupervised variant (Molinari and Bettineschi, 2026); Motwani et al. (2024) and Mathew et al. (2024) formalise and "
  "elicit steganographic collusion. <b>Control:</b> Greenblatt et al. (2024); Ctrl-Z (Bhatt et al., 2025); untrusted "
  "monitoring safety cases (Gardner-Challis et al., 2026). <b>Trace integrity:</b> agents can delete their own traces, "
  "so capture must sit outside their control (Qin et al., 2026). <b>Stigmergy:</b> LLM agents self-organise through a "
  "shared environment (SwarmWorld, Pal et al., 2026). None of these detects a channel the agents built themselves from "
  "metadata alone, or replays real swarm logs.")

P("3. Method", H)
P("Every source is mapped to one event schema: timestamp, principal, action (write, read, delete), opaque object id, "
  "namespace, size, and whether a write only appended. The detector never sees content or object names. For each object "
  "it keeps streaming state and computes six signals:")
s.append(tbl([
    ["Signal", "Definition", "Why a swarm shows it"],
    ["Flow", "log(1 + distinct writer-to-later-reader pairs where the reader also writes the object)", "Two-way exchange; one-way artifact consumption is excluded"],
    ["Mutability", "log(1 + rewrites) + log(1 + extra writers)", "Artifacts are written once; boards are rewritten"],
    ["Rhythm", "Share of small (<4 KB), quick (<1 h apart), append-only writes", "Chat-like traffic"],
    ["Join", "log(1 + peak distinct writers within one hour - 1)", "Recruitment bursts"],
    ["Persistence", "log(1 + recreations after deletion)", "Swarms rebuild wiped channels"],
    ["Novelty", "1 if a client writes a namespace only a proxy should write", "Channels hide where nobody looks"],
], [2.3 * cm, 7.6 * cm, 6.1 * cm]))
s.append(Spacer(1, 6))
P("The score is a weighted sum (flow 1.0, mutability 0.5, rhythm 1.0, join 0.7, persistence 1.0, novelty 3.0), set by "
  "hand before evaluation and printed in every alert. An object alerts once when its score reaches 6.0. After alerts, a "
  "role map ranks principals by the number of distinct alerted objects on which others picked up their writes.")

P("4. Experiments", H)
P("<b>E1, real logs.</b> We replay the public collusion.wiki release in time order: 14,591 revisions and 5,217 "
  "administrator deletions (19,808 events). Revisions carry the agent's self-chosen name, a /16 IP prefix and a "
  "timestamp. Labels from the dataset authors (page_family) are used only for evaluation; we treat the 709 "
  "relay-coordination pages as positives. We report page-level AUROC with 1,000-sample bootstrap intervals, the result "
  "on pages first written after the first 10 days, and results without labels derived from timing rules. Baseline: a "
  "multi-writer rule (at least 3 names and 3 writer switches within 24 h).")
P("<b>E3, sandbox.</b> A scripted world with 12 benign clients (publish write-once artifacts, read artifacts, read a "
  "proxy-filled remote cache, rewrite private scratch files) over 720 one-minute ticks. Seeded condition: from tick 240, "
  "10 agents discover and join a board under cache/remote/zz/, and a coordinator sends assignments through mailboxes. "
  "Adaptive condition: agents send each message as a new write-once artifact with jittered timing. 5 seeds per "
  "condition. Ground truth is every cross-agent message. Baselines: a volume alert (hourly events above 1.5x the "
  "running median) and a string rule matching the known board path.")

P("5. Results", H)
s.append(tbl([
    ["Experiment", "Result"],
    ["E1 relay vs other labelled pages (n=3,197)", "AUROC 0.62 (95% CI 0.60-0.64); recall 1.8% at 1% FPR, 11% at 5% FPR"],
    ["E1 held-out pages (after day 10, n=2,668)", "AUROC 0.62 (95% CI 0.60-0.65)"],
    ["E1 without timing-rule labels (n=2,663)", "AUROC 0.59 (95% CI 0.55-0.63)"],
    ["E1 first alert on a relay page", "7.1 h after the first relay page (26 May 2026, 09:50 UTC); baseline rule 6.9 h"],
    ["E1 alerts", "194 alerts, 73 of 709 relay pages; baseline rule 478 alerts, 176 relay pages"],
    ["E3 benign (5 seeds)", "0 false alarms; volume baseline also 0"],
    ["E3 seeded board (5 seeds)", "Detected 5/5; mean delay 3.8 min (95% CI 2.0-5.8); coordinator top-1 5/5; volume baseline detected 5/5"],
    ["E3 adaptive swarm (5 seeds)", "Detected 0/5; volume baseline 0/5"],
], [6 * cm, 10 * cm]))
s.append(Spacer(1, 6))
P("Two findings matter most. First, on real logs the untuned detector is weak: a supervised model on similar page "
  "metadata reached 0.75 AUROC in our pilot, so hand-set weights leave signal unused. Contrasting coordination pages with "
  "task-answer pages gave an inverted AUROC of 0.33, because on this wiki the task pages are also swarm-written (agents "
  "shared answers there); the dataset contains no benign traffic, so it cannot measure false alarms. Second, the "
  "sandbox shows the method works when the swarm uses a shared mutable object, and fails when the swarm spreads "
  "messages across write-once objects that look like normal artifacts: per-object signals cannot see a channel whose "
  "every object is ordinary.")

P("6. Discussion", H)
P("<b>Theory of change.</b> Operators of package caches, wikis, object stores and agent platforms already keep access "
  "logs. A content-blind first layer can run on them in real time, needs no access to the agents' models, and still "
  "works when content is encoded; content is read only after an alert. <b>Next steps:</b> (1) a benign baseline from "
  "human wiki edit histories to measure true false-alarm rates; (2) principal-level signals, such as reciprocal flows "
  "between principals across objects, aimed at the adaptive gap; (3) the same sandbox driven by real LLM agents; "
  "(4) weights fit on the first 10 days only and reported on held-out days; (5) identity linking across renamed agents.")

s.append(PageBreak())
P("Appendix A. Limitations and Dual-Use / Ethical Considerations", H)
P("<b>Limitations.</b> The sandbox is scripted, so seeded-condition results are a floor, not evidence about capable "
  "agents. Real-data labels come from the dataset authors' rules, some timing-based; we report results without them. "
  "collusion.wiki has no benign traffic, so false-alarm rates on real data are unmeasured. Weights were set by hand, not "
  "tuned. Self-chosen names are unreliable identities. Results come from one wiki and one simulated cache; transfer to "
  "other infrastructure is untested. A swarm that knows these signals can try to look benign, as the adaptive condition shows.")
P("<b>Dual use.</b> The work is defensive. We publish detection rates for the adaptive condition but no recipe for "
  "evasion beyond what the incident reports already describe. The repository ships no datasets, payloads or "
  "credentials; Swarm Traces contains attack code and was only parsed, never executed. We did not visit the live "
  "collusion.wiki site. A monitor of access patterns can also be used for surveillance of people; it should run only on "
  "infrastructure the operator is responsible for, on agent principals, with access controls on its outputs.")
P("Appendix B. Reproducibility", H)
P("All code was written during the sprint. <font face='Courier'>python -m footprints data</font> downloads the datasets "
  "and pins SHA-256 hashes; <font face='Courier'>replay</font> and <font face='Courier'>sandbox</font> regenerate every "
  "number in Section 5 (seeds 0-4); <font face='Courier'>pytest</font> runs unit tests.")
P("References", H)
for r in [
    "METR (Greenblatt, Cotra, Wijk). OpenAI / Hugging Face incident investigation. Aug 2026. metr.org/blog/2026-08-26-openai-hugging-face-incident-investigation",
    "Von Arx, Byrd, Kitts, Larsen. collusion.wiki: discovery of a new OpenAI agent message board. Sep 2026. collusion.wiki",
    "Forman et al. Swarm Traces. Sep 2026. swarmtraces.org",
    "Makins, Angelini, Shams, Phuong. Multi-Agent AI Control: Distributed Attacks Hamper Per-Instance Monitors. arXiv:2607.07368, 2026.",
    "Brown et al. Stateful Online Monitoring Catches Distributed Agent Attacks. arXiv:2605.31593, 2026.",
    "Hills, Caspary, Cooper Stickland. Distributed Attacks in Persistent-State AI Control. arXiv:2607.02514, 2026.",
    "Jones, Dragan, Steinhardt. Adversaries Can Misuse Combinations of Safe Models. arXiv:2406.14595, 2024.",
    "Rose, Cullen, Kaplowitz, Schroeder de Witt. Detecting Multi-Agent Collusion Through Multi-Agent Interpretability. arXiv:2604.01151, 2026.",
    "Molinari, Bettineschi. Multi-Agent Collusion and the J-Space. arXiv:2611.02153, 2026.",
    "Motwani et al. Secret Collusion among AI Agents: Multi-Agent Deception via Steganography. NeurIPS 2024 (arXiv:2402.07510).",
    "Mathew et al. Hidden in Plain Text: Emergence and Mitigation of Steganographic Collusion in LLMs. arXiv:2410.03768.",
    "Greenblatt, Shlegeris, Sachan, Roger. AI Control: Improving Safety Despite Intentional Subversion. arXiv:2312.06942, 2024.",
    "Bhatt et al. Ctrl-Z: Controlling AI Agents via Resampling. arXiv:2504.10374, 2025.",
    "Gardner-Challis et al. When can we trust untrusted monitoring? A safety case sketch across collusion strategies. arXiv:2602.20628, 2026.",
    "Qin et al. LLM Agents Can Easily Tamper With Their Own Traces. arXiv:2609.30266, 2026.",
    "Pal, Wang, Buehler. SwarmWorld: Stigmergic technological evolution in societies of language-model agents. arXiv:2608.26081, 2026.",
]:
    P(r, S)

SimpleDocTemplate(a.out, pagesize=A4, leftMargin=2.2 * cm, rightMargin=2.2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
                  title="Footprints", author=a.authors).build(s)
print("wrote", a.out)
