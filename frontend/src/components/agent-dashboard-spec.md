# Agent Dashboard — UI/UX Specification

**Stack:** Vite + React + TypeScript + Tailwind CSS
**Design ethos:** Quiet, engineering-grade UI. The interface should feel like a well-organized instrument panel — never like a "product." Every visual choice exists to make the AI system's behavior legible (what was retrieved, what was generated, how long it took), not to impress. No gradients-for-the-sake-of-it, no decorative illustrations, no marketing copy. Whitespace and restraint are the primary design tools.

---

## 1. Global Layout

A fixed **3-column shell**, no page scroll on the shell itself (only inner panels scroll):

```
┌──────────┬──────────────────────────────────────┬──────────────┐
│ Sidebar  │ Main Content (Chat / KB / Settings)   │ Trace Panel  │
│ 240px    │ flex-1, min-width 0                    │ 340px        │
│ fixed    │                                         │ collapsible  │
└──────────┴──────────────────────────────────────┴──────────────┘
```

- **Sidebar**: `w-60` (240px), fixed, full viewport height, left-aligned, `bg-white` with a `border-r border-slate-200`.
- **Main content**: fills remaining space, `bg-slate-50`, has its own top header bar + scrollable body.
- **Trace panel**: `w-[340px]`, slides in/out from the right, `border-l border-slate-200`, `bg-white`. Toggled by a "Show trace" switch in the chat composer, or an `×` close button in its own header. Collapsed state: panel width animates to 0 (or is simply unmounted) and main content expands to fill the space.
- Breakpoint behavior: below `lg` (1024px), the trace panel becomes an overlay (fixed, slides over content with a scrim) rather than pushing layout; below `md` (768px), the sidebar collapses to icon-only rail (`w-16`, labels hidden, tooltips on hover).

---

## 2. Sidebar

Top to bottom:

1. **Brand row** (`h-16`, `px-5`, flex items-center gap-2, border-b): a small geometric mark (rounded-square icon container, `bg-blue-600`, white icon) + product wordmark in `font-semibold text-lg text-slate-900`.
2. **Primary nav** (`px-3 py-4`, `flex flex-col gap-1`): four items, each a full-width button:
   - **Chat** — speech-bubble icon
   - **Knowledge Base** — document/stack icon
   - **Trace** — branching/waypoints icon
   - **Settings** — gear icon

   Each nav item: `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium`. Inactive: `text-slate-600 hover:bg-slate-100`. Active: `bg-blue-50 text-blue-700` with the icon also tinted blue — no left border stripe, the fill is enough.
3. **Knowledge Base quick-switcher** (below nav, separated by a `border-t`, `px-3 pt-4`): a small section labeled `KNOWLEDGE BASE` (`text-xs font-semibold text-slate-400 uppercase tracking-wide px-2 mb-2`), containing a **selected-source card**: rounded-lg border, `p-3`, icon + name ("Product Documentation") + chevron-down (this is a dropdown to switch between ingested sources/collections), and beneath the name a muted meta line: `12 documents · 4.2k chunks` in `text-xs text-slate-400`.
4. **User footer** (pinned to bottom via `mt-auto`, `border-t`, `p-3`): circular avatar (initials on a soft color, e.g. `bg-violet-100 text-violet-700`), user name (`text-sm font-medium`), and a trailing chevron `›` indicating it opens an account menu.

---

## 3. Screen: Chat

### 3.1 Header
`h-[72px]`, `px-8`, flex items-center justify-between, `border-b border-slate-200`, `bg-white`.
- Left: page title `Chat` (`text-xl font-semibold text-slate-900`) with a one-line subtitle underneath in `text-sm text-slate-500`: "Ask questions about your knowledge base."
- Right: the same **source selector** as the sidebar card, but as a pill button (icon + "Product Documentation" + chevron), `border border-slate-200 rounded-lg px-3 py-2 text-sm bg-white hover:bg-slate-50` — lets the user scope the chat to a specific ingested collection.

### 3.2 Message thread
`flex-1 overflow-y-auto px-8 py-6`, messages stacked with `space-y-6`, max width `max-w-3xl mx-auto` so lines don't stretch edge-to-edge on wide screens.

