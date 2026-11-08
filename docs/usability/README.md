# Usability sessions (M5-03)

Five people, a phone, a stopwatch, about 10 minutes each. The aim is to find out whether a stranger can use the site without help (PRD success measures S6 and S7). Nothing here needs more than a chat and a notes file.

## What has to be true to pass

| Measure | Target | Source |
| --- | --- | --- |
| Time for a **first-time visitor** to find their team's next match and where to watch it | **30 s or less** | S6 |
| Time for a **returning visitor** to do the same | **10 s or less** | S6 |
| People who finish choosing their team and service **without any help** | **4 of 5** or more | S7 |

Whether the targets are met is judged on the people's times: for each of the two times, at least 4 of the 5 must be inside the target. One slow person is a finding to read, not a failure of the site.

## Who

At least **5 volunteers** who watch football in Brazil: family and friends. Mix them on purpose: at least one who is over 50, at least one who does not follow a big club, at least one who rarely uses a phone for anything but messages. Nobody who helped build the site. The owner may be present but only reads the script and the stopwatch; **do not help, hint, or point**.

Record each person as **P1 to P5** only. **No names, no photos, no recordings** in this repository (see [PRIVACY.md](../../PRIVACY.md) for the line the project holds for visitors; volunteers get the same). Ask if it is fine to write down what they did and how long it took.

## Setup

- Their **own phone** if they are willing (the site stores its choices only in the browser: use a private tab or the page's "Apagar meus dados" button between sessions so the next person starts clean). Otherwise the owner's phone, with the data reset.
- The live site: <https://raissonls.github.io/ubi-ludus/>. A normal 4G or Wi-Fi connection.
- A stopwatch on another device. Notes in a copy of the sheet below.
- Run it on a day with matches in the next few days, so there is something to find.

## Script

Say it in your own words, but keep to this. Do not name any button.

**Opening (read once).** "Isto não é uma prova, o que estamos testando é o site, não você. Se algo for confuso, a culpa é do site. Eu não vou poder ajudar durante o teste; faça como você faria sozinho. Pode falar o que está pensando em voz alta, se quiser."

**Task 1: first-time visitor.** Hand over the phone with the browser **open on the address, not yet loaded**, with the data reset. "Você torce para um time de futebol, certo? Qual? Abra este endereço e descubra **quando é o próximo jogo do seu time e onde dá para assistir**. Diga em voz alta quando achar."
- **Start the stopwatch** when they tap to open the page. **Stop** when they say the time and the place (channel or service) aloud and it is on the screen.
- Note if they chose a team and a service, and how (search, list, skipped).

**Task 2: returning visitor.** Close the tab. Wait about a minute (talk about something else). "Agora imagine que é outro dia e você quer saber de novo. Abra o site de novo e me diga **onde assistir ao próximo jogo do seu time**."
- Start when they tap to open the page; stop when they say the place aloud. (Their choices were saved by task 1, so nothing needs choosing.)

**Task 3: one question each (no timing).** "Existe algum jogo hoje? Mostre." / "Como você saberia se o horário de um jogo mudou?" / "O que você faria se o canal estiver errado?" Note what they do, not what they say they would do.

**Close.** "O que foi mais difícil? O que você mudaria? Você usaria isto? Por quê?" Thank them.

## What counts as unaided

**Unaided** means the person finished choosing a team (and a service if they wanted one) without the owner speaking, pointing, or giving a hint, and without giving up. A question they ask out loud ("é aqui que eu clico?") that the owner **does not answer** is fine as long as they carry on alone. If they stop and ask for help twice, or say they give up, it is **not unaided**; end the task and note where.

Count a task as **timed** only if it ended with the answer on the screen. If someone gives up, write the time they stopped, mark "gave up" and keep going with the next task.

## Sheet (copy this into `docs/usability/YYYY-MM-DD.md`, one file per day of sessions)

```markdown
# Usability sessions 2026-12-__

| P | Age band | Phone | Follows | T1 first time (s) | Unaided? | T2 returning (s) | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P1 | 30-40 | Android | Palmeiras | 24 | yes | 6 | picked the team from the list at once |
| P2 | 55+ | iPhone | Sport | 71 | no (asked twice) | 12 | did not see the team list; typed in the search box |

**Targets:** first time <= 30 s: _ of 5. Returning <= 10 s: _ of 5. Unaided: _ of 5.

## Findings

| # | What happened | Who (P#) | How bad | Fix | Done in |
| --- | --- | --- | --- | --- | --- |
| 1 | Two people did not notice the team list below the search box | P2, P4 | blocks the task | move / rename | PR # |

How bad: **blocks the task** (someone could not finish), **slows** (finished, but hesitated or went the wrong way), **polish** (annoyed, not slowed).
```

## What to do with the findings

- A problem **two or more people** hit is fixed before launch, in a pull request that names the finding. A problem with a **blocks the task** note is fixed even if only one person hit it.
- A problem of one person that only **slows** or is **polish** goes in the findings table with "not fixed: one person" and is looked at again after the 14-day window.
- After the fixes, **re-run the task that failed with one new person** and write their line in the sheet.
- When done: tick the boxes in issue [#38](https://github.com/raissonls/ubi-ludus/issues/38) and link the sheet. The date of the sessions and the counts go in the [closure review](../closure-review.md).

## Before the first session, check yourself

A five-minute self-run catches silly problems that would waste a volunteer's time: reset the data, open the site on a phone, and do task 1 yourself. If it takes you more than 15 seconds, fix that first.
