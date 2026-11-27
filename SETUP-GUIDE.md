# Senate Nuclear Map — setup guide (no technical background needed)

You already have three things: a GitHub repository (`julianhong-del/senate-nuclear-map`), a live site at `https://julianhong-del.github.io/senate-nuclear-map/`, and a Supabase project with one account. This guide gets the final version live, turns on the automatic updates, and locks the doors. Budget 30 minutes.

What the pieces are, in plain terms:
- **GitHub** stores the website's files. Anything you upload there becomes the live site about a minute later.
- **GitHub Actions** are little robots inside GitHub. Two of them will run on a timer: one fetches news every morning, one refreshes the Senate roster every week.
- **Supabase** is the private database where your notes, tasks and lists live. Only accounts you create can read it.

---

## Part 1 — Put the final files on GitHub (10 minutes)

1. Double-click `senate-nuclear-map.zip` to unzip it. You get a folder called `senate-nuclear-map`.
2. Open your repository in the browser: github.com → your profile → `senate-nuclear-map`.
3. Click **Add file** (top right of the file list) → **Upload files**.
4. From the unzipped folder, drag these onto the page: `index.html`, `people.json`, `news.json`, `README.md`, `SETUP-GUIDE.md`, `supabase.sql`, `supabase-update.sql`, and the **`scripts`** folder (drag the whole folder; GitHub keeps it as a folder). GitHub will say some files will be replaced; that is what we want.
5. Scroll down, click the green **Commit changes** button.
6. The `.github` folder is invisible on a Mac, so make its two files by hand:
   - **Add file → Create new file**. In the name box type exactly `.github/workflows/news.yml` (the slashes create folders). In the big editor paste the contents of `news.yml` from the zip (to see it: in Finder press Cmd+Shift+. to show hidden files, open `.github/workflows/news.yml` in TextEdit, select all, copy). Click **Commit changes**.
   - Repeat for `.github/workflows/roster.yml`.
7. Wait a minute, open the site, and press Cmd+Shift+R to force a fresh load. You should see the sign-in screen (if Supabase is connected) or the Today page.

## Part 2 — Let the robots run (5 minutes)

1. Repository → **Settings** → left menu **Actions** → **General**.
2. Scroll to **Workflow permissions** → choose **Read and write permissions** → **Save**. (This lets the robots save the news and roster files.)
3. Click the **Actions** tab at the top. On the left you'll see **Daily news** and **Roster and committees**.
4. Click **Daily news** → **Run workflow** → green **Run workflow**. In about a minute it shows a green check. Reload the site: the **News** tab now has headlines.
5. Click **Roster and committees** → **Run workflow**. Green check means it worked (today it should change nothing).

From now on: news refreshes every morning at about 6:30 ET; the roster refreshes every Monday and daily from January 4 to 20 while the new Congress organizes. If GitHub ever emails you that "scheduled workflows were disabled" (it does this if a repository has had no activity for 60 days), open the Actions tab and click **Enable** — one click.

## Part 3 — Finish Supabase (5 minutes)

1. supabase.com → your project → **SQL Editor** → **New query** → paste the contents of `supabase-update.sql` → **Run**. This allows the database to store lists, tasks and team members. (You already ran the original `supabase.sql`.)
2. **Authentication → Users → Add user → Create new user** for each teammate: their email and a starting password; tick **Auto Confirm User**. Tell them the password in person or by text, not in the same email as the link.
3. Make sure **Authentication → Sign In / Providers → Email → "Allow new users to sign up"** is OFF. Nobody can create an account except you.
4. Each teammate opens the site, enters the Supabase URL and anon key once under Settings (or you bake them into `index.html` — see below), signs in, and from then on just signs in.

**Bake the connection in so nobody pastes keys:** on GitHub open `index.html` → click the pencil → use the browser's find (Cmd+F) for `SUPABASE_URL = ''` → put your project URL between the quotes, and your anon key on the next line → **Commit changes**. Everyone then sees only the sign-in screen.

## Part 4 — Daily use (what to expect)

- **Today**: your tasks, follow-ups due, priority-5 senators not yet met, recent meetings, next steps, referrals waiting, what changed recently.
- **People**: the roster. Click a row for the person page; click the name to jump to them on the graph.
- A **person page**: status (Not met / Met, with Follow up and Not a fit modifiers), stance, our ask / their ask, relationship notes (channel, gatekeeper, hooks), notes with **Dictate**, next step and due date, log an interaction (type, sentiment, issues, attendees, who they suggested), tasks (type `@name` to assign), history, committees with every subcommittee role, bills they back, their news, connections, sources.
- **Graph**: committees in the inner ring, subcommittees around them, senators and staff orbiting. Click anything to focus; Esc or empty space to release.
- **Meetings**: everything logged, with a 30-day digest and filters.
- **Bills**, **News**, **Settings** (export a JSON backup any time).

## Part 5 — Making it more secure

Already in place: HTTPS; notes readable only by signed-in accounts (row-level security); no public sign-up; the key in the page can't read anything by itself; every change stamped with the editor's email and copied to a history table.

Worth doing now, each a few clicks in Supabase:
1. **Strong passwords**: Authentication → Policies (or Settings → Auth) → minimum password length 12.
2. **Two-factor codes**: Authentication → Providers → turn on **MFA / TOTP** so sign-ins can require an authenticator app.
3. **Company-only rule**: SQL Editor → run
   `create policy "company only" on public.docs as restrictive for all to authenticated using (auth.jwt() ->> 'email' like '%@generalmatter.com');`
   Then even a stray account on another domain reads nothing. (Replace the domain if yours differs.)
4. **Set the site address**: Authentication → URL Configuration → Site URL = your site; add it under Redirect URLs. Password-reset links then only work for your site.
5. **Backups**: Database → Backups (daily on the Pro plan; on Free, use the site's Settings → Export notes weekly and keep the file somewhere safe).
6. **Remove people fast**: Authentication → Users → delete; their access ends immediately.

Worth knowing:
- The repository is public, so anyone can view the app code and the public roster. Your notes are never in the repository. If you prefer the code hidden, make the repository private (Settings → General → Danger Zone) — on a free GitHub account that turns off the website, so you'd need a paid GitHub plan or Netlify (drag the folder to app.netlify.com/drop) to keep hosting it.
- Never paste the Supabase **service_role** or **secret** key anywhere in the site. Only the **anon / publishable** key belongs there.
- Dictation uses your browser's own speech recognition (Chrome, Edge, Safari); audio is processed by the browser vendor, not stored by the site.

## If something breaks

- Site shows an old version: press Cmd+Shift+R.
- "Could not save (HTTP 400)" after an update: run `supabase-update.sql` (Part 3, step 1).
- "Could not save (HTTP 403)": the policies are missing; re-run `supabase.sql`.
- Sign-in fails: Authentication → Users → the account exists and is confirmed; use **Forgot password?** on the sign-in screen.
- News tab empty: Actions → Daily news → Run workflow, then check the run for a red step.