**User message row:**
- 32px circular avatar (neutral gray, generic person icon) on the left.
- Message bubble: `bg-blue-50 rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-slate-800`, content left-aligned.
- Timestamp (`text-xs text-slate-400`) below-left of the bubble, e.g. `10:24 AM`.

**Assistant message row:**
- 32px avatar: the brand mark again in a soft circle, so the agent's presence is visually consistent with the product identity.
- Body: plain text (no bubble background — this asymmetry is intentional, it makes assistant answers read like authoritative document content, not chat noise), `text-sm text-slate-800 leading-relaxed`, supports:
  - Paragraphs
  - Bullet lists (`list-disc pl-5 space-y-1`) — used for things like requirement lists
  - Inline **bold** for key terms
  - Section sub-headers when the answer has parts (`text-sm font-semibold text-slate-900 mt-3 mb-1`)

**Sources block** (directly beneath an assistant answer, only rendered when citations exist):
- Small label row: document-stack icon + `Sources` in `text-xs font-semibold text-slate-500 uppercase tracking-wide`.
- Row of **citation chips**, `flex flex-wrap gap-2`. Each chip is clickable:
  - `border border-slate-200 rounded-lg px-3 py-2 bg-white hover:border-blue-300 hover:bg-blue-50/40 transition-colors`, flex items-center gap-2.5
  - File-type icon in a tinted circle (`bg-blue-50 text-blue-600`).
  - Two-line text: filename in `text-sm font-medium text-slate-800` (e.g. `installation.pdf`), and beneath it a locator/snippet in `text-xs text-slate-400` (e.g. `Page 18 · On-premise deployment`).
  - Clicking a chip opens the source document at that page/chunk — either in a right-side drawer/preview or a modal (implementation detail, but the click target and hover affordance must exist).
- Timestamp for the whole assistant turn beneath the sources row.

### 3.3 Composer (bottom, pinned)
`border-t border-slate-200 bg-white px-8 py-5`. Inner container `max-w-3xl mx-auto`.
- A rounded input surface: `border border-slate-200 rounded-2xl bg-white shadow-sm`, containing:
  - Text input, `placeholder="Ask a question about your knowledge base..."`, borderless, `text-sm`, grows to `textarea` height on multi-line input (auto-resize, capped).
  - Send button, bottom-right inside the surface: circular, `bg-blue-600 hover:bg-blue-700`, white paper-plane icon, disabled/greyed when input is empty.
- Below the input surface, a thin **utility row** (`flex items-center gap-4 mt-2 px-1`):
  - `Attach file` — paperclip icon + text button, `text-sm text-slate-500 hover:text-slate-700`.
  - `Show trace` — a small labeled **toggle switch** (pill, `w-9 h-5`, off = `bg-slate-200`, on = `bg-blue-600` with the knob sliding right) that opens/closes the right Trace panel for the current conversation.

### 3.4 States
- **Empty state** (no messages yet): centered vertically, brand mark large and faint, heading "Ask anything about your documents," and 2–3 example-question chips the user can click to prefill the composer.
- **Streaming state**: assistant row appears immediately with a subtle pulsing text-cursor or three-dot typing indicator; text fills in progressively; the Sources block appears only once retrieval completes (it may appear before generation finishes, since retrieval happens first).
- **No-answer/low-confidence state**: assistant text is prefixed with a small amber notice strip ("Couldn't find a confident answer in the knowledge base") — muted, not alarming (`bg-amber-50 text-amber-800 border border-amber-200 rounded-lg px-3 py-2 text-xs mb-2`).

---

## 4. Screen: Knowledge Base

### 4.1 Header
Same header pattern as Chat: title `Knowledge Base`, subtitle `Manage your ingested documents`, and on the right a primary button `+ Upload` (`bg-blue-600 text-white rounded-lg px-4 py-2 text-sm font-medium`).

### 4.2 Collection selector row
A horizontal strip of collection "tabs" or a dropdown identical to the sidebar/chat source selector, so the whole screen is scoped to one knowledge base at a time (e.g. "Product Documentation ▾, 12 documents, 4.2k chunks").

