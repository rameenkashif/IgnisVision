# Live monitoring

The commander's dashboard for open incidents. Administrators can view it but cannot change anything.

## Logging an emergency

1. Press **+ Log new emergency**.
2. Enter the address and city, the structure and incident type, and the number of floors and zones per floor. Zones can be given labels such as "Lobby".
3. Optionally assign responders to zones now (you can change this later on **Team deployment**).
4. Press **Dispatch team & create incident**. The incident appears in the briefing state.

## Briefing and going live

In the briefing state you see the sector map with assignments. Press **Teams on site — start live monitoring** when operations start. Every zone begins as **Unclassified** until it has been analysed.

## Reading the dashboard

- **Zone map:** each zone shows its status with a colour, an icon **and** a word: Safe, Caution, Unsafe, Blocked or Unclassified. A zone whose last analysis is older than the configured limit shows **No current analysis**: never treat it as safe.
- **Select a zone** to open its details: why it has that status, its confidence, the latest frame with the damage overlay, its history, and who is assigned. Commanders can rename the zone's label there.
- **Alerts:** critical alerts are shown at the top and read aloud (if voice alerts are on in Settings). Acknowledge them once handled.
- **People detected:** ranked by the Rescue Priority Index (critical first). Use **Mark rescued** or **Not a person**.
- **Zone classification** and **Safety threshold** charts summarise the incident. The safety-threshold bar warns, and suggests considering evacuation, when safe plus caution zones fall below the configured share of analysed zones.

## Several incidents

If more than one incident is open, choose it from the tabs under the title.

## Closing an incident

Press **Close incident** and confirm. The report is compiled immediately and appears under **Incident reports**.
