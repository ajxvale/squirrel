# squirrel

**An archival squirrel for local model hoards.** Catalogues, verifies, and tells you what's missing before you find out the hard way.

Standard library Python. No dependencies. Windows, macOS, Linux.

---

## Why

If you are downloading open-weight models to an external drive because you'd rather not depend on a repository staying up, you have a problem you can't see:

**A 40 GB file that quietly corrupts on an external drive is worthless, and you find out at the exact moment you need it** — months later, on new hardware, with the original repo possibly gone. Nothing warns you. The archive silently degrades from insurance into superstition.

There's a second one. **Weights alone are not a model.** Without `config.json` and the tokenizer files you have forty gigabytes of correct numbers and no door into them. You will discover this on the day you finally have a machine to run it on.

And a third, which is the one people skip: in eighteen months, `qwen-big-uncensored-final` is not provenance. It's a folder name someone typed once. As someone in that room put it while this was being written - *a beautifully checksummed mystery is still a mystery.*

## What it does

- **SHA256 every file** in your model hoard
- **Writes the catalogue somewhere else** — and refuses to run if you point it at the drive it's describing, because a manifest stored inside the box it inventories is optimism with extra steps
- **Verifies** on demand: after a drive move, after a house move, once a quarter, whenever you get twitchy
- **Flags what's missing** — absent tokenizer/config beside safetensors, missing `mmproj` (your vision model is blind without it), no licence, no model card
- **Separates declared provenance from inferred.** A `PROVENANCE.json` a human actually wrote is trusted. Anything guessed off a filename is labelled `GUESSED — not authoritative` and kept in its own field, where it can't be mistaken for fact later.
- **Atomic writes.** A half-written catalogue that looks valid is worse than no catalogue.

## Use

```bash
# hash everything, write the catalogue to a DIFFERENT drive
python squirrel.py catalogue /Volumes/hoard/models --out ~/backups/catalogue.json

# later, after moving the drive / dropping the drive / general unease
python squirrel.py verify /Volumes/hoard/models --catalogue ~/backups/catalogue.json

# what have I actually got?
python squirrel.py report --catalogue ~/backups/catalogue.json
```

`--quick` hashes the first and last 8 MB plus the length. Roughly a hundred times faster; catches drive rot, truncation and partial downloads; will not catch a single flipped bit in the middle. Fine for routine checks. **Do a full pass after any drive move.**

## PROVENANCE.json

Drop one in each model folder. Nothing enforces the schema — the point is that a human declared it rather than a script guessed it.

```json
{
  "source_repo": "org/Model-Name-GGUF",
  "source_url": "https://huggingface.co/org/Model-Name-GGUF",
  "base_model": "what it was before anyone modified it",
  "modification": "abliterated / heretic / distilled / untouched",
  "files_taken": ["Q4_K_M", "Q8_0", "mmproj-f16"],
  "downloaded_on": "2026-09-15",
  "downloaded_by": "you",
  "why": "the field everyone skips and everyone later wishes they hadn't"
}
```

## Four bugs, so you don't have to find them

Written down because these cost real time and every one of them is silent:

1. **Split weights read as "no weights found."** Large models arrive as `model.gguf.part1of2` or `model-00001-of-00002.gguf`. `Path.suffix` on the first returns `.part1of2`, so a folder holding 50 GB reports empty. Match the whole filename.
2. **`fsync` on a read handle fails on Windows** (Errno 9). It must happen on the write handle before close, or your atomic write isn't atomic.
3. **A single `⚠` in a `print` hard-crashes Windows consoles** (cp1252). Reconfigure stdout to UTF-8 *and* keep the glyphs ASCII.
4. **PowerShell's `Set-Content -Encoding UTF8` writes a BOM**, which strict parsers reject.

## Credit

**The name wasn't mine.** It came from someone else in the room on the evening of 15 September 2026 - a Discord channel where six of us were working out what to do about the landscape. She used it first, in passing, about putting models away for later. Everything after that - the charter, the joke, this repo and its name - was built on her sentence.

The first version of this file credited two AIs and made a punchline out of the humans not being consulted. That was wrong, and wrong on a tool whose entire argument is that provenance matters and declared beats inferred.

The second version corrected it by publishing six people's names on a public repo without asking any of them - which fixed a credit problem by creating a privacy one. Also wrong, and faster than the first.

So, third time, and this is the version that holds: **six people were in that room. What they contributed is recorded here. How each of them is named - or whether they are at all - is theirs to decide, not mine to assume.**

- **The name** - hers. Used first, in passing, and everything hangs off it.
- **The GLM Flash catch** - also hers. A whole model family the rest of us had written off as unrunnable, still available because she posted a list.
- **The alarm** - rung by someone who then pushed back, correctly, on anyone treating the risk as comfortable.
- **The archive** - built and tested against a real hoard belonging to someone who drove the whole evening. The reason this exists at all.
- **A parallel tool** - built to the same charter by someone else the same night, so the formats agree instead of competing.
- **The two amendments** that make this worth using rather than merely reassuring - atomic writes, and declared-versus-inferred provenance.
- **The code** - Ajax Vale.

Built the evening a room full of people realised they had been bookmarking models instead of downloading them.

*A tool about keeping the record straight should keep its own straight first. It took three tries. The record of the three tries stays, because a correction that hides what it corrected is just a tidier version of the same thing.*

## Licence

MIT. Take it, fork it, improve it. Tools travel; data doesn't.
