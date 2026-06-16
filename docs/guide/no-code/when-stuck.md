# When something's not working

Almost every hiccup is small and quick to fix. Here are the ones people actually
run into, each with a plain answer. None of these require a command — just a
different thing to say.

If a word here is unfamiliar, the [plain-language dictionary](words.md) has it.

---

## "I typed `/` and there are no KB commands — did the install fail?"

**No — that's expected.** The main plugin, `kb-lifecycle`, deliberately has **no
slash commands**. It works by listening to what you say, not through a menu. So an
empty `/` list doesn't mean anything's broken.

The way to confirm it's working is to **start a session and talk to it** (see the
next item). If you specifically *want* menu commands, that comes from a different
plugin (`kb-wiki-vnext`) — but you don't need it to get going.

---

## "How do I even know it's working?"

Ask the assistant directly:

> *"What's the current state of this project?"*

- If it answers from your recorded memory — naming decisions or open items you
  saved — it's working.
- If it draws a blank or makes a vague guess, the memory probably wasn't loaded
  yet. Say *"start a KB session"* and ask again.

---

## "Nothing happened when I started — it doesn't seem to know anything"

This is normal in **Cowork**, and not a sign of a problem: Cowork doesn't load the
memory on its own. You start it yourself, every time, with:

> *"Start a KB session."*

Make that your first message in any working chat. (In **Claude Code** this is
automatic — if it didn't happen there, the project might not have a memory set up
yet; see [your first session](first-session.md), Step 2.)

---

## "I asked it to remember something, but it didn't seem to save it"

The assistant decides when to reach for the memory based on how you phrase things,
and it works best when you're explicit — especially in Cowork. If it just chatted
back without saving, say it plainly:

> *"Please record that as a decision in the knowledge base."*

Naming the action plainly — *"record a decision,"* *"save this to the KB,"*
*"file this"* — works far better than a vague *"remember this."* If you're not
sure it saved, ask: *"did you save that to the knowledge base?"*

---

## "I searched for something I know is in there, and it found nothing"

The memory matches the **actual words** in your records, not their meaning. So a
search for "car" won't find a record that only says "vehicle." Three easy fixes:

- Try the words you think are *actually in the record*.
- Use a shorter root — "deploy" will also catch "deployment" and "deploying."
- Easiest of all: **just ask the assistant** — *"find what we decided about the
  newsletter"* — and let it do the looking. It can read the records and find what
  you mean even when an exact-word search misses.

---

## "Do I even need all this?"

A fair question, asked honestly. If you only want a few light notes and you don't
care about keeping a *history* of how your thinking changed, then a simple notes
file plus your assistant's built-in memory is the simpler, right choice — you
don't need KB Factory.

It earns its place when you want decisions and reasoning to *stick* across many
conversations, and to be able to look back and see what changed and why. The
even-handed version is in the [comparison](../../comparison.md).

---

## Still stuck?

- For setup questions (Python, the memory folder, getting a plugin installed),
  see [installation](../../installation.md).
- For a fuller, slightly more technical list of fixes, see the main
  [troubleshooting](../troubleshooting.md) page.
- To go back to basics, return to [your first session](first-session.md) or
  [what this is](what-this-is.md).
