# Administration

For administrators. Every change here is recorded in the audit log.

## Users

- **New user:** choose a username, full name, role and language. A temporary password is shown **once**; give it to the person. They must change it at first sign-in.
- **Edit** changes the name, role or language. Changing a role signs the person out everywhere.
- **Reset password** creates a new temporary password and signs the person out.
- **Deactivate** blocks sign-in and ends their sessions; **Reactivate** allows it again. You cannot change your own role or deactivate yourself.

## Training scenarios

Create scenarios, upload images or videos, and label them in the browser:

- **Split into grid** or **Draw region** (click the corners, then **Finish**) for zone items; **Draw person box** for posture items.
- Choose the correct label for each region or person, and write the explanation in English and Urdu.
- For videos, pause on the right frame and press **Use current video frame**.
- **Save labels** also computes the model's output for the item. Items without labels or model output are hidden from trainees.
- After a model update, press **Recompute reference outputs**.

## System settings

Rescue priority weights and bands, zone-fusion thresholds, timings, data retention, AI features and trainer grading. Values are checked before saving (for example, priority bands must be critical > high > medium). Defaults are starting points and must be tuned with Rescue 1122.

## System status

Database, models, analysis jobs, storage, backups, AI and active sessions, refreshed every 15 seconds. Warnings explain what needs attention, for example a backup older than 36 hours or models running on the mock fallback.

## Audit log

Every user change, password reset, settings change, deletion and scenario change, with who did it, when and from which IP address. Filter by action, type and date, and open **Details** to compare before and after.
