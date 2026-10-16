# AI Work Discovery

A discovery run looks at how you work with AI — your own sessions, setup and tools — and writes a
folder of plain-text results that you send to your consultant. It reads; it never changes anything.

## Install (Claude Code, desktop app, claude.ai)

**By invitation only.** This repository is public so you can see what it does, but you may install
and run it only if Matthias Frank Consulting has invited you to. See `LICENSE.md`.

**From GitHub:**

    /plugin marketplace add mf-consulting-notion/ai-setup-discovery
    /plugin install ai-work-discovery@mf-discovery

In claude.ai or the desktop app: Customize → Plugins → Add marketplace → `mf-consulting-notion/ai-setup-discovery`.

**From a file:** Customize → Plugins → Add → Upload plugin, and choose the `.zip` you were sent.
In Claude Code: `claude --plugin-dir <unpacked folder>` runs it for one session without installing.

## Run

- **Claude Code** (terminal or desktop Code tab): type `/ai-work-discovery:discovery-run`
- **claude.ai chat, desktop chat or Cowork**: type `/ai-work-discovery:discovery-run-chat`

It takes about 10 minutes of your time; the rest runs by itself. At the end you get a folder of
plain text files to email to hello@matthiasfrank-consulting.com.

## No plugins possible?

Open `chat/discovery-run-chat.md`, copy its contents into a new chat, and follow along.
