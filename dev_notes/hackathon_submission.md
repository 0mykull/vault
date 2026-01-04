# Hackathon Submission Worksheet

## Project overview

### General info
- **Project name:** Vault Memory
- **Elevator pitch:** Minimalist second-brain for hackers; capture plain text instantly and let Gemini-powered Memory recall anything on demand.

## Project details

### About the project
Vault Memory was inspired by the desire for a Google Keep–style space stripped down to the essentials. I wanted a board that feels like Apple Notes—calm, rounded, obsidian-dark—but still behaves like a “second brain.”

- **Inspiration:** I was juggling book highlights, grocery lists, and hackathon ideas in different tools. I craved one canvas that blends short notes with AI recall without the cognitive load of a full PKM suite.
- **How it was built:**
  1. Flask + Peewee + SQLite power the backend. Every note auto-generates tags via Gemini (with a deterministic fallback) and stores them alongside titles.
  2. HTMX keeps the UI server-rendered yet fluid: two primary actions (“New note” and “Recall”), inline loaders, and a sync state indicator so users always know what’s happening.
  3. Memory uses a tag index (note id + tags + preview) to ask Gemini for an answer. If Gemini hiccups, a local scorer falls back to keyword recall so the user never hits a wall.
- **What I learned:** Prompt engineering for retrieval is as important as the LLM. I also deepened my understanding of how to keep HTMX interactions accessible and how to balance AI calls with graceful fallbacks.
- **Challenges:**
  - Gemini sometimes responds with pretty prose instead of JSON, so I had to parse candidates, regex the ids, and log helpful error copy.
  - Keeping the interface “lean” forced me to rethink layout flows: toggled panels, expandable note cards, and responsive spacing that works on phones.
  - Adding destructive actions (clear notes) while staying in a single-page feel required careful HTMX forms and visual cues.

### Built with
- Python, Flask, Peewee, SQLite
- HTMX, TailwindCSS (CDN)
- Google Gemini API (`google-generativeai`)
- Docker (dev), Git/GitHub

### Try it out links
- Repo: `https://github.com/USERNAME/vault-memory` _(placeholder – update with public repo)_
- Live instructions: `flask --app app run` (documented in README)

### Project media
_Add screenshots + 2 min video via Devpost UI_

## Additional info (judges & organizers)
- **MLH Points / Schools:** _Fill in team universities_
- **Discord usernames:** _List team handles_
- **Submitted elsewhere?** No
- **Public repo?** Yes
- **Demo video this weekend?** Yes (recorded during event)
- **Video mentions hackathon?** Yes (opening line)
- **Opt-in categories:** Best Hack for Hackers, Best Use of Gemini API
- **Sponsor tech feedback:** Gemini API was smooth once prompts were dialed in; JSON format inconsistencies required defensive parsing but overall docs + tooling were solid.
- **GitHub usernames:** _Add every teammate’s handle_
- **AI tools used:** Google Gemini API (generative). No other AI assistants besides Gemini + IDE helpers.
- **Implemented generative AI?** Yes. Model: `gemini-2.5-flash-lite`. _Add Gemini Project Number from AI Studio key page_
- **Cross-promotion?** No
- **Repo/video public post-event?** Yes

### Prize focus
1. **Best Use of Gemini API** – tags + recall lean entirely on Gemini.
2. **Best Hack for Hackers** – Vault Memory is a tool explicitly designed to help hackers capture and recall project ideas instantly.

### Requirements checklist
- [x] Code + video public
- [x] 2-minute demo created during hackathon (mentions event)
- [x] No prior work, no cross submissions
- [x] Repo ready for judges

> _Next actions before submission:_ upload media, finalize repo URL, fill in school/Discord/GitHub specifics, and capture the Gemini project number.