### 4.3 Document table/list
`bg-white rounded-xl border border-slate-200`, each row `px-4 py-3 flex items-center gap-4 border-b last:border-b-0`:
- File-type icon (color-coded by type: PDF = red-tinted, MD = slate, DOCX = blue).
- Filename (`text-sm font-medium text-slate-800`) + muted meta line beneath (`size · page/chunk count · uploaded date`).
- **Status badge**, pill-shaped, `text-xs font-medium px-2.5 py-1 rounded-full`:
  - `Indexed` — `bg-emerald-50 text-emerald-700`
  - `Processing` — `bg-amber-50 text-amber-700`, paired with a small spinner
  - `Failed` — `bg-red-50 text-red-700`, with a `Retry` inline text-button
  - `Queued` — `bg-slate-100 text-slate-500`
- Row-level actions on the far right, visible on hover: an eye icon (preview), and a trash icon (delete) that opens a confirm dialog before removing the doc and its chunks from the index.

### 4.4 Upload
Clicking `+ Upload` opens either a modal or an inline dropzone card at the top of the list: dashed-border rectangle (`border-2 border-dashed border-slate-300 rounded-xl`), centered upload-cloud icon, "Drag files here or click to browse," accepted formats listed small beneath (`PDF, DOCX, MD, TXT`). Uploaded files immediately appear in the list with `Processing` status and animate to `Indexed` when ingestion completes.

### 4.5 Empty state
Centered illustration-free message: stack icon, "No documents yet," short sentence, and the `+ Upload` button repeated centrally.

---

## 5. Trace Panel (right-side drawer)

Purpose: make the agent's retrieval-augmented-generation pipeline fully inspectable, turn by turn. This is the panel that differentiates an "AI engineering" tool from a generic chatbot — it should feel precise and log-like, not decorative.

### 5.1 Header
`h-16 px-5 flex items-center justify-between border-b`. Title `Execution Trace` (`text-base font-semibold`), close `×` button on the right (`text-slate-400 hover:text-slate-700`).

### 5.2 Event timeline
A vertical stepper: each event is a row with a small circular status icon connected by a thin vertical line (`border-l border-slate-200` running behind the icons) to the next event — this is what makes it read as a *sequence*, not a list.

Per-event row (`flex gap-3 py-3`):
- **Status icon** (24px circle):
  - Completed step → filled `bg-emerald-500` circle with a white checkmark.
  - Retrieval step → `bg-slate-100` circle with a magnifying-glass icon, `text-slate-500`.
  - Generation step → `bg-slate-100` circle with a branching/share icon.
  - Streaming step → `bg-slate-100` circle with a lightning-bolt icon.
  - In-progress step → circle with an animated spinner ring.
  - Error step → `bg-red-100` circle with a red `!` icon.
- **Content**: event title (`text-sm font-medium text-slate-800`) with a right-aligned timestamp (`text-xs text-slate-400`), and a muted one-line description beneath (`text-xs text-slate-500`), e.g.:
  - `Query received` — the raw user query, truncated with ellipsis if long.
  - `Retrieved relevant chunks` — "Found 5 relevant chunks."
  - `Generated response` — "Using \<model name\>."
  - `Response streamed` — "287 tokens."

### 5.3 Retrieved Sources section
Beneath the timeline, a divider (`border-t pt-4 mt-2`), section label `Retrieved Sources (N)` (`text-sm font-semibold`). Each source is a compact row, clickable, `flex items-center justify-between p-2 rounded-lg hover:bg-slate-50`:
- Left: small doc icon in tinted circle + filename (`text-sm font-medium`) with meta beneath (`text-xs text-slate-400`, e.g. `Page 18 · On-premise deployment`).
- Right: a `›` chevron indicating it expands to show the actual retrieved chunk text (in a monospace or quoted block) when clicked.

### 5.4 Performance section
Divider, label `Performance`. Three metric rows, each `flex items-center justify-between py-1.5`:
- icon + label (`Total latency`, `Retrieval time`, `Generation time`) on the left in `text-sm text-slate-600`, with a small icon per row (clock/stopwatch/hash), value right-aligned in `text-sm font-medium text-slate-800` (e.g. `2.3s`, `0.7s`, `1.6s`).

### 5.5 Behavior notes
- The trace panel is **per-message**: selecting a different assistant turn in the chat (or the trace updating live as a new turn streams) refreshes this panel's contents.
- While a response is streaming, events append to the timeline in real time (this is the "streamed events" requirement) rather than appearing all at once after completion.
- Panel content scrolls independently of the chat thread.

---

## 6. Screen: Settings

