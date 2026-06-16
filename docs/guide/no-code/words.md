# The words it uses (plain-language dictionary)

Every term you might meet in KB Factory, in one plain sentence. Skim it once, or
come back whenever a page uses a word you're not sure about.

## The everyday words

### Knowledge base (or "KB")
Your project's memory — the collection of everything the assistant has written
down for you.

### Record
One single thing saved in the memory — one decision, one fact, one open question.
Your knowledge base is made of many records.

### The five kinds of things you can save
Every record is one of five kinds, and you never have to pick — the assistant
does. They are: a **decision** (a choice you made), a **fact** (something
verified), an **assumption** (something you're taking as given for now), an **open
item** (a question still unanswered), and a **learning** (a lesson from
experience).

### Session
One working stretch with your assistant. You "start a session" so it loads the
project's memory before you begin, and "wrap up" when you're done so it tidies
things.

### Session start
The moment the assistant loads the project's memory. In Claude Code it happens
automatically when you open the project; in Cowork you ask for it ("start a KB
session").

### Tier (HOT / WARM / COLD)
How important a record is, which decides when the assistant brings it up. **HOT**
records are loaded every single time (the always-on essentials); **WARM** is the
normal setting — kept and found when relevant; **COLD** is archived but never
thrown away. You just say "this is important" to make something HOT.

### Supersede
A careful word for *replace without erasing*. When a decision changes, the
assistant writes the new one and keeps the old one linked behind it — so the
history of *why it changed* survives. This is the heart of what makes KB Factory
different.

### Provenance
A fancy word for *where something came from*. If a fact was pulled from a
document, the memory remembers which document — so you can always trace a record
back to its source.

### Source
A document or note you brought into the project (a brief, a spec, an email) so the
assistant can link facts back to it.

## The behind-the-scenes words

You don't need these to use KB Factory, but you'll see them in the more technical
pages — here's what they really mean.

### Plugin
A small add-on you install once that teaches your assistant how to use the project
memory. (`kb-lifecycle` is the main one.)

### Skill
The part of a plugin that "wakes up" when you mention something memory-related,
like "record this" or "what did we decide." It's why you can just talk instead of
running commands.

### Hook
An automatic trigger. In Claude Code, a hook loads your project's memory the
moment you open it — no asking required.

### Claude Code vs Cowork
Two ways to use Claude. **Cowork** is the desktop app (easiest for
non-developers). **Claude Code** runs in a terminal (a text-command window most
non-developers never open) and is aimed at developers. The big practical
difference: Code starts your memory session automatically; Cowork you start it by
asking.

### Command line / terminal / CLI
A text window where developers type instructions to a computer. You can use KB
Factory entirely *without* ever opening one — that's what this whole track is
about. "CLI" just stands for that text-command way of doing things.

### SQLite
The tiny, self-contained database that quietly stores your memory as a single file
on your computer. No server, no setup — it's just there.

### FTS5
The part of that database that powers search by matching the words in your
records. (It stands for "full-text search.") You'll only see it mentioned in setup
notes.

### Lexical search
Search that matches the actual *words* you type, not their meaning. So searching
"car" won't automatically find a record that only says "vehicle" — use the words
likely in the record, or just ask the assistant to find it for you.

### Domain
A simple label for an *area* of your project — like "design," "billing," or
"marketing" — so related records group together. Think of it as a folder tab.

### Ingest
To bring a document *into* the project memory so the assistant can link facts to
it. Plain version: "import this file."

### Stdlib-only / no dependencies
A promise about how it's built: it uses only what comes with Python (the
programming language it runs on) out of the box, so there's nothing extra to
install and nothing that can break or go out of date. For you, it just means
"it's simple and it keeps working."

---

Still stuck on something? → [When something's not working](when-stuck.md), or head
back to [your first session](first-session.md).
