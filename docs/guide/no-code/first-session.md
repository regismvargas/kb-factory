# Your first session (just by talking)

This is a hand-held walkthrough. We'll set up your project's memory and record
your first thing — mostly just by **chatting** with your assistant.

Here's the honest version up front: once you're set up, you *never* type a
command — you just talk. The **setup** has two small one-time steps (installing an
add-on, and making sure your project has a memory folder), and *one* of them might
need a hand from someone technical. We'll tell you exactly when, and it only
happens once.

We'll use **Claude Cowork** (the desktop app, and the friendliest option for
people who don't code) for this walkthrough. If you use **Claude Code** instead,
the steps are the same except it starts sessions for you automatically — we'll
flag the differences as we go.

> **What you need first:** the Claude desktop app with **Cowork**, and a project
> (any folder you're working in). That's it.

After each step there's a **"You'll know it worked when…"** check, so you're never
guessing whether you're on track.

---

## Step 1 — Add the plugin (one time)

A **plugin** is a small add-on that teaches your assistant how to use the project
memory. You install it once.

1. Open the Claude desktop app and switch to **Cowork**.
2. Open the settings where add-ons live — look for **Customize → Plugins** (the
   exact wording can vary a little by version).
3. Add **KB Factory** as a plugin source. You'll do this one of two ways,
   depending on what you have:
   - **Point it at the project online:** add the KB Factory repository as a
     plugin *marketplace* (a place the app pulls add-ons from), then install the
     plugin named **`kb-lifecycle`**.
   - **Or add a folder you already have:** if someone gave you the KB Factory
     files, upload the `plugins/kb-lifecycle` folder as a custom plugin.

`kb-lifecycle` is the only plugin you need to start. (There are two others for
later — see [the plugins](../plugins.md) — but skip them for now.)

> **This is the fiddliest step in the whole guide.** Finding the Plugins screen
> and adding a source is only a few clicks, but the exact button labels move
> around between app versions, so we can't promise the precise wording. If you get
> stuck *here*, this is the one moment worth asking someone who's added a Cowork
> plugin before — or following the step-by-step (with exact menu paths) in
> [installation](../../installation.md). Everything *after* this step is just
> talking.

> **You'll know it worked when…** the plugin shows up as installed/enabled in that
> same Plugins screen. If you reopened the app and it's listed, you're set.

> **🔔 Heads up — an empty `/` menu is normal.** The main plugin (`kb-lifecycle`)
> adds **no slash commands** on purpose. So if you type `/` and see no "KB"
> entries, *nothing is broken* — this plugin works by listening to what you say,
> not through a menu. You drive it by talking, which is exactly what the rest of
> this page does. (A "slash command" is just a shortcut you'd pick from a menu
> after typing `/`; this plugin simply doesn't use them.)

---

## Step 2 — Give your project a memory

The memory is a small folder (named `.kb`) that lives inside your project. You
don't create it by hand — you **ask your assistant to**:

> *"Set up a knowledge base for this project."*

Because the `kb-lifecycle` plugin now ships with the memory scaffold built in,
the assistant can usually set this up from the plugin alone — no downloads, no
repo. One of two things will happen, and both are fine:

- **It sets it up for you.** The assistant creates the memory and confirms it's
  ready. Great — move to Step 3.
- **It says it can't create files here.** Some setups don't let the assistant
  create folders on its own. That's okay — it's a **one-time** thing, and you have
  three ways past it:
  1. **Ask someone technical** to do the short setup once — it's "copy a folder and
     run one line," and the exact steps are on the
     [installation](../../installation.md) page.
  2. **Do it yourself** — that same one-time setup is genuinely short, and you
     won't need to touch it again afterward.
  3. **Ask the community** — open an issue on the project's GitHub describing what
     you're trying to do; that's exactly what it's there for.

  Once the memory folder exists, *everything* below works by chatting, forever —
  this is the only step that might need a hand.

> **Why we're upfront about this:** whether the assistant can create the folder
> itself depends on your specific setup, and we'd rather tell you the truth than
> promise something that might not happen on your machine. The *using* part is
> always just talking — only this first folder might need a hand.

> **You'll know it worked when…** you ask *"is there a knowledge base set up for
> this project?"* and the assistant confirms there is.

---

## Step 3 — Start the session

Starting a "session" just means telling the assistant to **load the project's
memory** before you begin, so it works from what you actually decided — not from
guesses.

In **Cowork**, do this at the start of every working chat:

> *"Start a KB session."*

That's all. (In **Claude Code** you can skip this — it loads the memory
automatically the moment you open the project.)

> **You'll know it worked when…** you ask *"what's the current state of this
> project?"* and the assistant answers from your recorded memory. If it draws a
> blank, just say *"start a KB session"* again and re-ask.

---

## Step 4 — Record your first thing

Here's the habit that makes the whole thing pay off. Whenever something worth
keeping comes up, just **say it** and ask the assistant to remember it:

> *"Remember this decision: we'll send the newsletter every Friday. It's an
> important one — keep it front and center."*

The assistant writes it down as a **decision** and, because you said "front and
center," marks it as important so it loads at the start of every future session.

You don't have to use the word "decision." *"Note that…"*, *"remember that…"*, or
*"log this…"* all work — the assistant figures out what kind of thing it is. (The
five kinds are explained in plain words [here](words.md#the-five-kinds-of-things-you-can-save).)

> **You'll know it worked when…** the assistant gives you a short confirmation —
> usually the title of what it saved and a short ID. That means it's safely in
> the memory, not just in the chat.

---

## Step 5 — Recall it (the payoff)

Now the reason you did all this. Instead of scrolling back or hoping the
assistant remembers, just **ask**:

> *"What did we decide about the newsletter, and why?"*

It looks in the memory and answers from the actual recorded decision — today,
next week, or in a completely new chat. It even works across apps: something you
saved in Cowork is there when you (or a teammate) open the project in Claude Code.

Other things you can simply ask:

> *"What's still open on this project?"*
>
> *"What do we know about our users so far?"*

> **You'll know it worked when…** the answer matches what you saved in Step 4 —
> ideally quoting it back — rather than a vague guess.

---

## Step 6 — When something changes, don't overwrite it

Plans change. When a decision is no longer true, **don't** ask the assistant to
"edit" or "delete" it. Ask it to **replace** it instead:

> *"We moved the newsletter to Tuesdays — please replace the old decision with
> this."*

The old decision stays in the memory, linked to the new one. So *"what do we send
on Fridays?"* now gives the current answer, and *"why did we move it?"* can still
be answered later. Keeping that trail is the entire reason a memory beats a notes
file. (The technical word for this is **supersede** — defined
[here](words.md#supersede).)

> **You'll know it worked when…** asking the question again returns the *new*
> answer, and the assistant can still tell you what the old one was if you ask.

---

## Step 7 — Wrap up

When you're done for the session, close it so the assistant tidies the memory and
refreshes its summary for next time:

> *"Let's wrap up the session."*

That's the full loop: **start → record → recall → replace when things change →
wrap up.** You'll repeat it naturally as you work.

---

## What to read next

- [Everyday use](../everyday-use.md) — the same loop in a bit more detail, once
  you've done it once.
- [The words it uses](words.md) — any term you weren't sure about.
- [When something's not working](when-stuck.md) — the small things that trip
  people up, with one-line fixes.
