# The Goal

This is what I'm trying to build, in plain language. No code, no architecture. Read this first.

---

## What the experience should feel like

I want to sit down, hop in voice chat with 1–3 friends, look at our D&D Beyond sheets, and play through a campaign together. I also want to be able to play alone, or with a different group of friends, without losing campaign data.

A campaign should be able to run for six months and feel like it's been six months. The session three weeks from now should remember what happened tonight. NPCs we wronged should still be wronged. Choices should matter later, not just in the moment.

**The world should remember.** That's the heart of all of this.

I want unique items to feel meaningful. Not "+1 sword" — *meaningful*. Something I want to talk about between sessions.

I want combat to be fun. I want to feel something when I kill an enemy. Combat shouldn't feel like rolling dice for the sake of rolling dice.

I want off-combat skills to matter. A druid should be able to talk to animals and have it matter. A wizard should be able to cast invisibility and have the world react. Intimidation vs persuasion should produce different scenes, not the same scene with different words.

I want the realm to notice. Good deeds and bad deeds should accumulate. Reputations should form. NPCs should remember.

## Player agency has to survive the AI

I want players to solve problems creatively, not feel railroaded into one correct path. If we come up with an unexpected solution, the world should adapt instead of forcing us back onto a scripted route. We should be able to derail plans, ignore hooks, attempt weird ideas, ally with enemies, avoid combat entirely, or fail catastrophically — and the system should roll with it instead of fighting us.

This is the difference between an AI DM and an AI cutscene generator. I'm building a DM.

## Narration describes reality, doesn't create it

The AI does not decide what's true on its own. World state, combat outcomes, character capabilities, and persistent facts have to exist outside the narration layer. The DM's job is to describe what happens — not to invent it on the fly when a player pushes back.

If I say "I attack the goblin" and roll a 2, the dice decided I missed. The DM doesn't get to narrate it as a graze. If I say "I cast Fireball" and I'm a rogue, the DM doesn't get to invent a reason why it works. If I say "says who" after a refusal, the refusal still stands. The world has rules and the DM enforces them. That's the whole job.

## Failure should create story, not dead ends

A failed roll should change the situation, not stop play. Stealth fails → guards are suspicious. Persuasion fails → the NPC wants proof. Lockpick fails → time pressure increases. Combat loss → capture, injury, debt, reputation shift. Failure is fuel, not a wall.

Failure outside combat needs to hurt too. A failed pickpocket should risk jail or a fine. A failed deception should burn the relationship. A failed Athletics check should cost time, alert someone, leave a mark. Right now combat is the only place with teeth. The rest of the world has to bite too.

## Multiplayer should feel collaborative

When friends are at the table, sessions should feel like several people playing together — not several people taking turns talking to an AI. Arguments between party members, stupid plans that succeed, someone sacrificing themselves, one player causing chaos while another cleans it up — that's where the memorable stuff lives. The system needs to leave room for players to bounce off each other.

## The world should reward curiosity

Exploration, investigation, and paying attention should uncover things we'd otherwise miss. Hidden lore, faction politics, strange places, an NPC who lied weeks ago, secrets pieced together over months. The discovery loop is core to how D&D feels — when it works, the world feels alive instead of scripted.

## Tone range matters

A real campaign swings between serious, funny, tense, dumb, emotional, and triumphant. The AI shouldn't flatten everything into "epic fantasy narrator voice." Some of the best tabletop moments are ridiculous accidents that become canon forever. The system needs room for humor, chaos, tension, and emotion without forcing a single tone all the time.

## The world should breathe

Not every room is a setpiece. Not every object hums with ancient magic. Not every NPC has a hidden agenda. Most of the world should be ordinary — quiet roads, boring inns, merchants who don't want to talk, rooms that contain crates and dust. Mystery only feels magical when it's contrasted against normality. If everything is enchanted, nothing is.

Memorable details should recur intentionally, not compulsively. If my character played a lute three turns ago, the lute doesn't need to come back into every following narration. The DM should drop a motif when the scene moves on. Recurring detail is a tool, not a tic.

## Encounters should reward thinking

The world shouldn't feel like a hallway: investigate → goblin → loot → investigate → goblin → loot. I want to solve puzzles, talk my way past problems, find the lever instead of the fight. I want to bribe goblins who are starving. I want to learn a faction is at war with itself and exploit it. I want a problem where the answer isn't obvious and the solution isn't always violence.

Combat is one payoff loop. It shouldn't be the only one.

---

## What failure looks like

The system can be technically working and still failing the goal. Specifically:

- If combat feels like rolling dice for the sake of rolling dice, we've failed.
- If my druid can't have a real moment with a forest spirit, we've failed.
- If a session three months in feels disconnected from the first session, we've failed.
- If a unique item the party found feels the same as starter gear, we've failed.
- If the world reacts the same to mercy as it does to slaughter, we've failed.
- If switching between solo play and friend-group play loses my place, we've failed.
- If players come up with a creative solution and the system forces them back to the "right" path, we've failed.
- If failed rolls just stop play instead of changing the situation, we've failed.
- If failure outside combat doesn't hurt, we've failed.
- If multiplayer sessions feel like four people taking turns talking to an AI instead of playing together, we've failed.
- If multiple players type at once and inputs get silently dropped, we've failed.
- If the DM repeats the same motif five turns running, we've failed.
- If the world feels like a hallway of investigate-fight-investigate-fight, we've failed.
- If the AI invents reality on the fly to accommodate what a player just said, we've failed.
- If everything sounds like the same epic fantasy narrator no matter what's happening, we've failed.
- If the campaign rewards going through the motions more than paying attention, we've failed.

These are the things that should haunt design decisions, not just "does the code run."

---

## How to use this document

This is the north star for priority decisions. When the queue has ten things on it and we're picking what to ship next, the question to ask is: *which of these moves the experience closer to the above?*

A technically clean ship that doesn't move toward the goal is less valuable than a messy ship that does. The reverse is also true — moving toward the goal in a way that breaks reliability is not actually progress.

This document doesn't replace `ROADMAP.md` (the queue), `VIRGIL_MASTER.md` (current state), or `WORKING_WITH_CLAUDE.md` (workflow rules). It sits above them. Those documents say *what* and *how*. This one says *why*.

When in doubt about priority, re-read this. If something on the queue doesn't visibly serve any of these goals, ask whether it should be on the queue at all.