Simple form-style screen, same header pattern (`Settings` / "Configure your agent"). Content organized into card sections (`bg-white border border-slate-200 rounded-xl p-6 space-y-4`, stacked with `space-y-6`):
- **Model** — dropdown for generation model, temperature slider.
- **Retrieval** — chunk size, top-k, similarity threshold (numeric inputs with small helper text under each).
- **Knowledge Base defaults** — default collection, auto-index-on-upload toggle.
- **Danger zone** — subtly separated (`border-red-100 bg-red-50/30`), e.g. "Clear all indexed data," red text-button, confirm-before-action.

---

## 7. Design Tokens

**Color:**
| Token | Value | Use |
|---|---|---|
| `slate-50` | background canvas |
| `white` | cards, panels, sidebar |
| `slate-200` | borders/dividers |
| `slate-400/500` | muted/secondary text |
| `slate-800/900` | primary text |
| `blue-600/700` | primary actions, active nav, links |
| `blue-50` | active-state tints, user message bubble |
| `emerald-500/700` | success / indexed / completed |
| `amber-500/700` | processing / warnings |
| `red-500/700` | errors / destructive |
| `violet-100/700` | avatar accent (rotate per-user if multi-user) |

**Typography:** a single sans stack (system UI or Inter). Scale: `text-xs` (12px) for meta, `text-sm` (14px) for body/UI default, `text-base` (16px) rare, `text-lg/xl` for headers only. Weight: `font-normal` body, `font-medium` for labels/buttons, `font-semibold` for headings and emphasis.

**Radius:** `rounded-lg` (8px) default for buttons/inputs/rows, `rounded-xl` (12px) for cards/panels, `rounded-2xl` (16px) for the chat composer and message bubbles, `rounded-full` for badges/avatars/toggles.

**Shadow:** almost flat design — rely on `border` not `shadow` for separation. Use `shadow-sm` only on floating/elevated elements (composer surface, dropdowns, modals).

**Spacing:** consistent 4px base scale via Tailwind defaults; screen padding `px-8 py-6`; card padding `p-4`–`p-6`; row padding `px-4 py-3`.

---

## 8. Component Inventory (for `src/components/`)

```
components/
  layout/
    Sidebar.tsx
    Header.tsx
    AppShell.tsx
  chat/
    ChatScreen.tsx
    MessageList.tsx
    UserMessage.tsx
    AssistantMessage.tsx
    SourceChip.tsx
    Composer.tsx
    EmptyState.tsx
  knowledge-base/
    KnowledgeBaseScreen.tsx
    DocumentRow.tsx
    StatusBadge.tsx
    UploadDropzone.tsx
    CollectionSelector.tsx
  trace/
    TracePanel.tsx
    TraceEvent.tsx
    RetrievedSourceRow.tsx
    PerformanceMetrics.tsx
  settings/
    SettingsScreen.tsx
    SettingsSection.tsx
  ui/                # shared primitives
    Badge.tsx
    Button.tsx
    Toggle.tsx
    Avatar.tsx
    Chip.tsx
    Dropdown.tsx
```

Routing (e.g. `react-router-dom`): `/chat`, `/knowledge-base`, `/trace` (optional standalone view), `/settings`, with `Chat` as the default/index route.

State: keep chat messages, trace events, and KB documents in lightweight context/hooks (or a small store like Zustand) rather than prop-drilling three levels deep through the shell.

---

## 9. Accessibility & Responsiveness
- All icon-only buttons (close, delete, preview) need `aria-label`s.
- Status badges convey meaning by color **and** text (never color alone).
- Toggle switches are real `<button role="switch" aria-checked>` elements, keyboard-operable.
- Citation chips and trace source rows are focusable and operable via Enter/Space.
- Trace panel becomes a full-screen overlay on mobile rather than a squeezed column.
- Sidebar collapses to an icon rail under `md`, with a hamburger to expand on very small screens.

---

## 10. What "clean" means here
No shadows-as-decoration, no colorful gradients, no illustrations, no marketing-style empty states. The only color that should draw the eye is the primary blue (actions, active nav) and the semantic status colors (green/amber/red). Everything else stays in the slate/gray scale so that when something *needs* attention — a failed ingest, a low-confidence answer, a retrieved source — it visually stands out precisely because the rest of the UI stays quiet.
