# Senate Nuclear Map — setup

A single-page wesb app: `index.html` (the app, with the graph library inlined) and `people.json` (the roster: 100 senators, 24 committees and 70 subcommittees with chair/ranking roles, committee staff, nuclear relevance and priority scores).

Notes, meetings and referrals are stored in one of three places, chosen automatically when the page loads:

| Where | When | Who sees it |
|---|---|---|
| Supabase (recommended for a team) | Settings → Supabase URL + anon key saved, user signed in | Everyone you give an account to |
| This browser only | No Supabase configured | Only that browser; use Export/Import to move notes |
| claude.ai artifact store | Only when opened as the Claude artifact | Everyone the artifact is shared with |

---

## 1. Put it online (10 minutes)

**Option A — Netlify Drop (fastest)**
1. Go to https://app.netlify.com/drop
2. Drag the `senate-nuclear-map` folder (both files) onto the page.
3. You get a URL like `https://random-name.netlify.app`. Rename it under Site settings → Change site name.

**Option B — GitHub Pages (versioned, updatable)**
1. Create a repo, e.g. `general-matter/senate-nuclear-map` (private is fine for Pages on paid plans; otherwise public).
2. Add `index.html`, `people.json`, `supabase.sql`, `README.md` and commit.
3. Settings → Pages → Source: *Deploy from a branch* → `main` / `/ (root)` → Save.
4. The site is live at `https://<org>.github.io/senate-nuclear-map/` in about a minute. Every push updates it.

Either host serves over HTTPS, which is required for sign-in to work.

---

## 2. Shared, secure storage with Supabase (20 minutes)

Supabase is the right choice here: a hosted Postgres database with built-in email/password auth and row-level security, free tier is plenty, and the app talks to it directly from the browser with no server of your own.

1. **Create a project** at https://supabase.com → New project. Pick a region near Washington (us-east-1). Save the database password somewhere safe (you will not need it in the app).
2. **Create the table and policies**: SQL Editor → New query → paste the contents of `supabase.sql` → Run. This creates `docs` (the data), `docs_history` (an audit trail), and policies so that *only signed-in users* can read or write. The public "anon" key by itself can do nothing.
3. **Turn off public sign-up**: Authentication → Providers → Email → switch off *Allow new users to sign up* (keep *Email* enabled). Optionally also require a minimum password length (Authentication → Policies).
4. **Create your team's accounts**: Authentication → Users → *Add user* → *Create new user* → enter email + a temporary password, tick *Auto confirm user*. Send each person their password out of band and ask them to change it (Supabase → Users → "Send password recovery" also works).
5. **Copy the connection details**: Project Settings → API → *Project URL* and the *anon public* key.
6. **Connect the app**: open your site → Settings → paste the URL and anon key → *Save and connect*. The page reloads; sign in with the account from step 4. Everyone on the team does the same once per browser (or bake the two values into `index.html` — see below — so nobody has to paste anything).

**Bake the project in (optional):** near the top of the script in `index.html` set

```js
const SUPABASE_URL = 'https://xxxx.supabase.co';
const SUPABASE_ANON_KEY = 'eyJ...';
```

and redeploy. Teammates then only see the sign-in form.

**Restrict to your company domain (optional, recommended):** in the SQL editor run

```sql
create policy "company only" on public.docs as restrictive for all to authenticated
  using (auth.jwt() ->> 'email' like '%@generalmatter.com');
```

so even a stray account outside your domain cannot read anything.

### Why this is secure enough
- The anon key is designed to be public; it only identifies the project. Row-level security means it grants no data access without a valid login.
- Logins are email + password over HTTPS, issued and verified by Supabase Auth. Sessions expire and refresh automatically; *Sign out* revokes them.
- No sign-ups: only accounts you create exist. Delete a user in the dashboard and their access ends immediately.
- Every change is stamped with the signed-in user's email on the server (not by the browser) and copied to `docs_history`, so an accidental overwrite can be recovered with one SQL query.
- Nothing sensitive is in the repo: no database password, no service-role key. Never put the *service_role* key in the app.

Optional hardening: enable MFA/TOTP for users (Authentication → Providers → MFA), set *Site URL* and *Redirect URLs* to your hosted URL (Authentication → URL Configuration), and turn on Supabase's daily backups (Database → Backups; included on Pro).

---

## 3. Keeping the roster current ("self-updating")

The roster (`people.json`) is static data in the repo; notes live in Supabase. To refresh the roster:

- Re-run the research with Claude (the scheduled task that built this dashboard can regenerate `people.json`), commit the new file, and the site updates on the next deploy. Notes are keyed by person id (`sen-risch-id`), so they survive roster refreshes as long as ids stay the same.
- In January 2027 the 120th Congress seats and committee rosters change; plan a refresh then. Twenty-one senators are leaving; their notes remain attached to their ids for the record.

---

## 4. Day-to-day

- **Today** — follow-ups due (30 days) and overdue (60), priority-5 people not yet met, recent meetings, referrals waiting to be added.
- **People** — the full roster; filter by committee from the left tree, by status or priority; click a row for the person page: properties, every committee and subcommittee with chair/ranking roles, nuclear record, state assets, linked people and sources.
- **Graph** — every senator and staffer around all 24 committees (nuclear committees have a bold ring). Click a node: its referrals and office links pull in and the graph zooms to it; click empty space or *Clear focus* to release them back to their orbit.
- **Meetings** — one place to log a meeting for anyone; names in *They suggested I meet* become referral cards that you can add to the map with one click.
- **Settings** — storage, sign-in, export/import, CSV, demo notes, theme.

Export a JSON backup from Settings before any migration; Import restores it into whichever storage is active.
